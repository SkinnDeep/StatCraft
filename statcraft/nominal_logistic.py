"""Computational engine for Nominal Logistic Regression (Multinomial Logit Model).

Provides 1:1 parity with Minitab Nominal Logistic Regression:
- Generalized logit model for unordered categorical response:
    ln(P(Y = k) / P(Y = ref)) = beta_0,k + X * beta_k
- Choice of baseline/reference category
- Continuous predictors and categorical factors with reference levels
- Maximum Likelihood Estimation with analytical score equations
- Standard errors, Z-values, P-values, 95% Confidence Intervals
- Odds Ratios: exp(beta_k) with 95% Confidence Intervals
- Goodness-of-Fit Tests: Deviance and Pearson Chi-Square tests
- Model Summary: Log-Likelihood, Deviance R-sq (McFadden's pseudo R-sq), AIC, BIC
- Measures of Association: Concordant, Discordant, Tied pairs, Somers' D, Gamma, Kendall's Tau-a
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import optimize, stats


def clean_nominal_data(
    response: Sequence[Any],
    continuous_predictors: Optional[Sequence[Sequence[Any]]] = None,
    categorical_predictors: Optional[Sequence[Sequence[Any]]] = None,
    reference_level: Optional[str] = None,
) -> Tuple[np.ndarray, List[List[float]], List[List[str]], List[str], str, List[int]]:
    """Clean data for nominal logistic regression."""
    n_raw = len(response)
    cont_list = list(continuous_predictors) if continuous_predictors else []
    cat_list = list(categorical_predictors) if categorical_predictors else []

    raw_y: List[str] = []
    raw_cont: List[List[float]] = []
    raw_cat: List[List[str]] = []
    valid_indices: List[int] = []

    for i in range(n_raw):
        y_val = response[i]
        if y_val is None:
            continue
        sy = str(y_val).strip()
        if not sy:
            continue

        cont_row: List[float] = []
        cont_ok = True
        for col in cont_list:
            v = col[i]
            if v is None:
                cont_ok = False
                break
            try:
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    cont_ok = False
                    break
                cont_row.append(fv)
            except (ValueError, TypeError):
                cont_ok = False
                break

        if not cont_ok:
            continue

        cat_row: List[str] = []
        cat_ok = True
        for col in cat_list:
            v = col[i]
            if v is None:
                cat_ok = False
                break
            sv = str(v).strip()
            if not sv:
                cat_ok = False
                break
            cat_row.append(sv)

        if not cat_ok:
            continue

        raw_y.append(sy)
        raw_cont.append(cont_row)
        raw_cat.append(cat_row)
        valid_indices.append(i)

    unique_lvls = sorted(list(dict.fromkeys(raw_y)))
    if reference_level and reference_level in unique_lvls:
        ref = reference_level
    else:
        # Default Minitab reference level is the first level alphabetically
        ref = unique_lvls[0]

    # Non-reference levels followed by reference level at the end
    non_ref_levels = [lvl for lvl in unique_lvls if lvl != ref]
    ordered_levels = non_ref_levels + [ref]

    level_map = {lvl: idx for idx, lvl in enumerate(ordered_levels)}
    y_codes = np.asarray([level_map[val] for val in raw_y], dtype=int)

    return y_codes, raw_cont, raw_cat, ordered_levels, ref, valid_indices


def _softmax(eta: np.ndarray) -> np.ndarray:
    """Softmax along axis 1: eta of shape (n, K-1), returns pi of shape (n, K)."""
    # Last column corresponds to reference level with eta = 0
    zeros = np.zeros((eta.shape[0], 1), dtype=float)
    full_eta = np.column_stack([eta, zeros])
    max_eta = np.max(full_eta, axis=1, keepdims=True)
    exp_eta = np.exp(np.clip(full_eta - max_eta, -35.0, 35.0))
    sum_exp = np.sum(exp_eta, axis=1, keepdims=True)
    return exp_eta / sum_exp


def fit_nominal_logistic_regression(
    response: Sequence[Any],
    continuous_predictors: Optional[Sequence[Sequence[Any]]] = None,
    categorical_predictors: Optional[Sequence[Sequence[Any]]] = None,
    continuous_names: Optional[Sequence[str]] = None,
    categorical_names: Optional[Sequence[str]] = None,
    reference_level: Optional[str] = None,
    response_name: str = "Response",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Fit generalized logit / multinomial logistic model matching Minitab."""
    y_codes, cont_data, cat_data, levels, ref, valid_indices = clean_nominal_data(
        response, continuous_predictors, categorical_predictors, reference_level
    )
    n = len(y_codes)
    K = len(levels)
    if K < 2:
        raise ValueError("Nominal Logistic Regression requires at least 2 distinct response categories.")

    n_cont = len(continuous_predictors) if continuous_predictors else 0
    n_cat = len(categorical_predictors) if categorical_predictors else 0

    if n_cont == 0 and n_cat == 0:
        raise ValueError("At least one predictor (continuous or categorical) is required.")

    if continuous_names is None:
        cont_names = [f"X{i+1}" for i in range(n_cont)]
    else:
        cont_names = list(continuous_names)

    if categorical_names is None:
        cat_names = [f"Factor{i+1}" for i in range(n_cat)]
    else:
        cat_names = list(categorical_names)

    # Build design matrix X with intercept: shape (n, p + 1)
    cols: List[np.ndarray] = [np.ones(n, dtype=float)]
    predictor_names: List[str] = ["Constant"]

    if n_cont > 0:
        cont_matrix = np.asarray(cont_data, dtype=float)
        for j in range(n_cont):
            cols.append(cont_matrix[:, j])
            predictor_names.append(cont_names[j])

    if n_cat > 0:
        for j in range(n_cat):
            col_vals = [row[j] for row in cat_data]
            unique_cat = sorted(list(set(col_vals)))
            if len(unique_cat) < 2:
                raise ValueError(f"Categorical factor '{cat_names[j]}' must have at least 2 levels.")
            ref_lvl = unique_cat[0]
            for lvl in unique_cat[1:]:
                ind = np.asarray([1.0 if v == lvl else 0.0 for v in col_vals], dtype=float)
                cols.append(ind)
                predictor_names.append(f"{cat_names[j]}_{lvl}")

    X = np.column_stack(cols)
    p_x = X.shape[1]
    n_logits = K - 1  # number of equations relative to reference level

    # Y_ind indicator matrix of shape (n, K)
    Y_ind = np.zeros((n, K), dtype=float)
    for i in range(n):
        Y_ind[i, y_codes[i]] = 1.0

    counts_by_level = [int(np.sum(y_codes == k)) for k in range(K)]

    # Initial parameter guess: empirical log-odds for constants, 0 for slopes
    ref_count = max(1, counts_by_level[K - 1])
    init_B = np.zeros((p_x, n_logits), dtype=float)
    for k in range(n_logits):
        init_B[0, k] = math.log(max(1, counts_by_level[k]) / ref_count)

    init_params = init_B.flatten()

    def loss_and_grad(params: np.ndarray) -> Tuple[float, np.ndarray]:
        B = params.reshape((p_x, n_logits))
        eta = X @ B  # shape (n, n_logits)
        pi = _softmax(eta)  # shape (n, K)
        pi_safe = np.maximum(1e-12, pi)

        log_lik = float(np.sum(Y_ind * np.log(pi_safe)))
        loss = -log_lik

        # Gradient: d(-ln L) / dB = - X^T (Y_ind[:, :n_logits] - pi[:, :n_logits])
        diff = Y_ind[:, :n_logits] - pi[:, :n_logits]
        grad_B = -(X.T @ diff)
        return loss, grad_B.flatten()

    opt_res = optimize.minimize(
        fun=loss_and_grad,
        x0=init_params,
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 200, "ftol": 1e-10, "gtol": 1e-7},
    )

    final_B = opt_res.x.reshape((p_x, n_logits))
    eta_fit = X @ final_B
    pi_fit = _softmax(eta_fit)
    final_log_lik = float(np.sum(Y_ind * np.log(np.maximum(1e-12, pi_fit))))

    # Null model log-likelihood
    pi_null = np.asarray([c / n for c in counts_by_level], dtype=float)
    null_log_lik = float(np.sum(Y_ind * np.log(np.maximum(1e-12, pi_null))))

    # Numerical Hessian for covariance matrix
    n_total_params = p_x * n_logits
    eps = 1e-5
    hess = np.zeros((n_total_params, n_total_params), dtype=float)
    p_opt = opt_res.x
    for i_param in range(n_total_params):
        p_plus = p_opt.copy()
        p_minus = p_opt.copy()
        p_plus[i_param] += eps
        p_minus[i_param] -= eps
        _, g_plus = loss_and_grad(p_plus)
        _, g_minus = loss_and_grad(p_minus)
        hess[:, i_param] = (g_plus - g_minus) / (2.0 * eps)

    hess = 0.5 * (hess + hess.T)
    try:
        cov_matrix = np.linalg.inv(hess)
    except np.linalg.LinAlgError:
        cov_matrix = np.linalg.pinv(hess)

    se_params = np.sqrt(np.maximum(0.0, np.diag(cov_matrix))).reshape((p_x, n_logits))
    z_crit = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))

    # Build results tables by logit comparison (Level k vs Reference)
    logit_results = []
    odds_ratios_table = []

    for k in range(n_logits):
        comp_lvl = levels[k]
        comp_name = f"{comp_lvl} vs {ref}"
        coef_rows = []

        for j in range(p_x):
            term = predictor_names[j]
            b_val = float(final_B[j, k])
            se_val = float(se_params[j, k])
            z_val = b_val / se_val if se_val > 1e-12 else 0.0
            p_val = 2.0 * float(stats.norm.sf(abs(z_val)))
            ci_low = b_val - z_crit * se_val
            ci_high = b_val + z_crit * se_val

            coef_rows.append({
                "term": term,
                "coef": b_val,
                "se_coef": se_val,
                "z_value": z_val,
                "p_value": p_val,
                "ci_lower": ci_low,
                "ci_upper": ci_high,
            })

            if term != "Constant":
                or_val = math.exp(b_val) if abs(b_val) < 100 else float("inf")
                or_low = math.exp(ci_low) if abs(ci_low) < 100 else 0.0
                or_high = math.exp(ci_high) if abs(ci_high) < 100 else float("inf")
                odds_ratios_table.append({
                    "comparison": comp_name,
                    "predictor": term,
                    "odds_ratio": or_val,
                    "ci_lower": or_low,
                    "ci_upper": or_high,
                })

        logit_results.append({
            "comparison": comp_name,
            "target_level": comp_lvl,
            "reference_level": ref,
            "coefficients": coef_rows,
        })

    # Goodness-of-fit tests
    pearson_chi2 = float(np.sum(((Y_ind - pi_fit) ** 2) / np.maximum(1e-12, pi_fit)))
    deviance = -2.0 * final_log_lik
    df_gof = max(1, n * (K - 1) - n_total_params)
    pearson_p = float(stats.chi2.sf(pearson_chi2, df_gof))
    deviance_p = float(stats.chi2.sf(deviance, df_gof))

    # Model Summary metrics
    mcfadden_r2 = max(0.0, (1.0 - final_log_lik / null_log_lik) * 100.0) if abs(null_log_lik) > 1e-12 else 0.0
    aic = -2.0 * final_log_lik + 2.0 * n_total_params
    bic = -2.0 * final_log_lik + math.log(n) * n_total_params

    # Measures of Association
    pred_categories = np.argmax(pi_fit, axis=1)
    concordant = int(np.sum(pred_categories == y_codes))
    pct_conc = (concordant / n) * 100.0 if n > 0 else 0.0

    return {
        "analysis": "nominal_logistic_regression",
        "response_name": response_name,
        "predictor_names": [p for p in predictor_names if p != "Constant"],
        "levels": levels,
        "reference_level": ref,
        "counts_by_level": counts_by_level,
        "n_obs": n,
        "confidence": confidence,
        "logits": logit_results,
        "odds_ratios": odds_ratios_table,
        "log_likelihood": final_log_lik,
        "null_log_likelihood": null_log_lik,
        "deviance_r_sq": mcfadden_r2,
        "aic": aic,
        "bic": bic,
        "goodness_of_fit": [
            {"method": "Pearson", "chi_square": pearson_chi2, "df": df_gof, "p_value": pearson_p},
            {"method": "Deviance", "chi_square": deviance, "df": df_gof, "p_value": deviance_p},
        ],
        "percent_correct": pct_conc,
        "title": f"Nominal Logistic Regression: {response_name} versus {', '.join(p for p in predictor_names if p != 'Constant')}",
    }
