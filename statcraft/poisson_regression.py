"""Computational engine for Poisson Regression.

Provides 1:1 parity with Minitab Poisson Regression:
- Log-linear model: ln(mu) = X*beta + offset
- Continuous and categorical predictors with reference coding
- Optional offset variable (exposure / observation period)
- Iteratively Reweighted Least Squares (IRLS / Fisher Scoring) with step halving
- Statistical inference: SE, Z-values, P-values, 95% Confidence Intervals
- Relative Risk / Rate Ratios: exp(beta) with 95% Confidence Intervals
- Goodness-of-Fit Tests: Deviance and Pearson Chi-Square tests
- Model Summary: Deviance R-sq, Adjusted Deviance R-sq, AIC, BIC, Log-Likelihood
- Analysis of Deviance (ANOVA table)
- Deviance, Pearson, and Raw Residuals
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import special, stats


def clean_poisson_data(
    response: Sequence[Any],
    continuous_predictors: Optional[Sequence[Sequence[Any]]] = None,
    categorical_predictors: Optional[Sequence[Sequence[Any]]] = None,
    offset: Optional[Sequence[Any]] = None,
) -> Tuple[np.ndarray, List[List[float]], List[List[str]], Optional[np.ndarray], List[int]]:
    """Clean and align response, predictors, and offset."""
    n_raw = len(response)
    cont_list = list(continuous_predictors) if continuous_predictors else []
    cat_list = list(categorical_predictors) if categorical_predictors else []

    valid_y: List[float] = []
    valid_cont: List[List[float]] = []
    valid_cat: List[List[str]] = []
    valid_offset: List[float] = []
    valid_indices: List[int] = []

    for i in range(n_raw):
        y_val = response[i]
        if y_val is None:
            continue
        try:
            fy = float(y_val)
            if math.isnan(fy) or math.isinf(fy) or fy < 0:
                continue
        except (ValueError, TypeError):
            continue

        # Check continuous predictors
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

        # Check categorical predictors
        cat_row: List[str] = []
        cat_ok = True
        for col in cat_list:
            v = col[i]
            if v is None:
                cat_ok = False
                break
            s_val = str(v).strip()
            if not s_val:
                cat_ok = False
                break
            cat_row.append(s_val)

        if not cat_ok:
            continue

        # Check offset if present
        fo = 0.0
        if offset is not None:
            ov = offset[i]
            if ov is None:
                continue
            try:
                fo = float(ov)
                if math.isnan(fo) or math.isinf(fo):
                    continue
            except (ValueError, TypeError):
                continue

        valid_y.append(fy)
        valid_cont.append(cont_row)
        valid_cat.append(cat_row)
        if offset is not None:
            valid_offset.append(fo)
        valid_indices.append(i)

    y_arr = np.asarray(valid_y, dtype=float)
    off_arr = np.asarray(valid_offset, dtype=float) if offset is not None else None
    return y_arr, valid_cont, valid_cat, off_arr, valid_indices


def _compute_poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    """Compute Poisson deviance: 2 * sum(y * ln(y / mu) - (y - mu))."""
    # Where y == 0, y * ln(y / mu) = 0
    safe_mu = np.maximum(1e-12, mu)
    dev_terms = np.zeros_like(y)
    pos = y > 0
    dev_terms[pos] = y[pos] * np.log(y[pos] / safe_mu[pos])
    dev_terms -= (y - safe_mu)
    return float(2.0 * np.sum(dev_terms))


def fit_poisson_regression(
    response: Sequence[Any],
    continuous_predictors: Optional[Sequence[Sequence[Any]]] = None,
    categorical_predictors: Optional[Sequence[Sequence[Any]]] = None,
    continuous_names: Optional[Sequence[str]] = None,
    categorical_names: Optional[Sequence[str]] = None,
    offset: Optional[Sequence[Any]] = None,
    offset_name: Optional[str] = None,
    response_name: str = "Y",
    confidence: float = 0.95,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> Dict[str, Any]:
    """Fit Poisson regression matching Minitab methods and formulas."""
    y, cont_data, cat_data, off, valid_indices = clean_poisson_data(
        response, continuous_predictors, categorical_predictors, offset
    )
    n = len(y)
    if n < 3:
        raise ValueError("At least 3 valid observations required for Poisson regression.")

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

    # Build design matrix with reference coding for categorical factors
    # First level alphabetically/order-wise is the reference level (omitted from design matrix)
    term_names = ["Constant"]
    term_sources = ["Constant"]
    cols: List[np.ndarray] = [np.ones(n, dtype=float)]

    # Continuous columns
    if n_cont > 0:
        cont_matrix = np.asarray(cont_data, dtype=float)
        for j in range(n_cont):
            col_j = cont_matrix[:, j]
            cols.append(col_j)
            term_names.append(cont_names[j])
            term_sources.append(cont_names[j])

    # Categorical columns
    cat_levels_info = {}
    if n_cat > 0:
        for j in range(n_cat):
            col_vals = [row[j] for row in cat_data]
            unique_levels = sorted(list(set(col_vals)))
            if len(unique_levels) < 2:
                raise ValueError(f"Categorical factor '{cat_names[j]}' must have at least 2 distinct levels.")
            ref_level = unique_levels[0]
            non_ref_levels = unique_levels[1:]
            cat_levels_info[cat_names[j]] = {
                "reference": ref_level,
                "all_levels": unique_levels,
            }
            for lvl in non_ref_levels:
                ind = np.asarray([1.0 if v == lvl else 0.0 for v in col_vals], dtype=float)
                cols.append(ind)
                term_names.append(f"{cat_names[j]}_{lvl}")
                term_sources.append(cat_names[j])

    X = np.column_stack(cols)
    p = X.shape[1]
    if n <= p:
        raise ValueError(f"Number of observations ({n}) must exceed number of estimated parameters ({p}).")

    off_vec = off if off is not None else np.zeros(n, dtype=float)

    # Initial estimates for beta
    # Standard GLM initial: eta = ln((y + 0.5)) - offset
    y_init = np.where(y == 0, 0.5, y)
    eta_init = np.log(y_init) - off_vec
    beta = np.linalg.lstsq(X, eta_init, rcond=None)[0]

    # IRLS algorithm
    converged = False
    prev_dev = float("inf")

    for iteration in range(max_iter):
        eta = X @ beta + off_vec
        # Safeguard eta against overflow
        eta = np.clip(eta, -30.0, 30.0)
        mu = np.exp(eta)

        dev = _compute_poisson_deviance(y, mu)
        if abs(prev_dev - dev) < tol:
            converged = True
            break
        prev_dev = dev

        # Weights W = mu
        w = np.maximum(1e-10, mu)
        # Working variable: z = (eta - off_vec) + (y - mu) / mu
        z = (eta - off_vec) + (y - mu) / w

        # Solve (X^T W X) delta = X^T W z
        # Use sqrt(W) * X for numerical stability
        sqrt_w = np.sqrt(w)[:, None]
        X_w = X * sqrt_w
        z_w = z * sqrt_w.squeeze()

        try:
            beta_new, residuals, rank, s_vals = np.linalg.lstsq(X_w, z_w, rcond=None)
            if rank < p:
                raise np.linalg.LinAlgError("Design matrix is rank deficient.")
        except np.linalg.LinAlgError:
            break

        # Step halving if deviance increases
        step_factor = 1.0
        for _ in range(5):
            candidate_beta = beta + step_factor * (beta_new - beta)
            c_eta = np.clip(X @ candidate_beta + off_vec, -30.0, 30.0)
            c_mu = np.exp(c_eta)
            c_dev = _compute_poisson_deviance(y, c_mu)
            if c_dev <= dev + 1e-7:
                beta = candidate_beta
                break
            step_factor *= 0.5
        else:
            beta = beta_new

    # Final fit values
    eta = np.clip(X @ beta + off_vec, -30.0, 30.0)
    mu = np.exp(eta)
    deviance = _compute_poisson_deviance(y, mu)
    df_residual = n - p

    # Covariance matrix: (X^T W X)^{-1}
    w = np.maximum(1e-10, mu)
    sqrt_w = np.sqrt(w)[:, None]
    X_w = X * sqrt_w
    try:
        cov = np.linalg.inv(X_w.T @ X_w)
        se_beta = np.sqrt(np.maximum(0.0, np.diag(cov)))
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(X_w.T @ X_w)
        se_beta = np.sqrt(np.maximum(0.0, np.diag(cov)))

    # Z critical value
    z_crit = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))

    # Coefficients table
    coef_table = []
    for j in range(p):
        b = float(beta[j])
        se = float(se_beta[j])
        z_val = b / se if se > 1e-12 else 0.0
        p_val = 2.0 * float(stats.norm.sf(abs(z_val)))
        ci_lower = b - z_crit * se
        ci_upper = b + z_crit * se
        # Relative Risk (Rate Ratio) exp(beta)
        # For constant, RR is baseline rate
        rr = math.exp(b) if abs(b) < 100 else float("inf")
        rr_lower = math.exp(ci_lower) if abs(ci_lower) < 100 else 0.0
        rr_upper = math.exp(ci_upper) if abs(ci_upper) < 100 else float("inf")

        coef_table.append({
            "term": term_names[j],
            "coef": b,
            "se_coef": se,
            "z_value": z_val,
            "p_value": p_val,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "relative_risk": rr,
            "rr_lower": rr_lower,
            "rr_upper": rr_upper,
        })

    # Pearson Chi-Square
    pearson_chi2 = float(np.sum(((y - mu) ** 2) / np.maximum(1e-12, mu)))
    pearson_p = float(stats.chi2.sf(pearson_chi2, df_residual))
    deviance_p = float(stats.chi2.sf(deviance, df_residual))

    # Null model deviance (intercept only + offset)
    # Solve for beta_0 such that sum(exp(beta_0 + offset)) = sum(y)
    sum_y = float(np.sum(y))
    if off is not None:
        # beta_0 = ln(sum_y / sum(exp(offset)))
        sum_exp_off = float(np.sum(np.exp(off_vec)))
        beta_0_null = math.log(max(1e-12, sum_y / max(1e-12, sum_exp_off)))
    else:
        beta_0_null = math.log(max(1e-12, sum_y / n))
    mu_null = np.exp(beta_0_null + off_vec)
    null_deviance = _compute_poisson_deviance(y, mu_null)
    df_null = n - 1

    # Model Summary metrics
    dev_r_sq = max(0.0, (1.0 - deviance / null_deviance) * 100.0) if null_deviance > 1e-12 else 0.0
    dev_r_sq_adj = (
        max(0.0, (1.0 - (deviance / df_residual) / (null_deviance / df_null)) * 100.0)
        if null_deviance > 1e-12 and df_null > 0 and df_residual > 0
        else 0.0
    )

    # Log-likelihood: sum(y * ln(mu) - mu - ln(y!))
    log_fact_y = special.gammaln(y + 1.0)
    log_lik = float(np.sum(y * np.log(np.maximum(1e-12, mu)) - mu - log_fact_y))
    aic = 2.0 * p - 2.0 * log_lik
    bic = math.log(n) * p - 2.0 * log_lik

    # Analysis of Deviance (ANOVA)
    dev_reg = max(0.0, null_deviance - deviance)
    df_reg = p - 1
    ms_reg = dev_reg / df_reg if df_reg > 0 else 0.0
    p_reg = float(stats.chi2.sf(dev_reg, df_reg)) if df_reg > 0 else 1.0

    anova = [
        {"source": "Regression", "df": df_reg, "adj_dev": dev_reg, "adj_ms": ms_reg, "chi_square": dev_reg, "p_value": p_reg},
        {"source": "Error", "df": df_residual, "adj_dev": deviance, "adj_ms": deviance / df_residual, "chi_square": None, "p_value": None},
        {"source": "Total", "df": df_null, "adj_dev": null_deviance, "adj_ms": None, "chi_square": None, "p_value": None},
    ]

    # Residuals
    raw_residuals = (y - mu).tolist()
    pearson_residuals = ((y - mu) / np.sqrt(np.maximum(1e-12, mu))).tolist()
    sign_res = np.sign(y - mu)
    # deviance residual: sign * sqrt(2 * (y * ln(y/mu) - (y - mu)))
    dev_indiv = np.zeros_like(y)
    pos = y > 0
    dev_indiv[pos] = y[pos] * np.log(y[pos] / np.maximum(1e-12, mu[pos]))
    dev_indiv -= (y - mu)
    dev_residuals = (sign_res * np.sqrt(np.maximum(0.0, 2.0 * dev_indiv))).tolist()

    # Regression Equation string
    eq_parts = [f"{beta[0]:.4f}"]
    for j in range(1, p):
        c = beta[j]
        sign = "+ " if c >= 0 else "- "
        eq_parts.append(f"{sign}{abs(c):.4f} {term_names[j]}")
    if offset_name:
        eq_parts.append(f"+ {offset_name}")
    equation = f"ln({response_name}) = {' '.join(eq_parts)}"

    return {
        "analysis": "poisson_regression",
        "response_name": response_name,
        "continuous_names": cont_names,
        "categorical_names": cat_names,
        "offset_name": offset_name,
        "n_obs": n,
        "confidence": confidence,
        "coefficients": coef_table,
        "deviance": deviance,
        "df_residual": df_residual,
        "null_deviance": null_deviance,
        "df_null": df_null,
        "deviance_r_sq": dev_r_sq,
        "deviance_r_sq_adj": dev_r_sq_adj,
        "log_likelihood": log_lik,
        "aic": aic,
        "bic": bic,
        "goodness_of_fit": [
            {"test": "Deviance", "df": df_residual, "chi_square": deviance, "p_value": deviance_p},
            {"test": "Pearson", "df": df_residual, "chi_square": pearson_chi2, "p_value": pearson_p},
        ],
        "anova": anova,
        "equation": equation,
        "fits": mu.tolist(),
        "residuals": raw_residuals,
        "pearson_residuals": pearson_residuals,
        "deviance_residuals": dev_residuals,
        "title": f"Poisson Regression: {response_name} versus {', '.join(cont_names + cat_names)}",
    }
