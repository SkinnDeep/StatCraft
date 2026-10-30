"""Computational engine for Two-Way Analysis of Variance (ANOVA).

Supports balanced and unbalanced two-factor designs, testing main effects
and factor interactions, model diagnostics, and cell means tables.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np
from scipy import stats

from .engine import normalize_numeric


def compute_twoway_anova(
    responses: list[Any],
    factor_a_vals: list[Any],
    factor_b_vals: list[Any],
    response_name: str = "Response",
    factor_a_name: str = "Factor A",
    factor_b_name: str = "Factor B",
    fit_interaction: bool = True,
    display_means: bool = True,
    confidence: float = 0.95
) -> dict[str, Any]:
    """Compute Two-Way ANOVA with main effects and optional interaction."""
    # 1. Clean and align complete triples
    n_raw = min(len(responses), len(factor_a_vals), len(factor_b_vals))
    clean_y = []
    clean_a = []
    clean_b = []
    missing_count = 0

    for i in range(n_raw):
        y_val = normalize_numeric(responses[i])
        a_val = factor_a_vals[i]
        b_val = factor_b_vals[i]

        if y_val is None or a_val is None or b_val is None:
            missing_count += 1
            continue
        a_str = str(a_val).strip()
        b_str = str(b_val).strip()
        if not a_str or not b_str:
            missing_count += 1
            continue

        clean_y.append(float(y_val))
        clean_a.append(a_str)
        clean_b.append(b_str)

    n_total = len(clean_y)
    if n_total < 3:
        raise ValueError("Two-Way ANOVA requires at least 3 valid observations.")

    # 2. Identify factor levels
    levels_a = sorted(list(set(clean_a)))
    levels_b = sorted(list(set(clean_b)))
    k_a = len(levels_a)
    k_b = len(levels_b)

    if k_a < 2 or k_b < 2:
        raise ValueError("Both factors must have at least 2 distinct levels.")

    # 3. Compute cell collections
    cells: dict[tuple[str, str], list[float]] = {}
    for a in levels_a:
        for b in levels_b:
            cells[(a, b)] = []

    for y, a, b in zip(clean_y, clean_a, clean_b):
        cells[(a, b)].append(y)

    grand_mean = float(np.mean(clean_y))
    ss_total = float(np.sum((np.array(clean_y) - grand_mean) ** 2))
    df_total = n_total - 1

    # Marginal computations for Factor A
    a_groups: dict[str, list[float]] = {a: [] for a in levels_a}
    for y, a in zip(clean_y, clean_a):
        a_groups[a].append(y)

    ss_a = 0.0
    a_stats = []
    for a in levels_a:
        vals = a_groups[a]
        cnt = len(vals)
        m = float(np.mean(vals)) if cnt > 0 else grand_mean
        s = float(np.std(vals, ddof=1)) if cnt > 1 else 0.0
        ss_a += cnt * (m - grand_mean) ** 2
        a_stats.append({
            "level": a,
            "count": cnt,
            "mean": m,
            "stdev": s
        })
    df_a = k_a - 1

    # Marginal computations for Factor B
    b_groups: dict[str, list[float]] = {b: [] for b in levels_b}
    for y, b in zip(clean_y, clean_b):
        b_groups[b].append(y)

    ss_b = 0.0
    b_stats = []
    for b in levels_b:
        vals = b_groups[b]
        cnt = len(vals)
        m = float(np.mean(vals)) if cnt > 0 else grand_mean
        s = float(np.std(vals, ddof=1)) if cnt > 1 else 0.0
        ss_b += cnt * (m - grand_mean) ** 2
        b_stats.append({
            "level": b,
            "count": cnt,
            "mean": m,
            "stdev": s
        })
    df_b = k_b - 1

    # Interaction & Error SS
    ss_cells = 0.0
    cell_stats = []
    for a in levels_a:
        row = []
        for b in levels_b:
            c_vals = cells[(a, b)]
            cnt = len(c_vals)
            m = float(np.mean(c_vals)) if cnt > 0 else grand_mean
            s = float(np.std(c_vals, ddof=1)) if cnt > 1 else 0.0
            if cnt > 0:
                ss_cells += cnt * (m - grand_mean) ** 2
            row.append({
                "factor_a": a,
                "factor_b": b,
                "count": cnt,
                "mean": m,
                "stdev": s
            })
        cell_stats.append(row)

    if fit_interaction:
        df_ab = df_a * df_b
        df_error = n_total - (k_a * k_b)
        if df_error <= 0:
            # Replicate-free single observation per cell -> default to additive
            fit_interaction = False
            df_ab = 0
            ss_ab = 0.0
            df_error = n_total - df_a - df_b - 1
            ss_error = max(0.0, ss_total - ss_a - ss_b)
        else:
            ss_ab = max(0.0, ss_cells - ss_a - ss_b)
            ss_error = max(0.0, ss_total - ss_cells)
    else:
        df_ab = 0
        ss_ab = 0.0
        df_error = n_total - df_a - df_b - 1
        ss_error = max(0.0, ss_total - ss_a - ss_b)

    if df_error <= 0:
        raise ValueError("Insufficient degrees of freedom for error. Check factor levels and replication.")

    # Mean Squares
    ms_a = ss_a / df_a if df_a > 0 else 0.0
    ms_b = ss_b / df_b if df_b > 0 else 0.0
    ms_ab = ss_ab / df_ab if df_ab > 0 else 0.0
    ms_error = ss_error / df_error if df_error > 0 else 0.0
    ms_total = ss_total / df_total if df_total > 0 else 0.0

    # F-statistics and P-values
    f_a = ms_a / ms_error if ms_error > 0 else None
    p_a = 1.0 - stats.f.cdf(f_a, df_a, df_error) if f_a is not None and math.isfinite(f_a) else None

    f_b = ms_b / ms_error if ms_error > 0 else None
    p_b = 1.0 - stats.f.cdf(f_b, df_b, df_error) if f_b is not None and math.isfinite(f_b) else None

    if fit_interaction and df_ab > 0:
        f_ab = ms_ab / ms_error if ms_error > 0 else None
        p_ab = 1.0 - stats.f.cdf(f_ab, df_ab, df_error) if f_ab is not None and math.isfinite(f_ab) else None
    else:
        f_ab = None
        p_ab = None

    # Model Summary
    s_val = math.sqrt(ms_error) if ms_error >= 0 else 0.0
    r_sq = (ss_total - ss_error) / ss_total if ss_total > 0 else 0.0
    r_sq_adj = 1.0 - (ms_error / ms_total) if ms_total > 0 else 0.0

    return {
        "analysis": "twoway_anova",
        "response_name": response_name,
        "factor_a_name": factor_a_name,
        "factor_b_name": factor_b_name,
        "levels_a": levels_a,
        "levels_b": levels_b,
        "fit_interaction": fit_interaction,
        "display_means": display_means,
        "confidence": confidence,
        "count": n_total,
        "missing": missing_count,
        "grand_mean": grand_mean,
        "df_a": df_a,
        "ss_a": ss_a,
        "ms_a": ms_a,
        "f_a": f_a,
        "p_a": p_a,
        "df_b": df_b,
        "ss_b": ss_b,
        "ms_b": ms_b,
        "f_b": f_b,
        "p_b": p_b,
        "df_ab": df_ab,
        "ss_ab": ss_ab,
        "ms_ab": ms_ab,
        "f_ab": f_ab,
        "p_ab": p_ab,
        "df_error": df_error,
        "ss_error": ss_error,
        "ms_error": ms_error,
        "df_total": df_total,
        "ss_total": ss_total,
        "s": s_val,
        "r_squared": r_sq,
        "adjusted_r_squared": r_sq_adj,
        "factor_a_stats": a_stats,
        "factor_b_stats": b_stats,
        "cell_stats": cell_stats
    }
