"""Attribute Gage Study (Analytic Method) Computational Engine.

AIAG MSA Manual (4th Edition) / Minitab Standard:
- Evaluates bias and repeatability of attribute (go/no-go, pass/fail) gages.
- Uses continuous reference standards with multiple inspection trials per part.
- Probit transformation of extreme-adjusted acceptance probabilities:
    Z = Phi^-1(P'_i)
- Least-squares linear regression: Z = b0 + b1 * X.
- Repeatability calculation with AIAG 1.08 over-estimation correction factor.
- Hypothesis testing for gage bias: H0: Bias = 0 vs H1: Bias != 0.
- Calculates data points and curve coordinates for the Gage Performance Curve.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Union


DEFAULT_SETTINGS = {
    "study_multiplier": 5.15,      # AIAG standard (5.15 or 6.0)
    "alpha": 0.05,                 # Significance level for bias test
    "adjustment_factor": 1.08,     # AIAG over-estimation correction factor
    "target": None,                # Target / Reference standard value
    "tolerance": None,             # Tolerance (USL - LSL) for %Repeatability
    "lsl": None,                   # Lower specification limit
    "usl": None,                   # Upper specification limit
    "title": "",                   # Custom chart title
    "gage_info": {
        "gage_name": "",
        "date_of_study": "",
        "reported_by": "",
        "misc": ""
    }
}


def compute_attribute_gage_study(
    reference_values: Sequence[Union[float, int]],
    acceptances: Sequence[Union[float, int]],
    trials: Union[int, Sequence[Union[float, int]]] = 20,
    part_labels: Optional[Sequence[Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute complete Attribute Gage Study (Analytic Method) statistics."""
    # Lazy imports for performance
    import numpy as np
    from scipy import stats

    opts = dict(DEFAULT_SETTINGS)
    if settings:
        opts.update(settings)
        if "gage_info" in settings and isinstance(settings["gage_info"], dict):
            opts["gage_info"] = dict(DEFAULT_SETTINGS["gage_info"])
            opts["gage_info"].update(settings["gage_info"])

    # Validate lengths and build observations
    n_refs = len(reference_values)
    n_acc = len(acceptances)
    if n_refs != n_acc:
        raise ValueError("Reference values and Acceptances columns must have identical lengths.")

    is_trials_seq = isinstance(trials, (list, tuple))
    if is_trials_seq and len(trials) != n_refs:
        raise ValueError("Trials column must have the same length as Reference values.")

    valid_rows = []
    for idx in range(n_refs):
        r_raw = reference_values[idx]
        a_raw = acceptances[idx]
        t_raw = trials[idx] if is_trials_seq else trials

        if r_raw is None or a_raw is None or t_raw is None:
            continue

        try:
            r_val = float(r_raw)
            a_val = int(round(float(a_raw)))
            t_val = int(round(float(t_raw)))
        except (ValueError, TypeError):
            continue

        if not math.isfinite(r_val):
            continue
        if t_val <= 0:
            raise ValueError(f"Number of trials must be positive (got {t_val} at row {idx + 1}).")
        if a_val < 0 or a_val > t_val:
            raise ValueError(f"Acceptances ({a_val}) cannot exceed trials ({t_val}) at row {idx + 1}.")

        p_label = str(part_labels[idx]) if part_labels and idx < len(part_labels) and part_labels[idx] is not None else f"Part {len(valid_rows) + 1}"
        valid_rows.append((p_label, r_val, t_val, a_val))

    N = len(valid_rows)
    if N < 3:
        raise ValueError("Attribute Gage Study requires at least 3 valid parts with reference values and trial counts.")

    # Sort parts by reference value ascending
    valid_rows.sort(key=lambda item: item[1])

    # Extreme value adjustments and probit z-scores (AIAG MSA standard)
    parts_table = []
    x_vals = []
    z_vals = []
    p_adj_vals = []

    for p_label, x_ref, m_trials, a_acc in valid_rows:
        if a_acc == 0:
            p_prime = 0.5 / m_trials
        elif a_acc == m_trials:
            p_prime = (m_trials - 0.5) / m_trials
        else:
            p_prime = a_acc / m_trials

        p_prime = max(1e-6, min(1.0 - 1e-6, p_prime))
        z_score = float(stats.norm.ppf(p_prime))

        parts_table.append({
            "part": p_label,
            "reference": x_ref,
            "trials": m_trials,
            "acceptances": a_acc,
            "raw_prob": a_acc / m_trials,
            "adj_prob": p_prime,
            "z_score": z_score,
        })
        x_vals.append(x_ref)
        z_vals.append(z_score)
        p_adj_vals.append(p_prime)

    x_arr = np.array(x_vals, dtype=float)
    z_arr = np.array(z_vals, dtype=float)

    # Check variation in reference values
    if np.allclose(x_arr, x_arr[0]):
        raise ValueError("Attribute Gage Study requires parts with differing reference values.")

    # Linear regression of Z on X: Z = b0 + b1 * X
    x_mean = float(np.mean(x_arr))
    z_mean = float(np.mean(z_arr))
    s_xx = float(np.sum((x_arr - x_mean) ** 2))
    s_xz = float(np.sum((x_arr - x_mean) * (z_arr - z_mean)))
    s_zz = float(np.sum((z_arr - z_mean) ** 2))

    if s_xx <= 1e-12:
        raise ValueError("Reference values have zero variance.")

    slope = s_xz / s_xx
    intercept = z_mean - slope * x_mean

    if abs(slope) < 1e-9:
        raise ValueError("Slope of fitted probit line is nearly zero; cannot estimate gage repeatability.")

    # Residual sum of squares & R^2
    z_pred = intercept + slope * x_arr
    ss_res = float(np.sum((z_arr - z_pred) ** 2))
    ss_tot = s_zz
    r_squared = float(max(0.0, 1.0 - (ss_res / ss_tot))) if ss_tot > 0 else 0.0

    df_error = N - 2
    s_error = math.sqrt(ss_res / max(1, df_error))

    # Point of 50% acceptance (where Z = 0)
    # 0 = b0 + b1 * X_0.5 => X_0.5 = -b0 / b1
    x_half = -intercept / slope

    # Target reference standard
    target = opts.get("target")
    if target is None:
        if opts.get("lsl") is not None:
            target = float(opts["lsl"])
        elif opts.get("usl") is not None:
            target = float(opts["usl"])
        else:
            target = x_mean
    else:
        target = float(target)

    # Bias = X_0.5 - Target (AIAG MSA standard)
    bias = x_half - target

    # Standard error of Bias via Delta Method on X_0.5
    # Var(-b0 / b1) = s_error^2 / b1^2 * (1/N + (X_0.5 - X_mean)^2 / S_xx)
    se_bias = (s_error / abs(slope)) * math.sqrt(1.0 / N + ((x_half - x_mean) ** 2) / s_xx)

    if se_bias > 1e-12:
        t_stat = bias / se_bias
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_error)))
    else:
        t_stat = 0.0
        p_val = 1.0

    # Repeatability (AIAG MSA 4th Edition Method)
    study_mult = float(opts.get("study_multiplier", 5.15))
    adj_factor = float(opts.get("adjustment_factor", 1.08))

    pre_adjusted_repeatability = study_mult / abs(slope)
    adjusted_repeatability = pre_adjusted_repeatability / adj_factor

    # Tolerance & Percent Repeatability
    tolerance = opts.get("tolerance")
    if tolerance is None and opts.get("lsl") is not None and opts.get("usl") is not None:
        tolerance = float(opts["usl"]) - float(opts["lsl"])
    elif tolerance is not None:
        tolerance = float(tolerance)

    pct_repeatability = None
    if tolerance is not None and tolerance > 0:
        pct_repeatability = (adjusted_repeatability / tolerance) * 100.0

    # High-resolution Gage Performance Curve points
    x_min = float(np.min(x_arr))
    x_max = float(np.max(x_arr))
    padding = max(0.1 * (x_max - x_min), 0.5 * adjusted_repeatability)
    curve_x_min = min(x_min - padding, target - padding if target else x_min - padding)
    curve_x_max = max(x_max + padding, target + padding if target else x_max + padding)

    curve_x = np.linspace(curve_x_min, curve_x_max, 120).tolist()
    curve_p = [float(stats.norm.cdf(intercept + slope * cx)) for cx in curve_x]

    plot_data = {
        "curve_x": curve_x,
        "curve_p": curve_p,
        "points_x": x_vals,
        "points_p": p_adj_vals,
        "points_raw_p": [p["raw_prob"] for p in parts_table],
        "target": target,
        "x_half": x_half,
        "lsl": opts.get("lsl"),
        "usl": opts.get("usl"),
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "bias": bias,
        "adjusted_repeatability": adjusted_repeatability,
    }

    return {
        "parts_table": parts_table,
        "regression": {
            "intercept": intercept,
            "slope": slope,
            "r_squared": r_squared,
            "s_error": s_error,
            "n": N,
        },
        "bias_metrics": {
            "target": target,
            "x_half": x_half,
            "bias": bias,
            "se_bias": se_bias,
            "t_statistic": t_stat,
            "df": df_error,
            "p_value": p_val,
            "alpha": float(opts.get("alpha", 0.05)),
            "is_significant": p_val < float(opts.get("alpha", 0.05)),
        },
        "repeatability": {
            "pre_adjusted": pre_adjusted_repeatability,
            "adjusted": adjusted_repeatability,
            "adjustment_factor": adj_factor,
            "study_multiplier": study_mult,
            "tolerance": tolerance,
            "pct_repeatability": pct_repeatability,
        },
        "plot_data": plot_data,
        "settings": opts,
    }
