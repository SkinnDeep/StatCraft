"""Evaluating the Measurement Process (EMP) — Dr. Donald J. Wheeler's measurement system analysis.

References:
- Wheeler, D. J. (2006). EMP III: Evaluating the Measurement Process & Using Imperfect Data. SPC Press.
- JMP: Analyze > Quality and Process > Variability / Attribute Gauge Chart > EMP Gauge.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import stats


def evaluate_measurement_process(
    measurements: Sequence[float],
    parts: Sequence[Any],
    operators: Sequence[Any],
    alpha_interaction: float = 0.05,
) -> Dict[str, Any]:
    """Fit two-way random effects ANOVA and compute Wheeler EMP metrics:
    - Intraclass Correlation Coefficient (ICC)
    - Process Signal Attenuation
    - Wheeler Classification (First, Second, Third, Fourth Class Monitor)
    - Probable Error (PE)
    - Smallest Effective Unit (SEU)
    - Shift Detection Probabilities
    """
    m_arr = np.asarray(measurements, dtype=float)
    p_arr = np.asarray(parts)
    o_arr = np.asarray(operators)

    if len(m_arr) != len(p_arr) or len(m_arr) != len(o_arr) or len(m_arr) < 6:
        raise ValueError("EMP requires at least 6 aligned measurement, part, and operator observations.")

    # Filter out missing values
    valid_mask = np.isfinite(m_arr) & (p_arr != None) & (o_arr != None) & (p_arr != "") & (o_arr != "")
    m_clean = m_arr[valid_mask]
    p_clean = p_arr[valid_mask]
    o_clean = o_arr[valid_mask]

    n_total = len(m_clean)
    unique_parts = np.unique(p_clean)
    unique_ops = np.unique(o_clean)
    n_p = len(unique_parts)
    n_o = len(unique_ops)

    if n_p < 2:
        raise ValueError("EMP requires at least 2 distinct parts.")
    if n_o < 1:
        raise ValueError("EMP requires at least 1 operator.")

    grand_mean = float(np.mean(m_clean))
    ss_total = float(np.sum((m_clean - grand_mean) ** 2))
    df_total = n_total - 1

    # Check balanced cell counts
    cells = {}
    for y_val, p_val, o_val in zip(m_clean, p_clean, o_clean):
        key = (p_val, o_val)
        cells.setdefault(key, []).append(y_val)

    rep_counts = [len(v) for v in cells.values()]
    n_rep = rep_counts[0]
    is_balanced = (len(set(rep_counts)) == 1) and (len(cells) == n_p * n_o)

    if not is_balanced:
        # Average replicates per cell
        n_rep = float(n_total) / float(n_p * n_o)

    # Sum of squares Part
    part_means = {p: np.mean([m_clean[i] for i in range(n_total) if p_clean[i] == p]) for p in unique_parts}
    ss_part = float(sum(len([1 for i in range(n_total) if p_clean[i] == p]) * ((part_means[p] - grand_mean) ** 2) for p in unique_parts))
    df_part = n_p - 1
    ms_part = ss_part / max(1, df_part)

    # Sum of squares Operator
    op_means = {o: np.mean([m_clean[i] for i in range(n_total) if o_clean[i] == o]) for o in unique_ops}
    ss_op = float(sum(len([1 for i in range(n_total) if o_clean[i] == o]) * ((op_means[o] - grand_mean) ** 2) for o in unique_ops))
    df_op = max(1, n_o - 1)
    ms_op = ss_op / max(1, df_op) if n_o > 1 else 0.0

    # Sum of squares Interaction
    cell_means = {k: np.mean(v) for k, v in cells.items()}
    ss_subtotal = float(sum(len(v) * ((cell_means[k] - grand_mean) ** 2) for k, v in cells.items()))
    ss_inter = max(0.0, ss_subtotal - ss_part - ss_op)
    df_inter = (n_p - 1) * (n_o - 1)
    ms_inter = (ss_inter / max(1, df_inter)) if df_inter > 0 else 0.0

    # Repeatability (pure error within cells)
    ss_error = max(0.0, ss_total - ss_subtotal)
    df_error = n_total - len(cells)
    ms_error = ss_error / max(1, df_error) if df_error > 0 else 0.0

    # Test interaction significance
    has_interaction = False
    if df_inter > 0 and ms_error > 1e-12:
        f_inter = ms_inter / ms_error
        p_inter = 1.0 - float(stats.f.cdf(f_inter, df_inter, df_error))
        has_interaction = (p_inter < alpha_interaction)

    # Variance components calculation
    var_repeatability = ms_error

    if has_interaction and df_inter > 0:
        var_inter = max(0.0, (ms_inter - ms_error) / n_rep)
        denom_part = ms_inter
    else:
        var_inter = 0.0
        # Pool interaction into error if not significant
        ss_pooled_error = ss_inter + ss_error
        df_pooled_error = df_inter + df_error
        ms_pooled_error = ss_pooled_error / max(1, df_pooled_error)
        var_repeatability = ms_pooled_error
        denom_part = ms_pooled_error

    if n_o > 1:
        denom_op = ms_inter if has_interaction else var_repeatability
        var_op = max(0.0, (ms_op - denom_op) / (n_p * n_rep))
    else:
        var_op = 0.0

    var_part = max(0.0, (ms_part - denom_part) / (n_o * n_rep))

    # Combined measurement error variance (Repeatability + Operator + Interaction)
    var_measurement = var_repeatability + var_op + var_inter
    var_total = var_part + var_measurement

    # Intraclass Correlation Coefficient (ICC = rho)
    rho = (var_part / var_total) if var_total > 1e-12 else 0.0
    rho = max(0.0, min(1.0, rho))

    # Process signal attenuation = 1 - sqrt(rho)
    attenuation = max(0.0, 1.0 - math.sqrt(rho))

    # Wheeler Classification
    if rho >= 0.80:
        emp_class = "First Class"
        class_desc = "Excellent: < 10% signal attenuation; detects shifts ≥ 3σ with Rule 1."
        color_code = "#10b981"  # Emerald
    elif rho >= 0.50:
        emp_class = "Second Class"
        class_desc = "Acceptable: 10%–30% signal attenuation; detects shifts with Rules 1–4."
        color_code = "#f59e0b"  # Amber
    elif rho >= 0.20:
        emp_class = "Third Class"
        class_desc = "Marginal: 30%–55% signal attenuation; detects shifts only with Rules 1–8."
        color_code = "#f97316"  # Orange
    else:
        emp_class = "Fourth Class"
        class_desc = "Unacceptable: > 55% signal attenuation; unable to monitor process."
        color_code = "#ef4444"  # Red

    # Probable Error (PE) = 0.6745 * sigma_e
    sigma_error = math.sqrt(var_measurement)
    pe = 0.67449 * sigma_error

    # Smallest Effective Unit (SEU)
    seu_lower = 0.2 * pe
    seu_upper = 2.0 * pe

    # Detect empirical measurement step size / resolution
    diffs = np.diff(np.sort(m_clean))
    nonzero_diffs = diffs[diffs > 1e-9]
    meas_resolution = float(np.min(nonzero_diffs)) if len(nonzero_diffs) > 0 else 0.1

    if meas_resolution > seu_upper:
        resolution_status = f"Too Chunky: measurement increment ({meas_resolution:.4g}) > 2·PE ({seu_upper:.4g})."
    elif meas_resolution < seu_lower:
        resolution_status = f"Too Fine: measurement increment ({meas_resolution:.4g}) < 0.2·PE ({seu_lower:.4g})."
    else:
        resolution_status = f"Appropriate: measurement increment ({meas_resolution:.4g}) is between 0.2·PE and 2·PE."

    # Shift Detection Probabilities across subgroups
    # P(shift >= k * sigma) detected within n subgroups
    shift_multipliers = [1.0, 2.0, 3.0, 4.0]
    shift_table = []
    for shift_k in shift_multipliers:
        # Effective shift in standardized units under attenuation: delta_eff = shift_k * sqrt(rho)
        delta_eff = shift_k * math.sqrt(rho)
        # Prob of single point outside 3 sigma:
        p_single = float(1.0 - stats.norm.cdf(3.0 - delta_eff) + stats.norm.cdf(-3.0 - delta_eff))
        p_within_1 = p_single
        p_within_2 = 1.0 - ((1.0 - p_single) ** 2)
        p_within_3 = 1.0 - ((1.0 - p_single) ** 3)
        p_within_4 = 1.0 - ((1.0 - p_single) ** 4)
        shift_table.append({
            "shift": f"{shift_k:g}σ",
            "delta_eff": delta_eff,
            "p_subgroup_1": p_within_1,
            "p_subgroup_2": p_within_2,
            "p_subgroup_3": p_within_3,
            "p_subgroup_4": p_within_4,
        })

    # Variance Components Breakdown Table
    components = [
        {
            "source": "Part-to-Part",
            "var": var_part,
            "pct": (var_part / var_total * 100.0) if var_total > 0 else 0.0,
            "sd": math.sqrt(var_part),
        },
        {
            "source": "Operator (Reproducibility)",
            "var": var_op,
            "pct": (var_op / var_total * 100.0) if var_total > 0 else 0.0,
            "sd": math.sqrt(var_op),
        },
    ]
    if var_inter > 0:
        components.append({
            "source": "Part * Operator",
            "var": var_inter,
            "pct": (var_inter / var_total * 100.0) if var_total > 0 else 0.0,
            "sd": math.sqrt(var_inter),
        })
    components.extend([
        {
            "source": "Repeatability (Equipment)",
            "var": var_repeatability,
            "pct": (var_repeatability / var_total * 100.0) if var_total > 0 else 0.0,
            "sd": math.sqrt(var_repeatability),
        },
        {
            "source": "Combined Measurement Error",
            "var": var_measurement,
            "pct": (var_measurement / var_total * 100.0) if var_total > 0 else 0.0,
            "sd": math.sqrt(var_measurement),
        },
        {
            "source": "Total Variation",
            "var": var_total,
            "pct": 100.0,
            "sd": math.sqrt(var_total),
        },
    ])

    return {
        "analysis": "evaluating_measurement_process",
        "n_obs": n_total,
        "n_parts": n_p,
        "n_operators": n_o,
        "rho": rho,
        "icc": rho,
        "attenuation": attenuation,
        "emp_class": emp_class,
        "class_desc": class_desc,
        "color_code": color_code,
        "probable_error": pe,
        "var_part": var_part,
        "var_measurement": var_measurement,
        "var_total": var_total,
        "resolution": meas_resolution,
        "resolution_status": resolution_status,
        "components": components,
        "shift_table": shift_table,
    }
