"""Statistical engine for standalone ANOVA plots: Main Effects Plots and Interactions Plots.

Minitab 22 compliant calculations:
- Main Effects: Data means across factor levels, overall grand mean, sample sizes, standard deviations.
- Interactions: Cell means matrix, factor level combinations, row/column marginals.
"""
from __future__ import annotations

import math
from typing import Any, List, Optional, Sequence, Union


def compute_main_effects(
    responses: Sequence[Any],
    factors_data: Sequence[Sequence[Any]],
    response_name: str = "Response",
    factor_names: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Compute main effects statistics across multiple factors.
    
    Parameters
    ----------
    responses : Sequence of response values (numeric)
    factors_data : List/tuple of factor column sequences (numeric or text)
    response_name : Display name of response variable
    factor_names : Display names of factor variables
    
    Returns
    -------
    dict with overall grand mean, per-factor level means, sample sizes, and SDs.
    """
    n_factors = len(factors_data)
    if n_factors == 0:
        raise ValueError("Main Effects Plot requires at least one factor.")
    
    if factor_names is None:
        factor_names = [f"Factor {i + 1}" for i in range(n_factors)]
    elif len(factor_names) != n_factors:
        raise ValueError("Length of factor_names must match number of factor columns.")

    n_rows = len(responses)
    for i, col in enumerate(factors_data):
        if len(col) != n_rows:
            raise ValueError(f"Factor '{factor_names[i]}' length ({len(col)}) does not match response length ({n_rows}).")

    # Filter complete observations
    valid_y: list[float] = []
    valid_factors: list[list[str]] = [[] for _ in range(n_factors)]

    for row_idx in range(n_rows):
        y_val = responses[row_idx]
        if y_val is None:
            continue
        try:
            y_float = float(y_val)
            if math.isnan(y_float) or math.isinf(y_float):
                continue
        except (ValueError, TypeError):
            continue

        # Check factor values
        row_factors = []
        valid_row = True
        for col in factors_data:
            f_val = col[row_idx]
            if f_val is None or (isinstance(f_val, str) and not f_val.strip()):
                valid_row = False
                break
            row_factors.append(str(f_val).strip())

        if valid_row:
            valid_y.append(y_float)
            for f_i, f_val in enumerate(row_factors):
                valid_factors[f_i].append(f_val)

    n_valid = len(valid_y)
    if n_valid < 2:
        raise ValueError("Main Effects Plot requires at least 2 complete observations.")

    grand_mean = sum(valid_y) / n_valid

    factor_summaries: list[dict[str, Any]] = []
    for f_i in range(n_factors):
        f_name = factor_names[f_i]
        vals = valid_factors[f_i]

        # Group responses by factor level
        level_groups: dict[str, list[float]] = {}
        for y, lvl in zip(valid_y, vals):
            level_groups.setdefault(lvl, []).append(y)

        # Sort levels naturally
        def _sort_key(lvl_str: str):
            try:
                return (0, float(lvl_str))
            except ValueError:
                return (1, lvl_str)

        sorted_levels = sorted(level_groups.keys(), key=_sort_key)
        level_stats: list[dict[str, Any]] = []

        for lvl in sorted_levels:
            ys = level_groups[lvl]
            cnt = len(ys)
            mean_val = sum(ys) / cnt
            if cnt > 1:
                variance = sum((v - mean_val) ** 2 for v in ys) / (cnt - 1)
                stdev = math.sqrt(variance)
            else:
                stdev = 0.0

            level_stats.append({
                "level": lvl,
                "count": cnt,
                "mean": mean_val,
                "stdev": stdev
            })

        factor_summaries.append({
            "factor_name": f_name,
            "levels": sorted_levels,
            "level_stats": level_stats,
            "min_mean": min(s["mean"] for s in level_stats),
            "max_mean": max(s["mean"] for s in level_stats)
        })

    return {
        "analysis": "main_effects_plot",
        "response_name": response_name,
        "count": n_valid,
        "grand_mean": grand_mean,
        "factor_summaries": factor_summaries
    }


def compute_interactions(
    responses: Sequence[Any],
    factor_a_vals: Sequence[Any],
    factor_b_vals: Sequence[Any],
    response_name: str = "Response",
    factor_a_name: str = "Factor A",
    factor_b_name: str = "Factor B",
) -> dict[str, Any]:
    """Compute interaction statistics between two factors.
    
    Parameters
    ----------
    responses : Numeric response values
    factor_a_vals : Factor A values (horizontal axis)
    factor_b_vals : Factor B values (separate curves/series)
    response_name : Display name of response
    factor_a_name : Display name of Factor A
    factor_b_name : Display name of Factor B
    
    Returns
    -------
    dict with cell means, counts, marginals, and grand mean.
    """
    n_rows = len(responses)
    if len(factor_a_vals) != n_rows or len(factor_b_vals) != n_rows:
        raise ValueError("Responses and factor columns must have identical lengths.")

    valid_y: list[float] = []
    valid_a: list[str] = []
    valid_b: list[str] = []

    for i in range(n_rows):
        y_raw = responses[i]
        fa_raw = factor_a_vals[i]
        fb_raw = factor_b_vals[i]

        if y_raw is None or fa_raw is None or fb_raw is None:
            continue
        try:
            y_float = float(y_raw)
            if math.isnan(y_float) or math.isinf(y_float):
                continue
        except (ValueError, TypeError):
            continue

        fa_str = str(fa_raw).strip()
        fb_str = str(fb_raw).strip()
        if not fa_str or not fb_str:
            continue

        valid_y.append(y_float)
        valid_a.append(fa_str)
        valid_b.append(fb_str)

    n_valid = len(valid_y)
    if n_valid < 2:
        raise ValueError("Interactions Plot requires at least 2 complete observations.")

    grand_mean = sum(valid_y) / n_valid

    def _sort_key(s: str):
        try:
            return (0, float(s))
        except ValueError:
            return (1, s)

    levels_a = sorted(list(set(valid_a)), key=_sort_key)
    levels_b = sorted(list(set(valid_b)), key=_sort_key)

    # Cell statistics: (a, b) -> [values]
    cell_groups: dict[tuple[str, str], list[float]] = {}
    for y, a, b in zip(valid_y, valid_a, valid_b):
        cell_groups.setdefault((a, b), []).append(y)

    cell_stats: dict[str, dict[str, dict[str, Any]]] = {}
    curves: list[dict[str, Any]] = []

    all_means: list[float] = []

    for b in levels_b:
        curve_points: list[dict[str, Any]] = []
        for a in levels_a:
            vals = cell_groups.get((a, b), [])
            cnt = len(vals)
            if cnt > 0:
                mean_val = sum(vals) / cnt
                all_means.append(mean_val)
            else:
                mean_val = None

            cell_stats.setdefault(a, {})[b] = {
                "count": cnt,
                "mean": mean_val
            }
            curve_points.append({
                "factor_a_level": a,
                "mean": mean_val,
                "count": cnt
            })

        curves.append({
            "factor_b_level": b,
            "points": curve_points
        })

    # Marginals for Factor A
    a_stats: list[dict[str, Any]] = []
    for a in levels_a:
        vals = [y for y, fa in zip(valid_y, valid_a) if fa == a]
        cnt = len(vals)
        mean_val = sum(vals) / cnt if cnt > 0 else 0.0
        a_stats.append({"level": a, "count": cnt, "mean": mean_val})

    # Marginals for Factor B
    b_stats: list[dict[str, Any]] = []
    for b in levels_b:
        vals = [y for y, fb in zip(valid_y, valid_b) if fb == b]
        cnt = len(vals)
        mean_val = sum(vals) / cnt if cnt > 0 else 0.0
        b_stats.append({"level": b, "count": cnt, "mean": mean_val})

    return {
        "analysis": "interactions_plot",
        "response_name": response_name,
        "factor_a_name": factor_a_name,
        "factor_b_name": factor_b_name,
        "count": n_valid,
        "grand_mean": grand_mean,
        "levels_a": levels_a,
        "levels_b": levels_b,
        "cell_stats": cell_stats,
        "curves": curves,
        "marginal_a": a_stats,
        "marginal_b": b_stats,
        "min_mean": min(all_means) if all_means else grand_mean,
        "max_mean": max(all_means) if all_means else grand_mean
    }
