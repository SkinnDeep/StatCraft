"""Marginal Plot Statistical Engine for Statcraft.

Implements Minitab-identical Marginal Plot:
- 2D scatterplot of Y vs X with complete observations
- Marginal distribution of X placed directly above the scatterplot
- Marginal distribution of Y placed directly to the right of the scatterplot
- Supports three marginal plot types:
  * 'histogram' (with optional fitted normal curve)
  * 'boxplot' (with quartiles, median, whiskers, and outlier detection)
  * 'dotplot' (discrete frequency dot bins)
- Computes summary statistics for both variables and Pearson correlation
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from .model import Column, Worksheet


def compute_marginal_plot(
    worksheet: Worksheet,
    y_index: int,
    x_index: int,
    marginal_type: str = 'histogram',  # 'histogram', 'boxplot', 'dotplot'
    show_normal_curve: bool = False,
    bins: int = 12,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute the complete case data, scatter coordinates, and aligned marginals."""
    if not (0 <= y_index < len(worksheet.columns) and 0 <= x_index < len(worksheet.columns)):
        raise ValueError('Select valid worksheet columns for X and Y.')
    if y_index == x_index:
        raise ValueError('X and Y variables must be distinct columns.')

    col_y = worksheet.columns[y_index]
    col_x = worksheet.columns[x_index]

    if col_y.kind != 'number' or col_x.kind != 'number':
        raise ValueError('Marginal plots require numeric columns.')

    n_total = max(len(col_y.values), len(col_x.values))
    pairs: List[Tuple[float, float, int]] = []

    for row in range(n_total):
        vy = col_y.values[row] if row < len(col_y.values) else None
        vx = col_x.values[row] if row < len(col_x.values) else None
        if vy is not None and vx is not None and math.isfinite(vy) and math.isfinite(vx):
            pairs.append((float(vx), float(vy), row + 1))

    if len(pairs) < 2:
        raise ValueError('Marginal plot requires at least 2 complete paired observations.')

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    row_indices = [p[2] for p in pairs]
    n = len(pairs)

    # Basic statistics
    x_mean = float(np.mean(xs))
    x_sd = float(np.std(xs, ddof=1)) if n > 1 else 0.0
    x_min, x_max = float(np.min(xs)), float(np.max(xs))

    y_mean = float(np.mean(ys))
    y_sd = float(np.std(ys, ddof=1)) if n > 1 else 0.0
    y_min, y_max = float(np.min(ys)), float(np.max(ys))

    # Pearson correlation
    if x_sd > 0 and y_sd > 0:
        r, p_val = stats.pearsonr(xs, ys)
        r_val = float(r)
        p_val = float(p_val)
    else:
        r_val = 0.0
        p_val = 1.0

    # Linear fit
    if x_sd > 0:
        slope, intercept, r_val_lin, p_lin, se_lin = stats.linregress(xs, ys)
    else:
        slope, intercept = 0.0, y_mean

    def get_box(vals: List[float]) -> Dict[str, Any]:
        arr = np.sort(vals)
        q1 = float(np.percentile(arr, 25))
        med = float(np.median(arr))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        inliers = [v for v in arr if lo_fence <= v <= hi_fence]
        outliers = [float(v) for v in arr if v < lo_fence or v > hi_fence]
        lo_whisker = float(inliers[0]) if inliers else q1
        hi_whisker = float(inliers[-1]) if inliers else q3
        return {
            'q1': q1, 'median': med, 'q3': q3, 'iqr': iqr,
            'low_whisker': lo_whisker, 'high_whisker': hi_whisker,
            'outliers': outliers,
        }

    x_box = get_box(xs)
    y_box = get_box(ys)

    # Histogram binning
    n_bins = max(5, min(50, bins))
    # Marginals for X
    x_edges = np.linspace(x_min, x_max, n_bins + 1).tolist() if x_max > x_min else [x_min - 0.5, x_max + 0.5]
    x_counts, _ = np.histogram(xs, bins=x_edges)
    x_counts = x_counts.tolist()

    # Marginals for Y
    y_edges = np.linspace(y_min, y_max, n_bins + 1).tolist() if y_max > y_min else [y_min - 0.5, y_max + 0.5]
    y_counts, _ = np.histogram(ys, bins=y_edges)
    y_counts = y_counts.tolist()

    # Fitted normal curve points for histograms
    x_normal_curve = []
    y_normal_curve = []
    if show_normal_curve:
        if x_sd > 0:
            x_curve_xs = np.linspace(x_min, x_max, 100).tolist()
            bin_w_x = x_edges[1] - x_edges[0] if len(x_edges) > 1 else 1.0
            x_curve_ys = [float(stats.norm.pdf(x, loc=x_mean, scale=x_sd) * n * bin_w_x) for x in x_curve_xs]
            x_normal_curve = [[x, y] for x, y in zip(x_curve_xs, x_curve_ys)]

        if y_sd > 0:
            y_curve_ys = np.linspace(y_min, y_max, 100).tolist()
            bin_w_y = y_edges[1] - y_edges[0] if len(y_edges) > 1 else 1.0
            y_curve_xs = [float(stats.norm.pdf(y, loc=y_mean, scale=y_sd) * n * bin_w_y) for y in y_curve_ys]
            y_normal_curve = [[x, y] for x, y in zip(y_curve_xs, y_curve_ys)]

    # Dotplot binning
    def get_dotplot(vals: List[float], n_dot_bins: int = 25) -> List[Dict[str, Any]]:
        v_min, v_max = min(vals), max(vals)
        if v_max == v_min:
            return [{'val': v_min, 'count': len(vals)}]
        bw = (v_max - v_min) / n_dot_bins
        dots = []
        for v in vals:
            b_idx = min(n_dot_bins - 1, int((v - v_min) / bw))
            center = v_min + (b_idx + 0.5) * bw
            dots.append(center)
        from collections import Counter
        cnts = Counter(dots)
        return [{'val': float(k), 'count': int(v)} for k, v in sorted(cnts.items())]

    x_dots = get_dotplot(xs)
    y_dots = get_dotplot(ys)

    plot_title = title or f'Marginal Plot of {col_y.name} vs {col_x.name}'

    return {
        'graph': 'marginal_plot',
        'analysis': 'marginal_plot',
        'title': plot_title,
        'y_name': col_y.name,
        'x_name': col_x.name,
        'marginal_type': marginal_type,
        'show_normal_curve': show_normal_curve,
        'n': n,
        'xs': xs,
        'ys': ys,
        'row_indices': row_indices,
        'x_stats': {
            'mean': x_mean, 'stdev': x_sd, 'min': x_min, 'max': x_max,
            'box': x_box, 'edges': x_edges, 'counts': x_counts,
            'normal_curve': x_normal_curve, 'dots': x_dots,
        },
        'y_stats': {
            'mean': y_mean, 'stdev': y_sd, 'min': y_min, 'max': y_max,
            'box': y_box, 'edges': y_edges, 'counts': y_counts,
            'normal_curve': y_normal_curve, 'dots': y_dots,
        },
        'correlation': r_val,
        'p_value': p_val,
        'slope': float(slope),
        'intercept': float(intercept),
    }
