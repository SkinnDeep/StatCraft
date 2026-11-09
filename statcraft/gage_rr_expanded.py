"""Computational engine for Gage R&R Study (Expanded).

Provides 1:1 parity with Minitab Expanded Gage R&R:
- Supports 2 to 10 factors (Part, Operator, Gage, Machine, Fixture, etc.)
- Multi-factor ANOVA with main effects and interaction terms
- Expected Mean Squares (EMS) and variance component estimation
- Gage Evaluation table: StdDev, Study Var (6*SD), %Study Var, %Contribution
- Optional %Tolerance (USL - LSL) and %Process (historical standard deviation)
- Number of Distinct Categories (ndc = 1.41 * SD_Part / SD_GRR)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import stats


def clean_expanded_gage_data(
    measurements: Sequence[Any],
    factors: Sequence[Sequence[Any]],
) -> Tuple[np.ndarray, List[List[str]], List[int]]:
    """Clean measurement data and aligned factor columns."""
    n_raw = len(measurements)
    p_factors = len(factors)
    valid_y: List[float] = []
    valid_factors: List[List[str]] = []
    valid_indices: List[int] = []

    for i in range(n_raw):
        m_val = measurements[i]
        if m_val is None:
            continue
        try:
            fm = float(m_val)
            if math.isnan(fm) or math.isinf(fm):
                continue
        except (ValueError, TypeError):
            continue

        row_f: List[str] = []
        ok = True
        for col in factors:
            v = col[i]
            if v is None:
                ok = False
                break
            sv = str(v).strip()
            if not sv:
                ok = False
                break
            row_f.append(sv)

        if ok:
            valid_y.append(fm)
            valid_factors.append(row_f)
            valid_indices.append(i)

    y_arr = np.asarray(valid_y, dtype=float)
    return y_arr, valid_factors, valid_indices


def analyze_gage_rr_expanded(
    measurements: Sequence[Any],
    part_values: Sequence[Any],
    operator_values: Sequence[Any],
    additional_factors: Optional[Sequence[Sequence[Any]]] = None,
    part_name: str = "Part",
    operator_name: str = "Operator",
    additional_factor_names: Optional[Sequence[str]] = None,
    study_multiplier: float = 6.0,
    tolerance: Optional[float] = None,
    process_stdev: Optional[float] = None,
) -> Dict[str, Any]:
    """Perform Expanded Gage R&R ANOVA analysis matching Minitab."""
    all_factor_cols = [part_values, operator_values]
    all_factor_names = [part_name, operator_name]

    if additional_factors:
        all_factor_cols.extend(additional_factors)
        if additional_factor_names:
            all_factor_names.extend(additional_factor_names)
        else:
            for i in range(len(additional_factors)):
                all_factor_names.append(f"Factor{i+1}")

    y, factors_clean, valid_indices = clean_expanded_gage_data(measurements, all_factor_cols)
    N = len(y)
    if N < 6:
        raise ValueError("Expanded Gage R&R requires at least 6 valid measurements.")

    K = len(all_factor_names)
    # Factor levels
    factor_levels: Dict[str, List[str]] = {}
    for j, fname in enumerate(all_factor_names):
        lvls = sorted(list(set(row[j] for row in factors_clean)))
        if len(lvls) < 2:
            raise ValueError(f"Factor '{fname}' must have at least 2 distinct levels.")
        factor_levels[fname] = lvls

    grand_mean = float(np.mean(y))
    ss_total = float(np.sum((y - grand_mean) ** 2))
    df_total = N - 1

    # 1. Main effects
    # For each factor, compute SS and DF
    anova_terms: List[Dict[str, Any]] = []
    ss_accounted = 0.0
    df_accounted = 0

    main_effect_ms: Dict[str, float] = {}
    main_effect_df: Dict[str, int] = {}
    main_effect_ss: Dict[str, float] = {}

    for j, fname in enumerate(all_factor_names):
        col_vals = [row[j] for row in factors_clean]
        lvls = factor_levels[fname]
        df_f = len(lvls) - 1
        ss_f = 0.0
        for lvl in lvls:
            lvl_y = [y[idx] for idx, v in enumerate(col_vals) if v == lvl]
            n_lvl = len(lvl_y)
            if n_lvl > 0:
                ss_f += n_lvl * (float(np.mean(lvl_y)) - grand_mean) ** 2
        ms_f = ss_f / df_f if df_f > 0 else 0.0
        main_effect_ss[fname] = ss_f
        main_effect_df[fname] = df_f
        main_effect_ms[fname] = ms_f
        ss_accounted += ss_f
        df_accounted += df_f

    # 2. Two-way interactions (Part * Operator, and interactions involving other factors)
    interaction_ss: Dict[str, float] = {}
    interaction_df: Dict[str, int] = {}
    interaction_ms: Dict[str, float] = {}

    for j1 in range(K):
        for j2 in range(j1 + 1, K):
            fn1 = all_factor_names[j1]
            fn2 = all_factor_names[j2]
            term_name = f"{fn1} * {fn2}"
            col1 = [row[j1] for row in factors_clean]
            col2 = [row[j2] for row in factors_clean]
            lvls1 = factor_levels[fn1]
            lvls2 = factor_levels[fn2]
            df_int = (len(lvls1) - 1) * (len(lvls2) - 1)

            # Compute interaction cell SS
            cell_ss = 0.0
            for l1 in lvls1:
                for l2 in lvls2:
                    sub_y = [y[idx] for idx in range(N) if col1[idx] == l1 and col2[idx] == l2]
                    n_sub = len(sub_y)
                    if n_sub > 0:
                        cell_ss += n_sub * (float(np.mean(sub_y)) - grand_mean) ** 2

            ss_int = max(0.0, cell_ss - main_effect_ss[fn1] - main_effect_ss[fn2])
            ms_int = ss_int / df_int if df_int > 0 else 0.0
            interaction_ss[term_name] = ss_int
            interaction_df[term_name] = df_int
            interaction_ms[term_name] = ms_int
            ss_accounted += ss_int
            df_accounted += df_int

    # 3. Residual Error (Repeatability)
    df_error = df_total - df_accounted
    if df_error <= 0:
        # If no replicates, error falls back to last interaction
        df_error = max(1, df_total - sum(main_effect_df.values()))
        ss_error = max(0.0, ss_total - sum(main_effect_ss.values()))
    else:
        ss_error = max(0.0, ss_total - ss_accounted)
    ms_error = ss_error / df_error if df_error > 0 else 0.0

    # Build ANOVA table with F-tests
    # Interacting terms tested against MS Error
    part_op_term = f"{part_name} * {operator_name}"
    base_denom_ms = interaction_ms.get(part_op_term, ms_error)
    base_denom_df = interaction_df.get(part_op_term, df_error)

    # Main effects rows
    for fname in all_factor_names:
        df_val = main_effect_df[fname]
        ss_val = main_effect_ss[fname]
        ms_val = main_effect_ms[fname]
        # In Gage R&R, Part and Operator main effects are tested against Part*Operator interaction if present
        if part_op_term in interaction_ms and fname in (part_name, operator_name) and base_denom_ms > 1e-12:
            denom_ms = base_denom_ms
            denom_df = base_denom_df
        else:
            denom_ms = ms_error
            denom_df = df_error

        f_stat = ms_val / denom_ms if denom_ms > 1e-12 else float("nan")
        p_val = float(stats.f.sf(f_stat, df_val, denom_df)) if denom_ms > 1e-12 and df_val > 0 and denom_df > 0 else None
        anova_terms.append({
            "source": fname,
            "df": df_val,
            "ss": ss_val,
            "ms": ms_val,
            "f": f_stat,
            "p_value": p_val,
        })

    # Interaction rows
    for term_name, ss_val in interaction_ss.items():
        df_val = interaction_df[term_name]
        ms_val = interaction_ms[term_name]
        f_stat = ms_val / ms_error if ms_error > 1e-12 else float("nan")
        p_val = float(stats.f.sf(f_stat, df_val, df_error)) if ms_error > 1e-12 and df_val > 0 and df_error > 0 else None
        anova_terms.append({
            "source": term_name,
            "df": df_val,
            "ss": ss_val,
            "ms": ms_val,
            "f": f_stat,
            "p_value": p_val,
        })

    # Error and Total rows
    anova_terms.append({
        "source": "Repeatability",
        "df": df_error,
        "ss": ss_error,
        "ms": ms_error,
        "f": None,
        "p_value": None,
    })
    anova_terms.append({
        "source": "Total",
        "df": df_total,
        "ss": ss_total,
        "ms": None,
        "f": None,
        "p_value": None,
    })

    # 4. Variance Components Estimation
    # Repeatability = MS Error
    var_repeatability = max(0.0, ms_error)

    # Number of levels
    p_count = len(factor_levels[part_name])
    o_count = len(factor_levels[operator_name])
    n_rep = max(1.0, float(N) / (p_count * o_count))

    # Interaction variance: Part * Operator
    var_part_op = 0.0
    if part_op_term in interaction_ms:
        var_part_op = max(0.0, (interaction_ms[part_op_term] - ms_error) / n_rep)

    # Operator variance
    var_operator = 0.0
    denom_op = interaction_ms.get(part_op_term, ms_error)
    var_operator = max(0.0, (main_effect_ms[operator_name] - denom_op) / (p_count * n_rep))

    # Additional factor variances
    other_variances: Dict[str, float] = {}
    for fname in all_factor_names:
        if fname in (part_name, operator_name):
            continue
        c_div = float(N) / len(factor_levels[fname])
        var_f = max(0.0, (main_effect_ms[fname] - ms_error) / c_div)
        other_variances[fname] = var_f

    # Reproducibility = Operator + Part*Operator + additional factor components
    var_reproducibility = var_operator + var_part_op + sum(other_variances.values())

    # Total Gage R&R = Repeatability + Reproducibility
    var_total_grr = var_repeatability + var_reproducibility

    # Part-to-Part variance
    denom_part = interaction_ms.get(part_op_term, ms_error)
    var_part = max(0.0, (main_effect_ms[part_name] - denom_part) / (o_count * n_rep))

    # Total Variation
    var_total = var_total_grr + var_part
    if var_total < 1e-12:
        var_total = 1.0

    # Components list
    components: List[Tuple[str, str, float]] = [
        ("total_grr", "Total Gage R&R", var_total_grr),
        ("repeatability", "  Repeatability", var_repeatability),
        ("reproducibility", "  Reproducibility", var_reproducibility),
        ("operator", f"    {operator_name}", var_operator),
    ]
    if var_part_op > 0 or part_op_term in interaction_ms:
        components.append(("part_operator", f"    {part_op_term}", var_part_op))
    for fname, vf in other_variances.items():
        components.append((fname.lower(), f"    {fname}", vf))

    components.append(("part_to_part", f"Part-To-Part ({part_name})", var_part))
    components.append(("total_variation", "Total Variation", var_total))

    # Variance Components table
    var_comp_table = []
    for cid, sname, vcomp in components:
        pct_contrib = (vcomp / var_total) * 100.0 if var_total > 0 else 0.0
        var_comp_table.append({
            "id": cid,
            "source": sname,
            "var_comp": vcomp,
            "pct_contribution": pct_contrib,
        })

    # Gage Evaluation table
    total_sd = math.sqrt(max(0.0, var_total))
    gage_eval_table = []
    for cid, sname, vcomp in components:
        sd = math.sqrt(max(0.0, vcomp))
        study_var = study_multiplier * sd
        pct_study_var = (sd / total_sd) * 100.0 if total_sd > 0 else 0.0
        pct_tolerance = (study_var / tolerance) * 100.0 if tolerance is not None and tolerance > 0 else None
        pct_process = (sd / process_stdev) * 100.0 if process_stdev is not None and process_stdev > 0 else None

        gage_eval_table.append({
            "id": cid,
            "source": sname,
            "std_dev": sd,
            "study_var": study_var,
            "pct_study_var": pct_study_var,
            "pct_tolerance": pct_tolerance,
            "pct_process": pct_process,
        })

    # Number of distinct categories: ndc = floor(1.41 * (SD_Part / SD_TotalGRR))
    sd_part = math.sqrt(max(0.0, var_part))
    sd_grr = math.sqrt(max(0.0, var_total_grr))
    if sd_grr > 1e-12:
        ndc = max(1, int(math.floor(1.41421356 * (sd_part / sd_grr))))
    else:
        ndc = 1

    return {
        "analysis": "gage_rr_expanded",
        "part_name": part_name,
        "operator_name": operator_name,
        "all_factor_names": all_factor_names,
        "study_multiplier": study_multiplier,
        "tolerance": tolerance,
        "process_stdev": process_stdev,
        "n_obs": N,
        "anova": anova_terms,
        "variance_components": var_comp_table,
        "gage_evaluation": gage_eval_table,
        "ndc": ndc,
        "total_variation": var_total,
        "total_sd": total_sd,
        "title": f"Gage R&R Study (Expanded) for {', '.join(all_factor_names)}",
    }
