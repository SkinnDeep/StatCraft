"""Quality Run Chart & Tests for Randomness.

Computes runs about the median (clustering & mixtures) and runs up/down (trends & oscillation).
"""
from __future__ import annotations

import math
import statistics
from scipy import stats
from .engine import normalize_numeric


def run_chart(values: list, subgroup_size: int = 1) -> dict:
    clean = [float(v) for v in (normalize_numeric(x) for x in values) if v is not None]
    n_raw = len(clean)
    if n_raw < 4:
        raise ValueError("Run Chart requires at least 4 nonmissing observations.")

    if subgroup_size < 1:
        subgroup_size = 1

    # Form subgroups
    if subgroup_size > 1:
        points = []
        for i in range(0, n_raw - subgroup_size + 1, subgroup_size):
            chunk = clean[i:i + subgroup_size]
            points.append(statistics.fmean(chunk))
    else:
        points = clean

    n = len(points)
    if n < 4:
        raise ValueError("Run Chart requires at least 4 subgroups/points.")

    # Center line is Median
    median_val = statistics.median(points)

    # 1. Runs about median
    # Classify points as >= median (1) or < median (0)
    # Ignore points exactly equal to median if alternating or classify strictly
    diffs = [p - median_val for p in points]
    signs_median = [1 if d >= 0 else -1 for d in diffs]
    n1 = sum(1 for s in signs_median if s == 1)
    n2 = sum(1 for s in signs_median if s == -1)

    runs_median = 1
    longest_median = 1
    current_run = 1
    for i in range(1, n):
        if signs_median[i] == signs_median[i - 1]:
            current_run += 1
            if current_run > longest_median:
                longest_median = current_run
        else:
            runs_median += 1
            current_run = 1

    # Expected runs and variance for runs about median
    if n > 1 and n1 > 0 and n2 > 0:
        exp_runs_median = 1.0 + (2.0 * n1 * n2) / n
        denom = (n ** 2) * (n - 1)
        var_runs_median = (2.0 * n1 * n2 * (2.0 * n1 * n2 - n)) / denom if denom > 0 else 0.0
        sd_runs_median = math.sqrt(max(0.0, var_runs_median))

        if sd_runs_median > 0:
            # Cluster p-value: P(Runs <= r)
            z_cluster = (runs_median - exp_runs_median + 0.5) / sd_runs_median
            p_cluster = float(stats.norm.cdf(z_cluster))

            # Mixture p-value: P(Runs >= r)
            z_mixture = (runs_median - exp_runs_median - 0.5) / sd_runs_median
            p_mixture = float(1.0 - stats.norm.cdf(z_mixture))
        else:
            p_cluster = 0.5
            p_mixture = 0.5
    else:
        exp_runs_median = 1.0
        p_cluster = 0.5
        p_mixture = 0.5

    # 2. Runs up or down
    # Compute successive differences
    diffs_ud = []
    for i in range(1, n):
        d = points[i] - points[i - 1]
        if d > 0:
            diffs_ud.append(1)
        elif d < 0:
            diffs_ud.append(-1)
        else:
            # Zero diff inherits previous sign or 1
            diffs_ud.append(diffs_ud[-1] if diffs_ud else 1)

    runs_ud = 1
    longest_ud = 1
    current_ud = 1
    for i in range(1, len(diffs_ud)):
        if diffs_ud[i] == diffs_ud[i - 1]:
            current_ud += 1
            if current_ud > longest_ud:
                longest_ud = current_ud
        else:
            runs_ud += 1
            current_ud = 1

    # Expected runs and variance for runs up/down
    exp_runs_ud = (2.0 * n - 1.0) / 3.0
    var_runs_ud = (16.0 * n - 29.0) / 90.0 if n >= 2 else 1.0
    sd_runs_ud = math.sqrt(max(0.0, var_runs_ud))

    if sd_runs_ud > 0:
        # Trend p-value: P(Runs <= r)
        z_trend = (runs_ud - exp_runs_ud + 0.5) / sd_runs_ud
        p_trend = float(stats.norm.cdf(z_trend))

        # Oscillation p-value: P(Runs >= r)
        z_osc = (runs_ud - exp_runs_ud - 0.5) / sd_runs_ud
        p_osc = float(1.0 - stats.norm.cdf(z_osc))
    else:
        p_trend = 0.5
        p_osc = 0.5

    return {
        'n': n,
        'n_raw': n_raw,
        'subgroup_size': subgroup_size,
        'points': points,
        'median': median_val,
        'runs_about_median': {
            'number_of_runs': runs_median,
            'expected_runs': exp_runs_median,
            'longest_run': longest_median,
            'p_cluster': min(1.0, max(0.0, p_cluster)),
            'p_mixture': min(1.0, max(0.0, p_mixture)),
        },
        'runs_up_or_down': {
            'number_of_runs': runs_ud,
            'expected_runs': exp_runs_ud,
            'longest_run': longest_ud,
            'p_trend': min(1.0, max(0.0, p_trend)),
            'p_oscillation': min(1.0, max(0.0, p_osc)),
        },
    }
