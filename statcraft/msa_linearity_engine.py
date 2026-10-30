"""Gage Linearity and Bias Study Engine.

Method reference: AIAG MSA Manual (4th Edition) / StatCraft Gage Linearity and Bias Study.
Determines whether a gage has linear bias across the operating measurement range.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np
from scipy import stats


def analyze_gage_linearity_and_bias(
    reference_values: List[float],
    measurements: List[float],
    parts: Optional[List[Any]] = None,
    process_variation: Optional[float] = None,
    process_stdev: Optional[float] = None,
    study_multiplier: float = 6.0,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Perform Gage Linearity and Bias analysis."""
    if len(reference_values) != len(measurements):
        raise ValueError("Reference values and measurements must have identical lengths.")

    for name, value in [('study variation multiplier', study_multiplier), ('alpha', alpha)]:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(name + ' must be positive and finite.')
    if alpha >= 1:
        raise ValueError('Alpha must be less than one.')
    for name, value in [('process variation', process_variation), ('process standard deviation', process_stdev)]:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
            raise ValueError(name + ' must be positive and finite.')

    # Clean rows
    valid_rows = []
    for idx, (ref, meas) in enumerate(zip(reference_values, measurements)):
        if ref is not None and meas is not None:
            try:
                r_val = float(ref)
                m_val = float(meas)
                if math.isfinite(r_val) and math.isfinite(m_val):
                    p_val = str(parts[idx]) if parts and idx < len(parts) and parts[idx] is not None else None
                    valid_rows.append((r_val, m_val, p_val))
            except (ValueError, TypeError):
                continue

    N = len(valid_rows)
    if N < 5:
        raise ValueError("Gage Linearity and Bias study requires at least 5 observations.")

    refs = np.array([r for r, _, _ in valid_rows], dtype=float)
    meas = np.array([m for _, m, _ in valid_rows], dtype=float)
    biases = meas - refs

    unique_refs = sorted(list(set(refs)))
    if len(unique_refs) < 2:
        raise ValueError("Gage Linearity study requires at least 2 distinct reference standard values.")

    # Determine Process Variation (PV)
    if process_variation is not None and process_variation > 0:
        pv = float(process_variation)
    elif process_stdev is not None and process_stdev > 0:
        pv = float(study_multiplier * process_stdev)
    else:
        # Default: study variation of measurements
        pv = float(study_multiplier * np.std(meas, ddof=1)) if len(meas) > 1 else 1.0

    # Linear Regression of Bias on Reference: bias = b0 + b1 * ref
    mean_ref = float(np.mean(refs))
    mean_bias = float(np.mean(biases))

    sxx = float(np.sum((refs - mean_ref) ** 2))
    sxy = float(np.sum((refs - mean_ref) * (biases - mean_bias)))
    syy = float(np.sum((biases - mean_bias) ** 2))

    if sxx <= 1e-15:
        raise ValueError("Reference values have near-zero variation.")

    slope = sxy / sxx
    intercept = mean_bias - slope * mean_ref

    ss_reg = float(slope * sxy)
    ss_resid = float(np.sum((biases - (intercept + slope * refs)) ** 2))
    df_resid = max(1, N - 2)
    ms_resid = ss_resid / df_resid
    s_err = math.sqrt(ms_resid)
    r_squared = float(ss_reg / syy) if syy > 0 else 0.0

    se_slope = s_err / math.sqrt(sxx) if sxx > 0 else 0.0
    def inference(estimate, standard_error):
        if standard_error == 0:
            return None, None
        t_value = estimate / standard_error
        return float(t_value), float(2 * stats.t.sf(abs(t_value), df=df_resid))
    t_slope, p_slope = inference(slope, se_slope)
    se_intercept = s_err * math.sqrt(1.0 / N + (mean_ref ** 2) / sxx)
    t_intercept, p_intercept = inference(intercept, se_intercept)

    # Gage Linearity
    linearity = abs(slope) * pv
    pct_linearity = (linearity / pv) * 100.0 if pv > 0 else 0.0

    # Bias by Reference Value Table
    bias_table = []
    ref_bias_groups: Dict[float, List[float]] = {}
    for r, b in zip(refs, biases):
        if r not in ref_bias_groups:
            ref_bias_groups[r] = []
        ref_bias_groups[r].append(b)

    for r in unique_refs:
        grp = ref_bias_groups[r]
        n_r = len(grp)
        avg_b = float(np.mean(grp))
        # StatCraft uses pooled s_err / sqrt(n_r)
        se_b = s_err / math.sqrt(n_r) if n_r > 0 else 0.0
        t_b, p_b = inference(avg_b, se_b)
        pct_b = (abs(avg_b) / pv) * 100.0 if pv > 0 else 0.0

        bias_table.append({
            "reference": r,
            "count": n_r,
            "average_bias": avg_b,
            "pct_bias": pct_b,
            "std_error": se_b,
            "t_statistic": t_b,
            "p_value": p_b,
        })

    # Overall Gage Bias
    se_overall = s_err / math.sqrt(N) if N > 0 else 0.0
    t_overall, p_overall = inference(mean_bias, se_overall)
    pct_overall = (abs(mean_bias) / pv) * 100.0 if pv > 0 else 0.0

    overall_bias = {
        "average_bias": mean_bias,
        "pct_bias": pct_overall,
        "std_error": se_overall,
        "t_statistic": t_overall,
        "p_value": p_overall,
    }

    # Plot data points & regression line with confidence intervals
    # CI for fitted line: y_fit +- t_crit * s_err * sqrt(1/N + (x - x_bar)^2 / sxx)
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df_resid))
    plot_x = np.linspace(min(unique_refs), max(unique_refs), 100)
    plot_fit = intercept + slope * plot_x
    plot_se = s_err * np.sqrt(1.0 / N + ((plot_x - mean_ref) ** 2) / sxx)
    plot_lci = plot_fit - t_crit * plot_se
    plot_uci = plot_fit + t_crit * plot_se

    return {
        "warnings": ['Sampling-based t tests are not estimable because residual variation is zero.'] if s_err == 0 else [],
        "analysis": "gage_linearity_and_bias",
        "method": "Gage Linearity and Bias Study (AIAG MSA / StatCraft)",
        "n_total": N,
        "process_variation": pv,
        "study_multiplier": study_multiplier,
        "alpha": alpha,
        "regression": {
            "slope": slope,
            "slope_se": se_slope,
            "slope_t": t_slope,
            "slope_p": p_slope,
            "intercept": intercept,
            "intercept_se": se_intercept,
            "intercept_t": t_intercept,
            "intercept_p": p_intercept,
            "s": s_err,
            "r_squared": r_squared,
            "equation": f"Bias = {intercept:.4f} + {slope:.4f} * Reference",
        },
        "linearity": linearity,
        "pct_linearity": pct_linearity,
        "bias_table": bias_table,
        "overall_bias": overall_bias,
        "plot_data": {
            "refs": refs.tolist(),
            "biases": biases.tolist(),
            "unique_refs": unique_refs,
            "plot_x": plot_x.tolist(),
            "plot_fit": plot_fit.tolist(),
            "plot_lci": plot_lci.tolist(),
            "plot_uci": plot_uci.tolist(),
        },
    }
