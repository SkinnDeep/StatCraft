"""Computational engine for Stepwise Regression.

Matches Minitab statistical formulas and algorithms:
- Stepwise Selection (Alpha-to-enter, Alpha-to-remove)
- Forward Selection (Alpha-to-enter)
- Backward Elimination (Alpha-to-remove)
- Forward Selection with AIC / BIC
- Backward Elimination with AIC / BIC
- Calculates S, R-sq, R-sq(adj), R-sq(pred), Mallows' Cp, AIC, BIC at each step.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import stats


def clean_stepwise_data(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """Filter rows where response or any predictor is None/NaN."""
    n_rows = len(response)
    p = len(predictors)
    valid_y: List[float] = []
    valid_x: List[List[float]] = []
    valid_indices: List[int] = []

    for i in range(n_rows):
        y_val = response[i]
        if y_val is None:
            continue
        try:
            fy = float(y_val)
            if math.isnan(fy) or math.isinf(fy):
                continue
        except (ValueError, TypeError):
            continue

        row_x: List[float] = []
        row_ok = True
        for j in range(p):
            x_val = predictors[j][i]
            if x_val is None:
                row_ok = False
                break
            try:
                fx = float(x_val)
                if math.isnan(fx) or math.isinf(fx):
                    row_ok = False
                    break
                row_x.append(fx)
            except (ValueError, TypeError):
                row_ok = False
                break

        if row_ok:
            valid_y.append(fy)
            valid_x.append(row_x)
            valid_indices.append(i)

    y_arr = np.asarray(valid_y, dtype=float)
    x_arr = np.asarray(valid_x, dtype=float).reshape(len(valid_y), p)
    return y_arr, x_arr, valid_indices


def _fit_model_step(
    y: np.ndarray,
    x_full: np.ndarray,
    subset_indices: Sequence[int],
    sst: float,
    mse_full: float,
    total_candidate_p: int,
) -> Dict[str, Any]:
    """Fit OLS with intercept for given subset of predictor column indices."""
    n = len(y)
    k = len(subset_indices)
    if k == 0:
        # Intercept-only model
        X = np.ones((n, 1), dtype=float)
    else:
        x_sub = x_full[:, subset_indices]
        X = np.column_stack([np.ones(n, dtype=float), x_sub])

    df_err = n - (k + 1)
    if df_err <= 0:
        raise ValueError("Degrees of freedom for error must be positive.")

    # QR decomposition for numerical stability
    Q, R = np.linalg.qr(X, mode="reduced")
    rank = np.linalg.matrix_rank(R)
    if rank < k + 1:
        raise np.linalg.LinAlgError("Singular matrix encountered.")

    coef = np.linalg.solve(R, Q.T @ y)
    fitted = X @ coef
    res = y - fitted
    sse = float(np.sum(res ** 2))
    mse = sse / df_err if df_err > 0 else float("nan")
    s = math.sqrt(max(0.0, mse))

    # Variance-covariance matrix of coefficients: (X^T X)^{-1} * MSE = (R^T R)^{-1} * MSE
    R_inv = np.linalg.inv(R)
    cov = (R_inv @ R_inv.T) * mse
    se_coef = np.sqrt(np.maximum(0.0, np.diag(cov)))

    t_values = np.zeros(k + 1, dtype=float)
    p_values = np.zeros(k + 1, dtype=float)
    for i in range(k + 1):
        if se_coef[i] > 1e-12:
            t_values[i] = coef[i] / se_coef[i]
            p_values[i] = 2.0 * float(stats.t.sf(abs(t_values[i]), df_err))
        else:
            t_values[i] = 0.0
            p_values[i] = 1.0

    # Model metrics
    r_sq = (1.0 - sse / sst) * 100.0 if sst > 1e-12 else 0.0
    r_sq_adj = (1.0 - (sse / df_err) / (sst / (n - 1))) * 100.0 if sst > 1e-12 and n > 1 else 0.0

    # PRESS and R-sq(pred)
    # h_ii = sum(Q[i, :] ** 2)
    h = np.sum(Q ** 2, axis=1)
    denom = np.maximum(1e-8, 1.0 - h)
    press_residuals = res / denom
    press = float(np.sum(press_residuals ** 2))
    r_sq_pred = max(0.0, (1.0 - press / sst) * 100.0) if sst > 1e-12 else 0.0

    # Mallows' Cp: SSE_p / MSE_full - (n - 2*(p + 1))
    if mse_full > 1e-12:
        mallows_cp = (sse / mse_full) - (n - 2 * (k + 1))
    else:
        mallows_cp = float(k + 1)

    # Information criteria (Minitab formulation)
    # AIC = 2*(k + 2) + n * ln(sse / n)
    # BIC = ln(n)*(k + 2) + n * ln(sse / n)
    log_sse = math.log(max(1e-12, sse / n))
    aic = 2.0 * (k + 2) + n * log_sse
    bic = math.log(n) * (k + 2) + n * log_sse

    return {
        "k": k,
        "coef": coef,
        "se_coef": se_coef,
        "t_values": t_values,
        "p_values": p_values,
        "sse": sse,
        "df_err": df_err,
        "mse": mse,
        "s": s,
        "r_sq": r_sq,
        "r_sq_adj": r_sq_adj,
        "r_sq_pred": r_sq_pred,
        "press": press,
        "mallows_cp": mallows_cp,
        "aic": aic,
        "bic": bic,
        "fitted": fitted,
        "residuals": res,
    }


def stepwise_regression(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
    predictor_names: Optional[Sequence[str]] = None,
    response_name: str = "Y",
    method: str = "stepwise",
    alpha_to_enter: float = 0.15,
    alpha_to_remove: float = 0.15,
    forced_indices: Optional[Sequence[int]] = None,
    max_steps: int = 100,
) -> Dict[str, Any]:
    """Perform Stepwise / Forward / Backward regression matching Minitab.
    
    Supported methods:
      - 'stepwise': Stepwise selection using alpha-to-enter and alpha-to-remove
      - 'forward': Forward selection using alpha-to-enter
      - 'backward': Backward elimination using alpha-to-remove
      - 'forward_aic': Forward selection using AIC
      - 'forward_bic': Forward selection using BIC
      - 'backward_aic': Backward elimination using AIC
      - 'backward_bic': Backward elimination using BIC
    """
    p_total = len(predictors)
    if p_total == 0:
        raise ValueError("At least one candidate predictor is required.")

    if predictor_names is None:
        p_names = [f"X{i+1}" for i in range(p_total)]
    else:
        p_names = list(predictor_names)
        if len(p_names) != p_total:
            raise ValueError("predictor_names count must match predictors count.")

    y, X, valid_indices = clean_stepwise_data(response, predictors)
    n = len(y)
    if n < p_total + 2 and method.startswith("backward"):
        raise ValueError(f"Need at least {p_total + 2} observations to fit full model for backward elimination.")
    if n < 3:
        raise ValueError("At least 3 valid observations required for regression.")

    mean_y = float(np.mean(y))
    sst = float(np.sum((y - mean_y) ** 2))
    if sst < 1e-12:
        raise ValueError("Response variable has zero variance.")

    # Fit full model to compute MSE_full for Mallows' Cp
    try:
        full_res = _fit_model_step(y, X, list(range(p_total)), sst, 1.0, p_total)
        mse_full = full_res["mse"]
    except Exception:
        mse_full = sst / max(1, n - 1)

    forced = set(forced_indices) if forced_indices is not None else set()
    current_terms: List[int] = sorted(list(forced))

    if method.startswith("backward"):
        # Start with all candidate predictors
        current_terms = list(range(p_total))

    method = method.lower()
    valid_methods = (
        "stepwise",
        "forward",
        "backward",
        "forward_aic",
        "forward_bic",
        "backward_aic",
        "backward_bic",
    )
    if method not in valid_methods:
        raise ValueError(f"Unknown stepwise method '{method}'. Valid options: {valid_methods}")

    steps: List[Dict[str, Any]] = []

    def _record_step(step_num: int, action: str, term_name: Optional[str], fit_info: Dict[str, Any]) -> None:
        coef_dict = {}
        # Intercept is index 0
        coef_dict["Constant"] = {
            "coef": float(fit_info["coef"][0]),
            "se": float(fit_info["se_coef"][0]),
            "t_value": float(fit_info["t_values"][0]),
            "p_value": float(fit_info["p_values"][0]),
        }
        for idx_pos, var_idx in enumerate(current_terms):
            coef_pos = idx_pos + 1
            var_name = p_names[var_idx]
            coef_dict[var_name] = {
                "coef": float(fit_info["coef"][coef_pos]),
                "se": float(fit_info["se_coef"][coef_pos]),
                "t_value": float(fit_info["t_values"][coef_pos]),
                "p_value": float(fit_info["p_values"][coef_pos]),
            }

        step_record = {
            "step": step_num,
            "action": action,
            "term": term_name,
            "terms": [p_names[i] for i in current_terms],
            "term_indices": list(current_terms),
            "coefficients": coef_dict,
            "s": float(fit_info["s"]),
            "r_sq": float(fit_info["r_sq"]),
            "r_sq_adj": float(fit_info["r_sq_adj"]),
            "r_sq_pred": float(fit_info["r_sq_pred"]),
            "mallows_cp": float(fit_info["mallows_cp"]),
            "aic": float(fit_info["aic"]),
            "bic": float(fit_info["bic"]),
            "fit_info": fit_info,
        }
        steps.append(step_record)

    # Initial baseline fit
    current_fit = _fit_model_step(y, X, current_terms, sst, mse_full, p_total)
    if method.startswith("backward") or len(current_terms) > 0:
        _record_step(1, "Initial", None, current_fit)

    step_count = len(steps)
    visited_states = set()

    while step_count < max_steps:
        state_key = tuple(sorted(current_terms))
        if state_key in visited_states and method == "stepwise":
            # Cycle detected
            break
        visited_states.add(state_key)

        made_change = False

        if method in ("stepwise", "forward"):
            # Try to add best candidate
            candidates = [i for i in range(p_total) if i not in current_terms]
            best_candidate = None
            best_p = 1.0
            best_fit = None

            for cand in candidates:
                test_terms = sorted(current_terms + [cand])
                try:
                    fit_cand = _fit_model_step(y, X, test_terms, sst, mse_full, p_total)
                    # p-value of candidate is at position test_terms.index(cand) + 1
                    pos = test_terms.index(cand) + 1
                    p_val = fit_cand["p_values"][pos]
                    if p_val < best_p:
                        best_p = p_val
                        best_candidate = cand
                        best_fit = fit_cand
                except (np.linalg.LinAlgError, ValueError):
                    continue

            if best_candidate is not None and best_p < alpha_to_enter:
                current_terms = sorted(current_terms + [best_candidate])
                current_fit = best_fit
                step_count += 1
                _record_step(step_count, "Add", p_names[best_candidate], current_fit)
                made_change = True

            # In stepwise mode, also check for removal after addition
            if method == "stepwise" and len(current_terms) > 0:
                worst_var = None
                worst_p = -1.0
                for idx_pos, var_idx in enumerate(current_terms):
                    if var_idx in forced:
                        continue
                    p_val = current_fit["p_values"][idx_pos + 1]
                    if p_val > worst_p:
                        worst_p = p_val
                        worst_var = var_idx

                if worst_var is not None and worst_p > alpha_to_remove:
                    current_terms = [i for i in current_terms if i != worst_var]
                    current_fit = _fit_model_step(y, X, current_terms, sst, mse_full, p_total)
                    step_count += 1
                    _record_step(step_count, "Remove", p_names[worst_var], current_fit)
                    made_change = True

        elif method == "backward":
            # Find worst variable to remove
            worst_var = None
            worst_p = -1.0
            for idx_pos, var_idx in enumerate(current_terms):
                if var_idx in forced:
                    continue
                p_val = current_fit["p_values"][idx_pos + 1]
                if p_val > worst_p:
                    worst_p = p_val
                    worst_var = var_idx

            if worst_var is not None and worst_p > alpha_to_remove:
                current_terms = [i for i in current_terms if i != worst_var]
                current_fit = _fit_model_step(y, X, current_terms, sst, mse_full, p_total)
                step_count += 1
                _record_step(step_count, "Remove", p_names[worst_var], current_fit)
                made_change = True

        elif method in ("forward_aic", "forward_bic"):
            criterion = "aic" if method == "forward_aic" else "bic"
            current_crit = current_fit[criterion]
            candidates = [i for i in range(p_total) if i not in current_terms]
            best_candidate = None
            best_crit = current_crit
            best_fit = None

            for cand in candidates:
                test_terms = sorted(current_terms + [cand])
                try:
                    fit_cand = _fit_model_step(y, X, test_terms, sst, mse_full, p_total)
                    if fit_cand[criterion] < best_crit:
                        best_crit = fit_cand[criterion]
                        best_candidate = cand
                        best_fit = fit_cand
                except (np.linalg.LinAlgError, ValueError):
                    continue

            if best_candidate is not None and best_crit < current_crit:
                current_terms = sorted(current_terms + [best_candidate])
                current_fit = best_fit
                step_count += 1
                _record_step(step_count, "Add", p_names[best_candidate], current_fit)
                made_change = True

        elif method in ("backward_aic", "backward_bic"):
            criterion = "aic" if method == "backward_aic" else "bic"
            current_crit = current_fit[criterion]
            removable = [i for i in current_terms if i not in forced]
            best_to_remove = None
            best_crit = current_crit
            best_fit = None

            for var_idx in removable:
                test_terms = [i for i in current_terms if i != var_idx]
                try:
                    fit_cand = _fit_model_step(y, X, test_terms, sst, mse_full, p_total)
                    if fit_cand[criterion] < best_crit:
                        best_crit = fit_cand[criterion]
                        best_to_remove = var_idx
                        best_fit = fit_cand
                except (np.linalg.LinAlgError, ValueError):
                    continue

            if best_to_remove is not None and best_crit < current_crit:
                current_terms = [i for i in current_terms if i != best_to_remove]
                current_fit = best_fit
                step_count += 1
                _record_step(step_count, "Remove", p_names[best_to_remove], current_fit)
                made_change = True

        if not made_change:
            break

    # If no steps were recorded yet (e.g. initial forward had no addition), record baseline
    if len(steps) == 0:
        _record_step(1, "Initial", None, current_fit)

    # Build final model summary
    k_final = len(current_terms)
    df_reg = k_final
    ss_reg = sst - current_fit["sse"]
    ms_reg = ss_reg / df_reg if df_reg > 0 else 0.0
    f_reg = ms_reg / current_fit["mse"] if current_fit["mse"] > 1e-12 else float("nan")
    p_reg = float(stats.f.sf(f_reg, df_reg, current_fit["df_err"])) if df_reg > 0 else 1.0

    anova = [
        {"source": "Regression", "df": df_reg, "ss": ss_reg, "ms": ms_reg, "f": f_reg, "p": p_reg},
        {"source": "Error", "df": current_fit["df_err"], "ss": current_fit["sse"], "ms": current_fit["mse"], "f": None, "p": None},
        {"source": "Total", "df": n - 1, "ss": sst, "ms": sst / max(1, n - 1), "f": None, "p": None},
    ]

    return {
        "analysis": "stepwise_regression",
        "response_name": response_name,
        "all_predictor_names": p_names,
        "selected_terms": [p_names[i] for i in current_terms],
        "selected_indices": list(current_terms),
        "method": method,
        "alpha_to_enter": alpha_to_enter,
        "alpha_to_remove": alpha_to_remove,
        "n_obs": n,
        "steps": steps,
        "final_fit": current_fit,
        "anova": anova,
        "s": current_fit["s"],
        "r_sq": current_fit["r_sq"],
        "r_sq_adj": current_fit["r_sq_adj"],
        "r_sq_pred": current_fit["r_sq_pred"],
        "mallows_cp": current_fit["mallows_cp"],
        "aic": current_fit["aic"],
        "bic": current_fit["bic"],
        "title": f"Stepwise Regression: {response_name} versus {', '.join(p_names)}",
    }
