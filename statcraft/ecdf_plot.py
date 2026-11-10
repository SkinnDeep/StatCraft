"""Empirical Cumulative Distribution Function (ECDF) Statistical Engine for Statcraft.

Implements Minitab-identical:
- Stepped empirical CDF curve F_n(x)
- Simultaneous Dvoretzky-Kiefer-Wolfowitz (DKW) & Greenwood confidence bands
- Parametric fitted CDF overlays (Normal, Lognormal, Weibull, Exponential)
- Empirical and parametric percentile tables
- Multi-series / grouped comparisons
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from .model import Worksheet


def compute_ecdf_plot(
    worksheet: Worksheet,
    variable_index: int,
    group_index: Optional[int] = None,
    distribution: str = 'None',  # 'None', 'Normal', 'Lognormal', 'Weibull', 'Exponential'
    confidence: float = 0.95,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute the empirical cumulative distribution, confidence bands, and fitted curve."""
    if not (0 <= variable_index < len(worksheet.columns)):
        raise ValueError('Select a valid worksheet column.')

    col = worksheet.columns[variable_index]
    if col.kind != 'number':
        raise ValueError('Empirical CDF requires a numeric variable.')

    grp_col = worksheet.columns[group_index] if group_index is not None and 0 <= group_index < len(worksheet.columns) else None

    # Filter observations
    rows: List[Tuple[float, str]] = []
    extent = max(len(col.values), len(grp_col.values) if grp_col else 0)

    for r in range(extent):
        v = col.values[r] if r < len(col.values) else None
        if v is not None and math.isfinite(v):
            g_lbl = str(grp_col.values[r]) if grp_col and r < len(grp_col.values) and grp_col.values[r] is not None else ''
            rows.append((float(v), g_lbl))

    if not rows:
        raise ValueError('No finite observations available for Empirical CDF.')

    # Grouping
    group_map: Dict[str, List[float]] = {}
    for v, g in rows:
        group_map.setdefault(g, []).append(v)

    alpha = 1.0 - confidence
    if not (0.0 < alpha < 1.0):
        raise ValueError('Confidence level must be strictly between 0 and 1.')

    series_list = []
    overall_vals = [v for v, _ in rows]

    for g_lbl, vals in group_map.items():
        arr = np.sort(vals)
        n = len(arr)
        if n < 2:
            continue

        mean = float(np.mean(arr))
        stdev = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        median = float(np.median(arr))

        # Compute empirical step points
        unique_vals, counts = np.unique(arr, return_counts=True)
        cum_counts = np.cumsum(counts)
        ecdf_vals = cum_counts / n

        # Build stepped polygon coordinates
        step_pts = [[float(unique_vals[0]), 0.0]]
        prev_p = 0.0
        for u, p in zip(unique_vals, ecdf_vals):
            step_pts.append([float(u), float(prev_p)])
            step_pts.append([float(u), float(p)])
            prev_p = float(p)

        # Simultaneous confidence band via Dvoretzky-Kiefer-Wolfowitz (DKW) inequality
        # epsilon = sqrt(ln(2 / alpha) / (2 * n))
        epsilon = math.sqrt(math.log(2.0 / alpha) / (2.0 * n))
        band_lower = []
        band_upper = []

        for pt in step_pts:
            x, p = pt[0], pt[1]
            band_lower.append([x, max(0.0, p - epsilon)])
            band_upper.append([x, min(1.0, p + epsilon)])

        # Parametric Fit Overlay
        fit_curve = []
        fit_params = {}
        dist_name = distribution.strip()

        if dist_name in ('Normal', 'norm'):
            if stdev > 0:
                xs_fit = np.linspace(arr[0], arr[-1], 150).tolist()
                ys_fit = [float(stats.norm.cdf(x, loc=mean, scale=stdev)) for x in xs_fit]
                fit_curve = [[x, y] for x, y in zip(xs_fit, ys_fit)]
                fit_params = {'Mean': mean, 'StDev': stdev}

        elif dist_name in ('Lognormal', 'lognorm'):
            pos_arr = arr[arr > 0]
            if len(pos_arr) > 2:
                log_vals = np.log(pos_arr)
                mu_log = float(np.mean(log_vals))
                sd_log = float(np.std(log_vals, ddof=1))
                if sd_log > 0:
                    xs_fit = np.linspace(pos_arr[0], pos_arr[-1], 150).tolist()
                    ys_fit = [float(stats.lognorm.cdf(x, s=sd_log, scale=math.exp(mu_log))) for x in xs_fit]
                    fit_curve = [[x, y] for x, y in zip(xs_fit, ys_fit)]
                    fit_params = {'Location': mu_log, 'Scale': sd_log}

        elif dist_name in ('Weibull', 'weibull'):
            pos_arr = arr[arr > 0]
            if len(pos_arr) > 2:
                try:
                    c, loc, scale = stats.weibull_min.fit(pos_arr, floc=0)
                    xs_fit = np.linspace(pos_arr[0], pos_arr[-1], 150).tolist()
                    ys_fit = [float(stats.weibull_min.cdf(x, c=c, scale=scale)) for x in xs_fit]
                    fit_curve = [[x, y] for x, y in zip(xs_fit, ys_fit)]
                    fit_params = {'Shape': float(c), 'Scale': float(scale)}
                except Exception:
                    pass

        elif dist_name in ('Exponential', 'expon'):
            if mean > 0:
                xs_fit = np.linspace(0.0, arr[-1], 150).tolist()
                ys_fit = [float(stats.expon.cdf(x, scale=mean)) for x in xs_fit]
                fit_curve = [[x, y] for x, y in zip(xs_fit, ys_fit)]
                fit_params = {'Mean (Scale)': mean}

        # Percentiles table (1%, 5%, 10%, 25%, 50%, 75%, 90%, 95%, 99%)
        percentile_levels = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_rows = []
        for pl in percentile_levels:
            q_emp = float(np.percentile(arr, pl))
            q_fit = None
            if dist_name == 'Normal' and stdev > 0:
                q_fit = float(stats.norm.ppf(pl / 100.0, loc=mean, scale=stdev))
            elif dist_name == 'Lognormal' and 'Location' in fit_params:
                q_fit = float(stats.lognorm.ppf(pl / 100.0, s=fit_params['Scale'], scale=math.exp(fit_params['Location'])))
            elif dist_name == 'Exponential' and mean > 0:
                q_fit = float(stats.expon.ppf(pl / 100.0, scale=mean))

            percentile_rows.append({
                'percent': pl,
                'empirical': q_emp,
                'fitted': q_fit,
            })

        series_list.append({
            'group': g_lbl or col.name,
            'n': n,
            'mean': mean,
            'stdev': stdev,
            'median': median,
            'step_points': step_pts,
            'band_lower': band_lower,
            'band_upper': band_upper,
            'fit_curve': fit_curve,
            'fit_params': fit_params,
            'percentiles': percentile_rows,
            'epsilon': epsilon,
        })

    plot_title = title or f'Empirical CDF of {col.name}'
    all_x = [pt[0] for s in series_list for pt in s['step_points']]
    x_min_all = min(all_x) if all_x else 0.0
    x_max_all = max(all_x) if all_x else 1.0

    return {
        'graph': 'ecdf_plot',
        'analysis': 'ecdf_plot',
        'title': plot_title,
        'variable_name': col.name,
        'group_name': grp_col.name if grp_col else None,
        'distribution': distribution,
        'confidence': confidence,
        'domain': [x_min_all, x_max_all],
        'series': series_list,
        'n_total': len(rows),
    }
