"""Symmetry Plot Computational Engine.

Minitab Standard Symmetry Plot:
- Evaluates whether continuous sample data come from a symmetric distribution.
- Computes distances from sample median for observations below the median vs above the median.
- Plots Lower Distance (X) vs Upper Distance (Y).
- Draws 45-degree reference line (Y = X) representing theoretical symmetry.
- Calculates sample size, median, mean, standard deviation, and sample skewness.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Union


DEFAULT_SETTINGS = {
    "show_line": True,         # Show 45-degree reference line Y = X
    "title": "",               # Custom plot title
    "subtitle": "",            # Custom plot subtitle
    "footnote": "",            # Custom plot footnote
}


def compute_symmetry_plot(
    values: Sequence[Union[float, int, None]],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute complete Symmetry Plot statistics and point coordinates."""
    opts = dict(DEFAULT_SETTINGS)
    if settings:
        opts.update(settings)

    # Filter valid finite numeric observations
    valid_vals: List[float] = []
    n_missing = 0
    for v in values:
        if v is None:
            n_missing += 1
            continue
        try:
            fv = float(v)
            if math.isfinite(fv):
                valid_vals.append(fv)
            else:
                n_missing += 1
        except (ValueError, TypeError):
            n_missing += 1

    n = len(valid_vals)
    if n < 4:
        raise ValueError("Symmetry Plot requires at least 4 valid numeric observations.")

    # Sort in ascending order
    sorted_vals = sorted(valid_vals)

    # Calculate median
    k = n // 2
    if n % 2 == 1:
        median = sorted_vals[k]
    else:
        median = (sorted_vals[k - 1] + sorted_vals[k]) / 2.0

    # Summary statistics
    mean_val = sum(sorted_vals) / n
    variance = sum((x - mean_val) ** 2 for x in sorted_vals) / (n - 1) if n > 1 else 0.0
    stdev = math.sqrt(variance)

    # Fisher-Pearson unbiased sample skewness
    if stdev > 1e-12 and n >= 3:
        m3 = sum((x - mean_val) ** 3 for x in sorted_vals) / n
        m2 = sum((x - mean_val) ** 2 for x in sorted_vals) / n
        skewness = (math.sqrt(n * (n - 1)) / (n - 2)) * (m3 / (m2 ** 1.5))
    else:
        skewness = 0.0

    # Compute distances from median for pairs (i=1..k)
    # Lower distance u_i = median - x_(i)
    # Upper distance v_i = x_(n - i + 1) - median
    points_table: List[Dict[str, Any]] = []
    lower_distances: List[float] = []
    upper_distances: List[float] = []
    discrepancies: List[float] = []

    for idx in range(k):
        rank = idx + 1
        x_low = sorted_vals[idx]
        x_high = sorted_vals[n - 1 - idx]

        u_dist = median - x_low
        v_dist = x_high - median
        diff = v_dist - u_dist

        points_table.append({
            "rank": rank,
            "lower_obs": x_low,
            "upper_obs": x_high,
            "lower_dist": u_dist,
            "upper_dist": v_dist,
            "discrepancy": diff,
        })
        lower_distances.append(u_dist)
        upper_distances.append(v_dist)
        discrepancies.append(diff)

    max_dist = max(max(lower_distances), max(upper_distances))
    if max_dist <= 1e-9:
        max_dist = 1.0

    # Symmetry assessment description
    if abs(skewness) < 0.2:
        assessment = "Points fall close to the 45° line: distribution is approximately symmetric."
        skew_label = "Symmetric"
    elif skewness >= 0.2:
        assessment = "Points fall predominantly above the 45° line: distribution is skewed right (positive skewness)."
        skew_label = "Skewed Right"
    else:
        assessment = "Points fall predominantly below the 45° line: distribution is skewed left (negative skewness)."
        skew_label = "Skewed Left"

    plot_data = {
        "lower_distances": lower_distances,
        "upper_distances": upper_distances,
        "ranks": list(range(1, k + 1)),
        "max_dist": max_dist,
        "show_line": opts.get("show_line", True),
        "median": median,
        "mean": mean_val,
        "stdev": stdev,
        "skewness": skewness,
    }

    return {
        "n": n,
        "n_missing": n_missing,
        "k_pairs": k,
        "median": median,
        "mean": mean_val,
        "stdev": stdev,
        "skewness": skewness,
        "skew_label": skew_label,
        "assessment": assessment,
        "points_table": points_table,
        "plot_data": plot_data,
        "settings": opts,
    }
