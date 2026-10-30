"""Nested Gage R&R Study Engine (Random Two-Factor Nested ANOVA).

Method reference: StatCraft official Nested Gage R&R methods and formulas.
In a nested design, parts are unique to each operator (e.g. destructive testing).
Factors:
  Operator: j = 1, ..., J
  Part(Operator): i = 1, ..., I parts nested within operator j
  Replicates: k = 1, ..., K repeated measurements per part
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np
from scipy.stats import f as f_dist


def analyze_nested_gage_rr(
    measurements: List[float],
    parts: List[Any],
    operators: List[Any],
    study_multiplier: float = 6.0,
    tolerance: Optional[float] = None,
    process_stdev: Optional[float] = None,
) -> Dict[str, Any]:
    """Fit balanced nested random-effects ANOVA: Part nested in Operator."""
    if len(measurements) != len(parts) or len(measurements) != len(operators):
        raise ValueError("Measurements, parts, and operators must have identical lengths.")

    # Clean missing values
    valid_rows = []
    for idx, (m, p, op) in enumerate(zip(measurements, parts, operators)):
        if m is not None and p is not None and op is not None:
            try:
                fm = float(m)
                if math.isfinite(fm):
                    valid_rows.append((fm, str(p), str(op), idx))
            except (ValueError, TypeError):
                continue

    if len(valid_rows) < 4:
        raise ValueError("Nested Gage R&R requires at least 4 valid observations.")

    # Group by Operator -> Part -> list of measurements
    op_tree: Dict[str, Dict[str, List[float]]] = {}
    for m, p, op, _ in valid_rows:
        if op not in op_tree:
            op_tree[op] = {}
        if p not in op_tree[op]:
            op_tree[op][p] = []
        op_tree[op][p].append(m)

    unique_ops = sorted(op_tree.keys())
    J = len(unique_ops)
    if J < 2:
        raise ValueError("Nested Gage R&R requires at least two operators.")

    # Check balance: each operator must have same number of parts, each part same number of replicates
    part_counts = [len(op_tree[op]) for op in unique_ops]
    I = part_counts[0]
    if any(c != I for c in part_counts) or I < 2:
        raise ValueError("Nested Gage R&R requires a balanced design with at least two parts per operator.")

    rep_counts = [len(op_tree[op][p]) for op in unique_ops for p in op_tree[op]]
    K = rep_counts[0]
    if any(c != K for c in rep_counts) or K < 2:
        raise ValueError("Nested Gage R&R requires a balanced design with at least two replicates per part.")

    N = J * I * K

    # Compute Means
    all_vals = [m for m, _, _, _ in valid_rows]
    grand_mean = float(np.mean(all_vals))

    op_means: Dict[str, float] = {}
    part_means: Dict[str, Dict[str, float]] = {}

    for op in unique_ops:
        op_vals = []
        part_means[op] = {}
        for p in op_tree[op]:
            p_vals = op_tree[op][p]
            part_means[op][p] = float(np.mean(p_vals))
            op_vals.extend(p_vals)
        op_means[op] = float(np.mean(op_vals))

    # Sum of Squares
    ss_operator = float(I * K * sum((op_means[op] - grand_mean) ** 2 for op in unique_ops))
    ss_part_op = float(K * sum(
        (part_means[op][p] - op_means[op]) ** 2
        for op in unique_ops for p in op_tree[op]
    ))
    ss_error = float(sum(
        (m - part_means[op][p]) ** 2
        for op in unique_ops for p in op_tree[op] for m in op_tree[op][p]
    ))
    ss_total = float(sum((m - grand_mean) ** 2 for m in all_vals))

    # Degrees of Freedom
    df_operator = J - 1
    df_part_op = J * (I - 1)
    df_error = J * I * (K - 1)
    df_total = N - 1

    # Mean Squares
    ms_operator = ss_operator / df_operator if df_operator > 0 else 0.0
    ms_part_op = ss_part_op / df_part_op if df_part_op > 0 else 0.0
    ms_error = ss_error / df_error if df_error > 0 else 0.0

    # F-tests
    # Operator tested against Part(Operator)
    if ms_part_op > 0:
        f_op = ms_operator / ms_part_op
        p_op = float(f_dist.sf(f_op, df_operator, df_part_op))
    else:
        f_op = None
        p_op = None

    # Part(Operator) tested against Repeatability (Error)
    if ms_error > 0:
        f_part = ms_part_op / ms_error
        p_part = float(f_dist.sf(f_part, df_part_op, df_error))
    else:
        f_part = None
        p_part = None

    anova_table = [
        {"source": "Operator", "df": df_operator, "ss": ss_operator, "ms": ms_operator, "f": f_op, "p_value": p_op},
        {"source": "Part (Operator)", "df": df_part_op, "ss": ss_part_op, "ms": ms_part_op, "f": f_part, "p_value": p_part},
        {"source": "Repeatability", "df": df_error, "ss": ss_error, "ms": ms_error, "f": None, "p_value": None},
        {"source": "Total", "df": df_total, "ss": ss_total, "ms": None, "f": None, "p_value": None},
    ]

    # Variance Components (Random Effects)
    var_repeat = ms_error
    var_part = max(0.0, (ms_part_op - ms_error) / K)
    var_operator = max(0.0, (ms_operator - ms_part_op) / (I * K))

    var_grr = var_repeat + var_operator
    var_total = var_grr + var_part

    definitions = [
        ("total_grr", "Total Gage R&R", var_grr),
        ("repeatability", "  Repeatability", var_repeat),
        ("reproducibility", "  Reproducibility (Operator)", var_operator),
        ("part_to_part", "Part-To-Part (Operator)", var_part),
        ("total", "Total Variation", var_total),
    ]

    components = []
    for key, label, var in definitions:
        sd = math.sqrt(var) if var >= 0 else 0.0
        study_var = study_multiplier * sd
        pct_contrib = 100.0 * (var / var_total) if var_total > 0 else 0.0
        pct_study_var = 100.0 * (sd / math.sqrt(var_total)) if var_total > 0 else 0.0
        pct_tolerance = 100.0 * (study_var / tolerance) if tolerance is not None and tolerance > 0 else None
        pct_process = 100.0 * (sd / process_stdev) if process_stdev is not None and process_stdev > 0 else None

        components.append({
            "key": key,
            "source": label,
            "variance": var,
            "sd": sd,
            "study_variation": study_var,
            "percent_contribution": pct_contrib,
            "percent_study_variation": pct_study_var,
            "percent_tolerance": pct_tolerance,
            "percent_process": pct_process,
        })

    # Number of distinct categories (ndc)
    if var_grr > 0:
        ratio = 1.41 * math.sqrt(var_part) / math.sqrt(var_grr)
        ndc = max(1, math.floor(ratio))
    else:
        ndc = 1 if var_part == 0 else None

    # Chart / plot summaries
    plot_data = {
        "operators": unique_ops,
        "n_operators": J,
        "n_parts_per_op": I,
        "n_replicates": K,
        "op_means": op_means,
        "part_means": part_means,
        "raw_points": [{"op": op, "part": p, "val": m} for m, p, op, _ in valid_rows],
    }

    return {
        "analysis": "nested_gage_rr",
        "method": "Balanced Nested Random-Effects ANOVA",
        "study_multiplier": study_multiplier,
        "tolerance": tolerance,
        "process_stdev": process_stdev,
        "n_total": N,
        "operators_count": J,
        "parts_per_operator": I,
        "replicates_per_part": K,
        "grand_mean": grand_mean,
        "anova": anova_table,
        "variance_components": components,
        "ndc": ndc,
        "plot_data": plot_data,
    }
