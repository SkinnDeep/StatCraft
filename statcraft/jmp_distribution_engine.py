"""Computation engine for JMP Distribution platform (Univariate analysis).

Computes Quantiles, Summary Statistics (Mean, Std Dev, Std Err Mean, 95% Confidence Intervals,
Skewness, Kurtosis, CV), Outlier Box Plot metrics, Histogram frequencies, Normal distribution fit,
and Categorical Frequencies matching JMP specifications.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np
import scipy.stats as stats

from .model import Worksheet, Column


def compute_continuous_distribution(col: Column, conf: float = 0.95) -> Dict[str, Any]:
    """Compute comprehensive distribution metrics for a continuous numeric variable."""
    # Filter valid numeric values
    raw_vals = [float(v) for v in col.values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    arr = np.array(raw_vals, dtype=float)
    n = len(arr)

    if n == 0:
        raise ValueError(f"Column '{col.name}' contains no valid numeric data.")

    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    stderr_val = std_val / math.sqrt(n) if n > 0 else 0.0

    # Student-t critical value for confidence intervals
    if n > 1:
        alpha = 1.0 - conf
        t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=n - 1))
        ci_lower = mean_val - t_crit * stderr_val
        ci_upper = mean_val + t_crit * stderr_val
    else:
        ci_lower = mean_val
        ci_upper = mean_val

    sum_val = float(np.sum(arr))
    var_val = float(np.var(arr, ddof=1)) if n > 1 else 0.0

    # Skewness and Kurtosis (unbiased)
    skew_val = float(stats.skew(arr, bias=False)) if n > 2 and std_val > 1e-12 else 0.0
    kurt_val = float(stats.kurtosis(arr, bias=False)) if n > 3 and std_val > 1e-12 else 0.0
    cv_val = (100.0 * std_val / mean_val) if abs(mean_val) > 1e-12 else 0.0

    # Exact JMP 11 Quantiles
    # 100.0% max, 99.5%, 97.5%, 90.0%, 75.0% Q3, 50.0% median, 25.0% Q1, 10.0%, 2.5%, 0.5%, 0.0% min
    quantile_levels = [1.0, 0.995, 0.975, 0.90, 0.75, 0.50, 0.25, 0.10, 0.025, 0.005, 0.0]
    quantiles = {}
    for q in quantile_levels:
        quantiles[f"{q*100:.1f}%"] = float(np.percentile(arr, q * 100))

    q25 = quantiles["25.0%"]
    median_val = quantiles["50.0%"]
    q75 = quantiles["75.0%"]
    iqr = q75 - q25

    # Outlier Box Plot metrics
    lower_fence = q25 - 1.5 * iqr
    upper_fence = q75 + 1.5 * iqr
    in_fence = arr[(arr >= lower_fence) & (arr <= upper_fence)]
    lower_whisker = float(np.min(in_fence)) if len(in_fence) > 0 else float(np.min(arr))
    upper_whisker = float(np.max(in_fence)) if len(in_fence) > 0 else float(np.max(arr))
    outliers = [float(x) for x in arr if x < lower_fence or x > upper_fence]

    # Extreme Observations (Lowest 5 and Highest 5 with row indices)
    indexed_vals = sorted(enumerate(arr), key=lambda x: x[1])
    lowest_5 = [{"row": idx + 1, "value": float(val)} for idx, val in indexed_vals[:5]]
    highest_5 = [{"row": idx + 1, "value": float(val)} for idx, val in indexed_vals[-5:][::-1]]

    # Histogram binning (Freedman-Diaconis rule with min 5, max 40 bins)
    min_v = float(np.min(arr))
    max_v = float(np.max(arr))
    if min_v == max_v:
        num_bins = 1
        bin_edges = [min_v - 0.5, max_v + 0.5]
    else:
        h = 2.0 * iqr * (n ** (-1.0 / 3.0)) if iqr > 1e-9 else 0.0
        if h > 1e-9:
            num_bins = max(5, min(40, int(math.ceil((max_v - min_v) / h))))
        else:
            num_bins = max(5, min(25, int(math.ceil(math.sqrt(n)))))
        bin_counts, bin_edges = np.histogram(arr, bins=num_bins)
        bin_counts = [int(c) for c in bin_counts]
        bin_edges = [float(e) for e in bin_edges]

    # Fitted Normal Curve points
    curve_x = []
    curve_y = []
    if std_val > 1e-12:
        xs = np.linspace(min_v, max_v, 80)
        bin_w = (max_v - min_v) / num_bins if num_bins > 1 else 1.0
        ys = stats.norm.pdf(xs, loc=mean_val, scale=std_val) * n * bin_w
        curve_x = [float(x) for x in xs]
        curve_y = [float(y) for y in ys]

    return {
        "variable": col.name,
        "type": "continuous",
        "modeling_type": "continuous",
        "n": n,
        "mean": mean_val,
        "std_dev": std_val,
        "std_err": stderr_val,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "sum": sum_val,
        "variance": var_val,
        "skewness": skew_val,
        "kurtosis": kurt_val,
        "cv": cv_val,
        "quantiles": quantiles,
        "q25": q25,
        "median": median_val,
        "q75": q75,
        "iqr": iqr,
        "lower_whisker": lower_whisker,
        "upper_whisker": upper_whisker,
        "outliers": outliers,
        "lowest_5": lowest_5,
        "highest_5": highest_5,
        "bin_counts": bin_counts,
        "bin_edges": bin_edges,
        "curve_x": curve_x,
        "curve_y": curve_y,
    }


def compute_categorical_distribution(col: Column) -> Dict[str, Any]:
    """Compute frequencies, probabilities, and cumulative proportions for nominal/ordinal data."""
    # Count frequencies of non-null levels
    counts: Dict[str, int] = {}
    total_valid = 0
    for v in col.values:
        if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "":
            continue
        s_val = str(v).strip()
        counts[s_val] = counts.get(s_val, 0) + 1
        total_valid += 1

    if total_valid == 0:
        raise ValueError(f"Column '{col.name}' contains no valid categorical observations.")

    # Sort levels by frequency descending
    sorted_levels = sorted(counts.items(), key=lambda x: (-x[1], x[0]))

    freq_rows = []
    cum_count = 0
    cum_prob = 0.0
    for level, count in sorted_levels:
        prob = count / total_valid
        std_err = math.sqrt(prob * (1.0 - prob) / total_valid) if total_valid > 1 else 0.0
        cum_count += count
        cum_prob += prob
        freq_rows.append({
            "level": level,
            "count": count,
            "prob": prob,
            "std_err": std_err,
            "cum_count": cum_count,
            "cum_prob": min(1.0, cum_prob)
        })

    return {
        "variable": col.name,
        "type": "categorical",
        "modeling_type": col.metadata.get("modeling_type", "nominal"),
        "n": total_valid,
        "num_levels": len(freq_rows),
        "frequencies": freq_rows
    }


def compute_jmp_distribution(
    worksheet: Worksheet,
    column_indices: List[int],
    confidence: float = 0.95
) -> Dict[str, Any]:
    """Execute JMP Distribution platform across selected columns."""
    if not column_indices:
        raise ValueError("Please select at least one column to analyze.")

    variables_result = []
    for idx in column_indices:
        if idx >= len(worksheet.columns):
            continue
        col = worksheet.columns[idx]
        mt = col.metadata.get("modeling_type")
        is_cat = (mt in ("nominal", "ordinal")) or (col.kind == "text")

        if is_cat:
            res = compute_categorical_distribution(col)
        else:
            try:
                res = compute_continuous_distribution(col, conf=confidence)
            except Exception:
                # Fallback to categorical if non-numeric
                res = compute_categorical_distribution(col)

        variables_result.append(res)

    col_names = [worksheet.columns[i].name for i in column_indices if i < len(worksheet.columns)]
    title = f"Distributions: {', '.join(col_names[:3])}" + ("..." if len(col_names) > 3 else "")

    return {
        "analysis": "jmp_distribution",
        "platform": "distribution",
        "title": title,
        "confidence": confidence,
        "variables": variables_result,
        "sheet_name": worksheet.name
    }
