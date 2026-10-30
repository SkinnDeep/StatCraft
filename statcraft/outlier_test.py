"""Grubbs' Test for Outliers (Single Outlier Detection).

Tests whether the most extreme value (smallest or largest) is a statistical outlier
from a normal distribution.
"""
from __future__ import annotations

import math
import statistics
from scipy import stats
from .engine import normalize_numeric


def grubbs_test(values: list, alpha: float = 0.05, alternative: str = 'two-sided') -> dict:
    clean = []
    orig_indices = []
    for idx, v in enumerate(values):
        norm = normalize_numeric(v)
        if norm is not None:
            clean.append(float(norm))
            orig_indices.append(idx + 1)

    n = len(clean)
    if n < 3:
        raise ValueError("Outlier Test requires at least 3 nonmissing observations.")

    mean_val = statistics.fmean(clean)
    stdev_val = statistics.stdev(clean)
    if stdev_val <= 0:
        raise ValueError("All values are identical; standard deviation is zero.")

    min_val = min(clean)
    max_val = max(clean)
    min_idx = clean.index(min_val)
    max_idx = clean.index(max_val)

    dev_min = abs(mean_val - min_val)
    dev_max = abs(max_val - mean_val)

    if alternative == 'min':
        g_stat = (mean_val - min_val) / stdev_val
        outlier_val = min_val
        outlier_row = orig_indices[min_idx]
        outlier_type = "Low"
    elif alternative == 'max':
        g_stat = (max_val - mean_val) / stdev_val
        outlier_val = max_val
        outlier_row = orig_indices[max_idx]
        outlier_type = "High"
    else:  # two-sided
        if dev_max >= dev_min:
            g_stat = dev_max / stdev_val
            outlier_val = max_val
            outlier_row = orig_indices[max_idx]
            outlier_type = "High"
        else:
            g_stat = dev_min / stdev_val
            outlier_val = min_val
            outlier_row = orig_indices[min_idx]
            outlier_type = "Low"

    # Compute critical value and p-value using t-distribution
    df = n - 2
    if alternative == 'two-sided':
        t_crit_p = alpha / (2.0 * n)
    else:
        t_crit_p = alpha / n

    t_crit = stats.t.ppf(1.0 - t_crit_p, df)
    g_crit = ((n - 1) / math.sqrt(n)) * math.sqrt(t_crit ** 2 / (df + t_crit ** 2))

    # Exact p-value calculation
    denom = (n - 1) ** 2 - n * (g_stat ** 2)
    if denom <= 0:
        p_val = 0.0
    else:
        t_val = math.sqrt(max(0.0, (n * df * (g_stat ** 2)) / denom))
        sf = stats.t.sf(t_val, df)
        mult = (2.0 * n) if alternative == 'two-sided' else float(n)
        p_val = min(1.0, max(0.0, mult * sf))

    is_outlier = g_stat > g_crit or p_val < alpha

    return {
        'analysis': 'outlier_test',
        'n': n,
        'mean': mean_val,
        'stdev': stdev_val,
        'min': min_val,
        'max': max_val,
        'g_stat': g_stat,
        'g_crit': g_crit,
        'p_value': p_val,
        'alpha': alpha,
        'alternative': alternative,
        'is_outlier': is_outlier,
        'outlier_value': outlier_val,
        'outlier_row': outlier_row,
        'outlier_type': outlier_type,
        'values': clean,
        'rows': orig_indices,
    }
