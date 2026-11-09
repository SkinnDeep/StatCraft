"""Computational engine for Ordinal Logistic Regression.

Provides 1:1 parity with Minitab Ordinal Logistic Regression:
- Proportional odds cumulative logit model:
    ln(P(Y <= k) / P(Y > k)) = theta_k - X*beta
- Ordered response with K >= 2 categories
- Continuous predictors and categorical factors with reference levels
- Maximum Likelihood Estimation via Fisher / BFGS with analytical gradients
- Parameter estimates: Thresholds (theta_1, ..., theta_{K-1}) and Slopes (beta_1, ..., beta_p)
- Standard errors, Z-values, P-values, 95% Confidence Intervals
- Odds Ratios: exp(beta) with 95% Confidence Intervals
- Goodness-of-Fit Tests: Deviance and Pearson Chi-Square tests
- Measures of Association: Concordant, Discordant, Tied pairs, Somers' D, Gamma, Kendall's Tau-a
- Model Summary: Log-Likelihood, Deviance R-sq (McFadden's pseudo R-sq), AIC, BIC
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import optimize, stats


def clean_ordinal_data(
    response: Sequence[Any],
    continuous_predictors: Optional[Sequence[Sequence[Any]]] = None,
    categorical_predictors: Optional[Sequence[Sequence[Any]]] = None,
    ordered_levels: Optional[Sequence[Any]] = None,
) -> Tuple[np.ndarray, List[List[float]], List[List[str]], List[str], List[int]]:
    """Clean and validate data for ordinal logistic regression."""
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

    if ordered_levels:
        distinct_levels = [str(x).strip() for x in ordered_levels]
    else:
        # Sort naturally or numerically if all are numbers
        unique_vals = list(dict.fromkeys(raw_y))
        try:
            distinct_levels = sorted(unique_vals, key=lambda v: float(v))
        except ValueError:
            distinct_levels = sorted(unique_vals)

    level_map = {lvl: idx for idx, lvl in enumerate(distinct_levels)}
    y_codes = np.asarray([level_map[val] for val in raw_y], dtype=int)

    return y_codes, raw_cont, raw_cat, distinct_levels, valid_indices


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))


def fit_ordinal_logistic_regression(
    response: Sequence[Any],
    continuous_predictors: Optional[Sequence[Sequence[Any]]] = None,
    categorical_predictors: Optional[Sequence[Sequence[Any]]] = None,
    continuous_names: Optional[Sequence[str]] = None,
    categorical_names: Optional[Sequence[str]] = None,
    ordered_levels: Optional[Sequence[Any]] = None,
    response_name: str = "Response",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Fit proportional odds cumulative logit model matching Minitab."""
    y_codes, cont_data, cat_data, levels, valid_indices = clean_ordinal_data(
        response, continuous_predictors, categorical_predictors, ordered_levels
    )
    n = len(y_codes)
    K = len(levels)
    if K < 2:
        raise ValueError("Ordinal Logistic Regression requires at least 2 distinct response categories.")

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

    # Build design matrix X (without intercept, thresholds act as cutpoints)
    predictor_names: List[str] = []
    cols: List[np.ndarray] = []

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
    p = X.shape[1]
    n_cutpoints = K - 1

    # Response counts
    counts_by_level = [int(np.sum(y_codes == k)) for k in range(K)]

    # Initial parameter guesses
    # Set initial thresholds using empirical cumulative log-odds
    cum_counts = np.cumsum(counts_by_level)
    initial_theta = []
    for k in range(n_cutpoints):
        prop = max(0.01, min(0.99, cum_counts[k] / n))
        initial_theta.append(float(np.log(prop / (1.0 - prop))))

    # Ensure strictly increasing
    for k in range(1, n_cutpoints):
        if initial_theta[k] <= initial_theta[k - 1]:
            initial_theta[k] = initial_theta[k - 1] + 0.5

    init_params = np.concatenate([initial_theta, np.zeros(p, dtype=float)])

    # Indicator matrix for categories: Y_ind of shape (n, K)
    Y_ind = np.zeros((n, K), dtype=float)
    for i in range(n):
        Y_ind[i, y_codes[i]] = 1.0

    # Negative log-likelihood function and gradient
    def loss_and_grad(params: np.ndarray) -> Tuple[float, np.ndarray]:
        theta = params[:n_cutpoints]
        beta = params[n_cutpoints:]

        # Enforce order on theta during optimization via penalty if needed
        penalty = 0.0
        grad_penalty = np.zeros_like(params)
        for k in range(n_cutpoints - 1):
            diff = theta[k] - theta[k + 1]
            if diff > -1e-4:
                viol = diff + 1e-4
                penalty += 1000.0 * (viol ** 2)
                grad_penalty[k] += 2000.0 * viol
                grad_penalty[k + 1] -= 2000.0 * viol

        # x_beta of shape (n,)
        x_beta = X @ beta

        # Cumulative probabilities F of shape (n, K-1)
        # F[:, k] = P(Y <= k) = sigmoid(theta[k] - x_beta)
        F = np.zeros((n, n_cutpoints), dtype=float)
        f_dens = np.zeros((n, n_cutpoints), dtype=float)
        for k in range(n_cutpoints):
            z = theta[k] - x_beta
            F[:, k] = _sigmoid(z)
            f_dens[:, k] = F[:, k] * (1.0 - F[:, k])

        # Category probabilities pi of shape (n, K)
        pi = np.zeros((n, K), dtype=float)
        pi[:, 0] = F[:, 0]
        for k in range(1, n_cutpoints):
            pi[:, k] = np.maximum(1e-12, F[:, k] - F[:, k - 1])
        pi[:, K - 1] = np.maximum(1e-12, 1.0 - F[:, n_cutpoints - 1])
        pi = np.maximum(1e-12, pi)

        # Log-likelihood
        log_lik = float(np.sum(Y_ind * np.log(pi)))
        loss = -log_lik + penalty

        # Gradients
        grad = np.zeros_like(params)
        # d(-ln L) / d(theta_m)
        for m in range(n_cutpoints):
            # d(pi_m) / d(theta_m) = f_m
            # d(pi_{m+1}) / d(theta_m) = -f_m
            t_grad = (Y_ind[:, m] / pi[:, m] - Y_ind[:, m + 1] / pi[:, m + 1]) * f_dens[:, m]
            grad[m] = -float(np.sum(t_grad))

        # d(-ln L) / d(beta_j)
        # d(pi_k) / d(beta) = -X * (f_k - f_{k-1})
        f_diff = np.zeros((n, K), dtype=float)
        f_diff[:, 0] = f_dens[:, 0]
        for k in range(1, n_cutpoints):
            f_diff[:, k] = f_dens[:, k] - f_dens[:, k - 1]
        f_diff[:, K - 1] = -f_dens[:, n_cutpoints - 1]

        # term_i = sum_k (Y_ind[:, k] / pi[:, k]) * f_diff[:, k]
        weighted_f = np.sum((Y_ind / pi) * f_diff, axis=1)  # shape (n,)
        # grad_beta = X^T @ weighted_f
        grad[n_cutpoints:] = float(1.0) * (X.T @ weighted_f)

        return loss, grad + grad_penalty

    # Optimize using L-BFGS-B
    opt_res = optimize.minimize(
        fun=loss_and_grad,
        x0=init_params,
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 200, "ftol": 1e-10, "gtol": 1e-7},
    )

    opt_params = opt_res.x
    final_theta = opt_params[:n_cutpoints]
    final_beta = opt_params[n_cutpoints:]

    # Compute fitted probabilities
    x_beta = X @ final_beta
    F = np.zeros((n, n_cutpoints), dtype=float)
    for k in range(n_cutpoints):
        F[:, k] = _sigmoid(final_theta[k] - x_beta)

    pi_fit = np.zeros((n, K), dtype=float)
    pi_fit[:, 0] = F[:, 0]
    for k in range(1, n_cutpoints):
        pi_fit[:, k] = np.maximum(1e-12, F[:, k] - F[:, k - 1])
    pi_fit[:, K - 1] = np.maximum(1e-12, 1.0 - F[:, n_cutpoints - 1])
    pi_fit = np.maximum(1e-12, pi_fit)

    final_log_lik = float(np.sum(Y_ind * np.log(pi_fit)))

    # Null model log-likelihood (thresholds only)
    pi_null = np.asarray([c / n for c in counts_by_level], dtype=float)
    null_log_lik = float(np.sum(Y_ind * np.log(np.maximum(1e-12, pi_null))))

    # Compute Hessian numerically for standard errors
    eps = 1e-5
    n_total_params = n_cutpoints + p
    hess = np.zeros((n_total_params, n_total_params), dtype=float)
    for i_param in range(n_total_params):
        p_plus = opt_params.copy()
        p_minus = opt_params.copy()
        p_plus[i_param] += eps
        p_minus[i_param] -= eps
        _, g_plus = loss_and_grad(p_plus)
        _, g_minus = loss_and_grad(p_minus)
        hess[:, i_param] = (g_plus - g_minus) / (2.0 * eps)

    # Symmetrize Hessian
    hess = 0.5 * (hess + hess.T)
    try:
        cov_matrix = np.linalg.inv(hess)
    except np.linalg.LinAlgError:
        cov_matrix = np.linalg.pinv(hess)

    se_params = np.sqrt(np.maximum(0.0, np.diag(cov_matrix)))
    z_crit = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))

    # Build Coefficients table
    coef_table = []
    # Thresholds
    for k in range(n_cutpoints):
        t_val = float(final_theta[k])
        se_val = float(se_params[k])
        z_val = t_val / se_val if se_val > 1e-12 else 0.0
        p_val = 2.0 * float(stats.norm.sf(abs(z_val)))
        coef_table.append({
            "term": f"Const({k+1})",
            "coef": t_val,
            "se_coef": se_val,
            "z_value": z_val,
            "p_value": p_val,
            "ci_lower": t_val - z_crit * se_val,
            "ci_upper": t_val + z_crit * se_val,
            "is_threshold": True,
        })

    # Slopes
    odds_ratios_table = []
    for j in range(p):
        idx_p = n_cutpoints + j
        b_val = float(final_beta[j])
        se_val = float(se_params[idx_p])
        z_val = b_val / se_val if se_val > 1e-12 else 0.0
        p_val = 2.0 * float(stats.norm.sf(abs(z_val)))
        ci_low = b_val - z_crit * se_val
        ci_high = b_val + z_crit * se_val

        coef_table.append({
            "term": predictor_names[j],
            "coef": b_val,
            "se_coef": se_val,
            "z_value": z_val,
            "p_value": p_val,
            "ci_lower": ci_low,
            "ci_upper": ci_high,
            "is_threshold": False,
        })

        # Odds Ratio = exp(beta)
        or_val = math.exp(b_val) if abs(b_val) < 100 else float("inf")
        or_low = math.exp(ci_low) if abs(ci_low) < 100 else 0.0
        or_high = math.exp(ci_high) if abs(ci_high) < 100 else float("inf")
        odds_ratios_table.append({
            "predictor": predictor_names[j],
            "odds_ratio": or_val,
            "ci_lower": or_low,
            "ci_upper": or_high,
        })

    # Goodness-of-Fit Tests
    # Pearson chi-square: sum (y_ik - pi_ik)^2 / pi_ik
    pearson_chi2 = float(np.sum(((Y_ind - pi_fit) ** 2) / pi_fit))
    # Deviance: 2 * (L_sat - L_model) = -2 * ln L
    deviance = -2.0 * final_log_lik
    df_gof = max(1, n * (K - 1) - n_total_params)
    pearson_p = float(stats.chi2.sf(pearson_chi2, df_gof))
    deviance_p = float(stats.chi2.sf(deviance, df_gof))

    # Model Summary metrics
    mcfadden_r2 = max(0.0, (1.0 - final_log_lik / null_log_lik) * 100.0) if abs(null_log_lik) > 1e-12 else 0.0
    aic = -2.0 * final_log_lik + 2.0 * n_total_params
    bic = -2.0 * final_log_lik + math.log(n) * n_total_params

    # Measures of Association (Concordant, Discordant, Tied pairs)
    # Predicted response index for each observation
    pred_score = x_beta  # Higher x_beta implies higher likelihood of higher category
    concordant = 0
    discordant = 0
    tied = 0
    total_pairs = 0

    for i in range(n):
        for j in range(i + 1, n):
            if y_codes[i] == y_codes[j]:
                continue
            total_pairs += 1
            # Compare actual order vs predicted order
            actual_diff = y_codes[i] - y_codes[j]
            pred_diff = pred_score[i] - pred_score[j]
            if abs(pred_diff) < 1e-7:
                tied += 1
            elif (actual_diff > 0 and pred_diff > 0) or (actual_diff < 0 and pred_diff < 0):
                concordant += 1
            else:
                discordant += 1

    if total_pairs > 0:
        pct_conc = (concordant / total_pairs) * 100.0
        pct_disc = (discordant / total_pairs) * 100.0
        pct_tied = (tied / total_pairs) * 100.0
        somers_d = (concordant - discordant) / total_pairs
        gamma = (concordant - discordant) / (concordant + discordant) if (concordant + discordant) > 0 else 0.0
        kendalls_tau_a = (concordant - discordant) / (0.5 * n * (n - 1)) if n > 1 else 0.0
    else:
        pct_conc = pct_disc = pct_tied = somers_d = gamma = kendalls_tau_a = 0.0

    return {
        "analysis": "ordinal_logistic_regression",
        "response_name": response_name,
        "predictor_names": predictor_names,
        "levels": levels,
        "counts_by_level": counts_by_level,
        "n_obs": n,
        "confidence": confidence,
        "coefficients": coef_table,
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
        "association": {
            "concordant": concordant,
            "pct_concordant": pct_conc,
            "discordant": discordant,
            "pct_discordant": pct_disc,
            "tied": tied,
            "pct_tied": pct_tied,
            "total_pairs": total_pairs,
            "somers_d": somers_d,
            "gamma": gamma,
            "kendalls_tau_a": kendalls_tau_a,
        },
        "title": f"Ordinal Logistic Regression: {response_name} versus {', '.join(predictor_names)}",
    }
