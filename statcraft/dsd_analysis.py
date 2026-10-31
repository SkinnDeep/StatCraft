"""Analysis of Definitive Screening Designs (DSD) using stepwise model selection with heredity.

References:
- Jones, B., & Nachtsheim, C. J. (2011). "A Class of Three-Level Designs for Physical Experiments."
  Journal of Quality Technology, 43(1), 1-15.
- Montgomery, D. C. (2017). Design and Analysis of Experiments (9th ed.). Wiley.
"""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import stats

from .model import Worksheet


def _f_cdf(x: float, df1: float, df2: float) -> float:
    if x <= 0 or df1 <= 0 or df2 <= 0:
        return 0.0
    return float(stats.f.cdf(x, df1, df2))


def _t_ppf(q: float, df: float) -> float:
    if df <= 0:
        return 1.96
    return float(stats.t.ppf(q, df))


def analyze_definitive_screening_design(
    worksheet: Worksheet,
    response_index: int,
    factor_indices: Optional[Sequence[int]] = None,
    selection: str = "stepwise",  # 'stepwise', 'main_effects', 'full'
    alpha_enter: float = 0.10,
    alpha_leave: float = 0.10,
    confidence: float = 95.0,
    show_pareto: bool = True,
) -> Dict[str, Any]:
    """Fit a Definitive Screening Design model and compute full ANOVA, Model Summary,
    Coded Coefficients, and Standardized Effects for Pareto analysis.
    """
    if not (0 <= response_index < len(worksheet.columns)):
        raise ValueError(f"Invalid response column index {response_index}.")

    resp_col = worksheet.columns[response_index]
    if resp_col.kind != "number":
        raise ValueError(f"Response column '{resp_col.name}' must be numeric.")

    # Determine factors
    metadata = worksheet.metadata.get("doe", {})
    known_factors = metadata.get("factors", []) if metadata.get("design") == "definitive_screening" else []

    if factor_indices is None:
        if known_factors:
            factor_indices = [f["column_index"] for f in known_factors if 0 <= f.get("column_index", -1) < len(worksheet.columns)]
        else:
            # Auto-detect numeric non-runorder columns
            reserved = {"stdorder", "runorder", "pttype", "blocks", resp_col.name.casefold()}
            factor_indices = [
                idx for idx, c in enumerate(worksheet.columns)
                if idx != response_index and c.name.casefold() not in reserved and c.kind == "number"
            ]

    if not factor_indices or len(factor_indices) < 2:
        raise ValueError("Definitive Screening Design analysis requires at least 2 factors.")

    if response_index in factor_indices:
        raise ValueError("Response column cannot also be a factor.")

    # Extract aligned rows without missing values
    n_rows = worksheet.row_count
    valid_rows = []
    y_raw = resp_col.values

    factors_meta = []
    for f_idx in factor_indices:
        col = worksheet.columns[f_idx]
        # Check if known metadata has low/high
        f_info = next((f for f in known_factors if f.get("column_index") == f_idx or f.get("name") == col.name), None)
        factors_meta.append({
            "index": f_idx,
            "name": col.name,
            "col": col,
            "low": f_info.get("low") if f_info else None,
            "high": f_info.get("high") if f_info else None,
            "mid": f_info.get("mid") if f_info else None,
            "type": f_info.get("type", "continuous") if f_info else "continuous",
        })

    for r in range(n_rows):
        y_val = y_raw[r]
        if y_val is None or not isinstance(y_val, (int, float)) or not math.isfinite(y_val):
            continue
        row_ok = True
        for fm in factors_meta:
            v = fm["col"].values[r]
            if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
                row_ok = False
                break
        if row_ok:
            valid_rows.append(r)

    n_valid = len(valid_rows)
    if n_valid < len(factor_indices) + 2:
        raise ValueError(f"Insufficient complete observations ({n_valid}) for DSD analysis.")

    Y = np.array([float(y_raw[r]) for r in valid_rows], dtype=float)
    X_orig = np.zeros((n_valid, len(factor_indices)), dtype=float)
    for c_idx, fm in enumerate(factors_meta):
        X_orig[:, c_idx] = [float(fm["col"].values[r]) for r in valid_rows]

    # Code factors to [-1, 0, +1]
    X_coded = np.zeros_like(X_orig)
    coding_info = []
    for c_idx, fm in enumerate(factors_meta):
        col_vals = X_orig[:, c_idx]
        min_v = np.min(col_vals)
        max_v = np.max(col_vals)
        low_v = fm["low"] if fm["low"] is not None else min_v
        high_v = fm["high"] if fm["high"] is not None else max_v
        span = high_v - low_v
        if span <= 1e-12:
            span = 1.0
        mid_v = (low_v + high_v) / 2.0
        coding_info.append({"low": low_v, "high": high_v, "mid": mid_v, "half_span": span / 2.0})
        # Coded = (X - mid) / (span / 2)
        X_coded[:, c_idx] = (col_vals - mid_v) / (span / 2.0)

    k = len(factors_meta)

    # 1. Fit linear main effects model
    # Because DSD main effects are orthogonal, X_ME^T X_ME is diagonal
    X_me = np.column_stack([np.ones(n_valid), X_coded])
    beta_me, residuals_me, rank_me, _ = np.linalg.lstsq(X_me, Y, rcond=None)
    y_pred_me = X_me @ beta_me
    e_me = Y - y_pred_me
    df_e_me = max(1, n_valid - (k + 1))
    s2_me = np.sum(e_me**2) / df_e_me

    # Standard errors of main effects
    diag_inv = np.diag(np.linalg.pinv(X_me.T @ X_me))
    se_me = np.sqrt(np.maximum(1e-14, s2_me * diag_inv))
    t_me = beta_me / np.maximum(1e-14, se_me)
    p_me = 2.0 * (1.0 - stats.t.cdf(np.abs(t_me), df_e_me))

    # Candidate active factors (p-value < alpha_enter or top factors)
    active_factors = []
    for i in range(k):
        # i + 1 corresponds to factor i in X_me
        if p_me[i + 1] <= alpha_enter:
            active_factors.append(i)

    # Ensure at least the top 2 most significant factors are kept if none met alpha_enter
    if len(active_factors) < 2:
        sorted_factors = sorted(range(k), key=lambda idx: p_me[idx + 1])
        active_factors = sorted_factors[:min(3, k)]

    # 2. Build candidate model terms
    # Candidate terms:
    # - Main effects: i
    # - 2-Factor Interactions: (i, j) involving active factors
    # - Curvature / Quadratic: (i, i) for continuous active factors
    candidate_terms = []
    # All main effects always available
    for i in range(k):
        candidate_terms.append(("linear", (i,), factors_meta[i]["name"]))

    if selection in ("stepwise", "full"):
        # 2-factor interactions between active factors or weak heredity
        for i in active_factors:
            for j in range(i + 1, k):
                # Include if both active, or one active under weak heredity
                if selection == "full" or j in active_factors:
                    term_name = f"{factors_meta[i]['name']}*{factors_meta[j]['name']}"
                    candidate_terms.append(("interaction", (i, j), term_name))

        # Quadratic terms for active continuous factors
        for i in active_factors:
            if factors_meta[i]["type"] == "continuous":
                term_name = f"{factors_meta[i]['name']}*{factors_meta[i]['name']}"
                candidate_terms.append(("quadratic", (i, i), term_name))

    # Selected terms
    if selection == "main_effects":
        selected_terms = [t for t in candidate_terms if t[0] == "linear"]
    elif selection == "full":
        selected_terms = list(candidate_terms)
    else:
        # Forward stepwise with heredity
        # Start with significant main effects
        selected_terms = [t for t in candidate_terms if t[0] == "linear" and t[1][0] in active_factors]
        if not selected_terms:
            selected_terms = [t for t in candidate_terms if t[0] == "linear"]

        # Evaluate candidate 2FI and quadratics
        additional_candidates = [t for t in candidate_terms if t[0] in ("interaction", "quadratic")]

        # Forward addition
        max_terms = min(n_valid - 3, len(candidate_terms))
        while len(selected_terms) < max_terms and additional_candidates:
            best_term = None
            best_p = 1.0
            current_x = _build_model_matrix(X_coded, selected_terms, n_valid)

            for cand in additional_candidates:
                test_x = np.column_stack([current_x, _eval_term(X_coded, cand)])
                b, _, _, _ = np.linalg.lstsq(test_x, Y, rcond=None)
                e = Y - test_x @ b
                df_res = max(1, n_valid - test_x.shape[1])
                s2 = np.sum(e**2) / df_res
                cov = np.linalg.pinv(test_x.T @ test_x)
                cand_se = math.sqrt(max(1e-14, s2 * cov[-1, -1]))
                cand_t = b[-1] / max(1e-14, cand_se)
                cand_p = 2.0 * (1.0 - stats.t.cdf(abs(cand_t), df_res))

                if cand_p < best_p:
                    best_p = cand_p
                    best_term = cand

            if best_term and best_p <= alpha_enter:
                selected_terms.append(best_term)
                additional_candidates.remove(best_term)
            else:
                break

    # 3. Final model estimation
    p_terms = len(selected_terms)
    X_final = _build_model_matrix(X_coded, selected_terms, n_valid)
    beta_final, _, rank_final, _ = np.linalg.lstsq(X_final, Y, rcond=None)
    y_pred = X_final @ beta_final
    residuals = Y - y_pred

    n_params = X_final.shape[1]
    df_error = max(1, n_valid - n_params)
    df_total = n_valid - 1
    df_model = n_params - 1

    ss_total = float(np.sum((Y - np.mean(Y))**2))
    ss_error = float(np.sum(residuals**2))
    ss_model = max(0.0, ss_total - ss_error)

    ms_model = ss_model / max(1, df_model)
    ms_error = ss_error / max(1, df_error)
    f_model = (ms_model / ms_error) if ms_error > 1e-14 else 0.0
    p_model = 1.0 - _f_cdf(f_model, df_model, df_error)

    # Standard error of regression and R-squared metrics
    s_reg = math.sqrt(ms_error)
    r2 = (ss_model / ss_total) if ss_total > 1e-14 else 0.0
    r2_adj = 1.0 - (1.0 - r2) * (df_total / max(1, df_error))

    # Hat matrix and PRESS for R-sq pred
    H = X_final @ np.linalg.pinv(X_final.T @ X_final) @ X_final.T
    h_diag = np.diag(H)
    press_residuals = residuals / np.maximum(1e-6, 1.0 - h_diag)
    press = float(np.sum(press_residuals**2))
    r2_pred = max(0.0, 1.0 - (press / ss_total)) if ss_total > 1e-14 else 0.0

    # Covariance and Coded Coefficients
    xtx_inv = np.linalg.pinv(X_final.T @ X_final)
    se_beta = np.sqrt(np.maximum(1e-14, ms_error * np.diag(xtx_inv)))
    t_beta = beta_final / np.maximum(1e-14, se_beta)
    p_beta = 2.0 * (1.0 - stats.t.cdf(np.abs(t_beta), df_error))

    alpha_sig = (100.0 - confidence) / 100.0
    t_crit = _t_ppf(1.0 - alpha_sig / 2.0, df_error)

    # VIF
    vifs = [1.0]  # Intercept
    for j in range(1, n_params):
        if n_params <= 2:
            vifs.append(1.0)
        else:
            # Regress column j on other columns
            xj = X_final[:, j]
            x_others = np.delete(X_final[:, 1:], j - 1, axis=1)
            b_j, _, _, _ = np.linalg.lstsq(np.column_stack([np.ones(n_valid), x_others]), xj, rcond=None)
            r2_j = 1.0 - np.sum((xj - np.column_stack([np.ones(n_valid), x_others]) @ b_j)**2) / max(1e-14, np.sum((xj - np.mean(xj))**2))
            vif_val = 1.0 / max(1e-4, 1.0 - r2_j) if r2_j < 0.9999 else 100.0
            vifs.append(vif_val)

    # Breakdown ANOVA by Source
    ss_linear = 0.0
    df_linear = 0
    ss_2way = 0.0
    df_2way = 0
    ss_quad = 0.0
    df_quad = 0

    term_rows = []
    term_rows.append({
        "term": "Constant",
        "coef": float(beta_final[0]),
        "se": float(se_beta[0]),
        "ci_lower": float(beta_final[0] - t_crit * se_beta[0]),
        "ci_upper": float(beta_final[0] + t_crit * se_beta[0]),
        "t_val": float(t_beta[0]),
        "p_val": float(p_beta[0]),
        "vif": 1.0,
    })

    for idx, term in enumerate(selected_terms):
        t_kind, t_indices, t_name = term
        param_idx = idx + 1
        b_val = float(beta_final[param_idx])
        se_val = float(se_beta[param_idx])
        t_val = float(t_beta[param_idx])
        p_val = float(p_beta[param_idx])
        vif_val = float(vifs[param_idx])

        # Partial SS
        partial_ss = (t_val**2) * ms_error

        if t_kind == "linear":
            ss_linear += partial_ss
            df_linear += 1
        elif t_kind == "interaction":
            ss_2way += partial_ss
            df_2way += 1
        elif t_kind == "quadratic":
            ss_quad += partial_ss
            df_quad += 1

        term_rows.append({
            "term": t_name,
            "coef": b_val,
            "se": se_val,
            "ci_lower": b_val - t_crit * se_val,
            "ci_upper": b_val + t_crit * se_val,
            "t_val": t_val,
            "p_val": p_val,
            "vif": vif_val,
            "type": t_kind,
        })

    # Build ANOVA table rows
    anova_table = [
        {"source": "Model", "df": df_model, "adj_ss": ss_model, "adj_ms": ms_model, "f_val": f_model, "p_val": p_model}
    ]
    if df_linear > 0:
        ms_lin = ss_linear / df_linear
        f_lin = ms_lin / ms_error if ms_error > 1e-14 else 0.0
        p_lin = 1.0 - _f_cdf(f_lin, df_linear, df_error)
        anova_table.append({"source": "  Linear", "df": df_linear, "adj_ss": ss_linear, "adj_ms": ms_lin, "f_val": f_lin, "p_val": p_lin})
    if df_2way > 0:
        ms_2w = ss_2way / df_2way
        f_2w = ms_2w / ms_error if ms_error > 1e-14 else 0.0
        p_2w = 1.0 - _f_cdf(f_2w, df_2way, df_error)
        anova_table.append({"source": "  2-Way Interactions", "df": df_2way, "adj_ss": ss_2way, "adj_ms": ms_2w, "f_val": f_2w, "p_val": p_2w})
    if df_quad > 0:
        ms_q = ss_quad / df_quad
        f_q = ms_q / ms_error if ms_error > 1e-14 else 0.0
        p_q = 1.0 - _f_cdf(f_q, df_quad, df_error)
        anova_table.append({"source": "  Curvature / Quadratic", "df": df_quad, "adj_ss": ss_quad, "adj_ms": ms_q, "f_val": f_q, "p_val": p_q})

    anova_table.append({"source": "Error", "df": df_error, "adj_ss": ss_error, "adj_ms": ms_error, "f_val": None, "p_val": None})
    anova_table.append({"source": "Total", "df": df_total, "adj_ss": ss_total, "adj_ms": None, "f_val": None, "p_val": None})

    # Standardized Effects for Pareto chart
    pareto_effects = []
    for tr in term_rows[1:]:
        pareto_effects.append({
            "term": tr["term"],
            "effect": abs(tr["t_val"]),
            "t_val": tr["t_val"],
            "p_val": tr["p_val"],
        })
    pareto_effects.sort(key=lambda item: item["effect"], reverse=True)

    # Prediction Profiler Model Spec
    profiler_factors = []
    for fm, ci in zip(factors_meta, coding_info):
        profiler_factors.append({
            "name": fm["name"],
            "min": ci["low"],
            "max": ci["high"],
            "current": ci["mid"],
            "type": fm["type"],
        })

    def predict_fn(factor_values: Dict[str, float]) -> float:
        # Code values
        coded_vals = {}
        for fm, ci in zip(factors_meta, coding_info):
            raw_v = factor_values.get(fm["name"], ci["mid"])
            coded_vals[fm["name"]] = (raw_v - ci["mid"]) / ci["half_span"]

        y_eval = beta_final[0]
        for tr_idx, term in enumerate(selected_terms):
            t_kind, t_indices, _ = term
            b = beta_final[tr_idx + 1]
            if t_kind == "linear":
                f_name = factors_meta[t_indices[0]]["name"]
                y_eval += b * coded_vals[f_name]
            elif t_kind == "interaction":
                f1 = factors_meta[t_indices[0]]["name"]
                f2 = factors_meta[t_indices[1]]["name"]
                y_eval += b * coded_vals[f1] * coded_vals[f2]
            elif t_kind == "quadratic":
                f1 = factors_meta[t_indices[0]]["name"]
                y_eval += b * (coded_vals[f1] ** 2)
        return float(y_eval)

    # Build unstandardized regression equation string
    eq_parts = [f"{beta_final[0]:.4g}"]
    for idx, term in enumerate(selected_terms):
        b = beta_final[idx + 1]
        sign = "+" if b >= 0 else "-"
        eq_parts.append(f"{sign} {abs(b):.4g}*{term[2]}")
    equation_str = f"{resp_col.name} = " + " ".join(eq_parts)

    return {
        "analysis": "definitive_screening_analysis",
        "response_name": resp_col.name,
        "response_index": response_index,
        "factor_indices": factor_indices,
        "n_obs": n_valid,
        "s": s_reg,
        "r2": r2,
        "r2_adj": r2_adj,
        "r2_pred": r2_pred,
        "press": press,
        "terms": term_rows,
        "anova": anova_table,
        "pareto_effects": pareto_effects,
        "t_crit": t_crit,
        "confidence": confidence,
        "equation": equation_str,
        "selection": selection,
        "residuals": [float(r) for r in residuals],
        "fitted": [float(f) for f in y_pred],
        "active_factors": [factors_meta[i]["name"] for i in active_factors],
        "profiler_spec": {
            "factors": profiler_factors,
            "response": resp_col.name,
            "predict_fn": predict_fn,
        },
    }


def _build_model_matrix(X_coded: np.ndarray, terms: Sequence[Tuple[str, Tuple[int, ...], str]], n_rows: int) -> np.ndarray:
    cols = [np.ones(n_rows)]
    for term in terms:
        cols.append(_eval_term(X_coded, term))
    return np.column_stack(cols)


def _eval_term(X_coded: np.ndarray, term: Tuple[str, Tuple[int, ...], str]) -> np.ndarray:
    t_kind, t_indices, _ = term
    if t_kind == "linear":
        return X_coded[:, t_indices[0]]
    elif t_kind == "interaction":
        return X_coded[:, t_indices[0]] * X_coded[:, t_indices[1]]
    elif t_kind == "quadratic":
        return X_coded[:, t_indices[0]] ** 2
    raise ValueError(f"Unknown term kind {t_kind}")
