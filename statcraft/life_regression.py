"""Computational engine for Regression with Life Data (Accelerated Failure Time / Parametric Survival Regression).

Provides 1:1 parity with Minitab Regression with Life Data:
- Fits Accelerated Failure Time (AFT) models with censoring:
  ln(T) = X * beta + sigma * epsilon
- Assumed distributions:
  * Weibull (Extreme Value error epsilon)
  * Lognormal (Standard Normal error epsilon)
  * Exponential (Extreme Value error with fixed sigma = 1)
  * Loglogistic (Standard Logistic error epsilon)
- Right censoring support (Censored = 0, Exact Failure = 1).
- Maximum Likelihood Estimation via BFGS optimization of log-likelihood.
- Inverted Hessian Fisher Information covariance matrix for SEs and CIs.
- Coefficients Table: Term, Coef, SE Coef, Z, P-value, 95% CI.
- Distribution Parameters Table: Scale (sigma), Shape (1/sigma for Weibull).
- Percentiles / Quantiles table (10th percentile, 50th percentile MTTF) at mean predictor values.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import stats, optimize


def _error_distribution(dist_name: str):
    """Return standard survival S0(z) and PDF f0(z) for standardized error z = (ln(t) - mu) / sigma."""
    d = dist_name.lower()
    if d in ("weibull", "exponential"):
        # Smallest Extreme Value distribution:
        # S0(z) = exp(-exp(z)), f0(z) = exp(z - exp(z))
        log_s0 = lambda z: -np.exp(np.clip(z, -30.0, 30.0))
        log_f0 = lambda z: z - np.exp(np.clip(z, -30.0, 30.0))
        q0 = lambda p: float(np.log(-np.log(1.0 - p)))
    elif d in ("lognormal", "normal"):
        # Standard normal
        log_s0 = lambda z: stats.norm.logsf(z)
        log_f0 = lambda z: stats.norm.logpdf(z)
        q0 = lambda p: float(stats.norm.ppf(p))
    elif d in ("loglogistic", "logistic"):
        # Standard logistic
        log_s0 = lambda z: -np.log1p(np.exp(np.clip(z, -30.0, 30.0)))
        log_f0 = lambda z: -np.clip(z, -30.0, 30.0) - 2.0 * np.log1p(np.exp(-np.clip(z, -30.0, 30.0)))
        q0 = lambda p: float(np.log(p / (1.0 - p)))
    else:
        raise ValueError(f"Unsupported distribution '{dist_name}'. Choose Weibull, Lognormal, Exponential, or Loglogistic.")
    return log_s0, log_f0, q0


def clean_life_data(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
    censor: Optional[Sequence[Any]] = None,
    predictor_names: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Clean and filter life regression data."""
    n_preds = len(predictors)
    p_names = list(predictor_names) if predictor_names else [f"X{i+1}" for i in range(n_preds)]
    n_rows = len(response)

    clean_y: List[float] = []
    clean_x: List[List[float]] = []
    clean_c: List[int] = []

    for i in range(n_rows):
        y_val = response[i]
        c_val = censor[i] if censor is not None and i < len(censor) else 1

        if y_val is None:
            continue
        try:
            fy = float(y_val)
            if math.isnan(fy) or math.isinf(fy) or fy <= 0:
                continue
            fc = int(c_val) if c_val is not None else 1
            if fc not in (0, 1):
                fc = 1 if fc > 0 else 0

            # Predictors
            row_x: List[float] = []
            row_valid = True
            for p_vec in predictors:
                v = p_vec[i] if i < len(p_vec) else None
                if v is None:
                    row_valid = False
                    break
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    row_valid = False
                    break
                row_x.append(fv)

            if not row_valid:
                continue

            clean_y.append(fy)
            clean_x.append(row_x)
            clean_c.append(fc)
        except (ValueError, TypeError):
            continue

    if len(clean_y) < n_preds + 2:
        raise ValueError("Insufficient valid observations for regression with life data.")

    return np.array(clean_y, dtype=float), np.array(clean_x, dtype=float), np.array(clean_c, dtype=int), p_names


def fit_life_regression(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
    censor: Optional[Sequence[Any]] = None,
    distribution: str = "weibull",
    confidence: float = 0.95,
    response_name: str = "Lifetime",
    predictor_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Fit Parametric Survival / Life Regression model via Maximum Likelihood Estimation."""
    arr_y, arr_x, arr_c, p_names = clean_life_data(response, predictors, censor, predictor_names)
    n, p = arr_x.shape
    dist = distribution.lower()
    is_exponential = (dist == "exponential")

    log_s0, log_f0, q0 = _error_distribution(dist)
    log_y = np.log(arr_y)

    # Design matrix: intercept + predictors
    X = np.column_stack([np.ones(n), arr_x])
    k_params = p + 1  # beta coefficients

    # Initial estimates via OLS
    try:
        b_init = np.linalg.lstsq(X, log_y, rcond=None)[0]
    except Exception:
        b_init = np.zeros(k_params)

    res_init = log_y - X @ b_init
    sigma_init = float(np.std(res_init, ddof=1)) if not is_exponential else 1.0
    if sigma_init <= 1e-4:
        sigma_init = 1.0

    # Optimization parameter vector:
    # If not exponential: theta = [beta_0, ..., beta_p, ln_sigma]
    # If exponential: theta = [beta_0, ..., beta_p]
    if is_exponential:
        theta_init = b_init
    else:
        theta_init = np.append(b_init, np.log(sigma_init))

    def neg_log_lik(theta: np.ndarray) -> float:
        beta = theta[:k_params]
        if is_exponential:
            sigma = 1.0
        else:
            sigma = math.exp(np.clip(theta[-1], -10.0, 10.0))

        mu = X @ beta
        z = (log_y - mu) / sigma

        # Log-likelihood:
        # For uncensored (arr_c == 1): -ln(sigma) + log_f0(z) - log_y
        # For censored (arr_c == 0): log_s0(z)
        ll = 0.0
        uncensored = (arr_c == 1)
        censored = (arr_c == 0)

        if np.any(uncensored):
            ll += np.sum(-math.log(sigma) + log_f0(z[uncensored]) - log_y[uncensored])
        if np.any(censored):
            ll += np.sum(log_s0(z[censored]))

        return -float(ll) if math.isfinite(ll) else 1e12

    opt_res = optimize.minimize(
        neg_log_lik,
        theta_init,
        method="BFGS",
        options={"maxiter": 500, "gtol": 1e-5},
    )

    theta_opt = opt_res.x
    beta_hat = theta_opt[:k_params]
    sigma_hat = 1.0 if is_exponential else math.exp(theta_opt[-1])
    max_log_lik = -float(opt_res.fun)

    # Covariance matrix via inverse Hessian
    try:
        cov_theta = opt_res.hess_inv
        if hasattr(cov_theta, "todense"):
            cov_theta = cov_theta.todense()
    except Exception:
        cov_theta = np.eye(len(theta_opt))

    z_crit = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))

    # Coefficients Table
    coefficients = []
    term_names = ["Intercept"] + p_names

    for i in range(k_params):
        b_val = float(beta_hat[i])
        var_b = max(0.0, float(cov_theta[i, i]))
        se_b = math.sqrt(var_b)
        z_val = b_val / se_b if se_b > 0 else 0.0
        p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z_val))))
        ci_lower = b_val - z_crit * se_b
        ci_upper = b_val + z_crit * se_b

        coefficients.append({
            "term": term_names[i],
            "coef": b_val,
            "se_coef": se_b,
            "z_value": z_val,
            "p_value": p_val,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
        })

    # Scale parameter info
    if not is_exponential:
        var_ln_sigma = max(0.0, float(cov_theta[-1, -1]))
        se_ln_sigma = math.sqrt(var_ln_sigma)
        se_sigma = sigma_hat * se_ln_sigma
        ci_sigma = (
            sigma_hat * math.exp(-z_crit * se_ln_sigma),
            sigma_hat * math.exp(z_crit * se_ln_sigma),
        )
    else:
        se_sigma = 0.0
        ci_sigma = (1.0, 1.0)

    # For Weibull, shape k = 1 / sigma
    shape_hat = (1.0 / sigma_hat) if sigma_hat > 0 else 1.0
    se_shape = (se_sigma / (sigma_hat ** 2)) if sigma_hat > 0 else 0.0
    ci_shape = (1.0 / ci_sigma[1], 1.0 / ci_sigma[0]) if ci_sigma[0] > 0 else (0.0, 0.0)

    # Percentiles table evaluated at mean predictor values
    mean_x = np.mean(arr_x, axis=0) if p > 0 else np.array([])
    x0 = np.append([1.0], mean_x)
    mu0 = float(x0 @ beta_hat)

    # Covariance of mu0
    cov_beta = cov_theta[:k_params, :k_params]
    var_mu0 = float(x0 @ cov_beta @ x0)

    percentile_probs = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90]
    percentiles_table = []

    for prob in percentile_probs:
        zp = q0(prob)
        log_tp = mu0 + sigma_hat * zp
        tp_est = math.exp(log_tp)

        # Delta method variance for log(tp)
        if not is_exponential:
            # cov between beta and ln_sigma is cov_theta[:k_params, -1]
            cov_mu_lns = float(x0 @ cov_theta[:k_params, -1])
            var_log_tp = var_mu0 + (zp * sigma_hat) ** 2 * var_ln_sigma + 2.0 * zp * sigma_hat * cov_mu_lns
        else:
            var_log_tp = var_mu0

        se_log_tp = math.sqrt(max(0.0, var_log_tp))
        ci_tp_l = tp_est * math.exp(-z_crit * se_log_tp)
        ci_tp_u = tp_est * math.exp(z_crit * se_log_tp)
        se_tp = tp_est * se_log_tp

        percentiles_table.append({
            "percent": prob * 100.0,
            "estimate": tp_est,
            "se": se_tp,
            "ci_lower": ci_tp_l,
            "ci_upper": ci_tp_u,
        })

    return {
        "analysis": "life_regression",
        "title": f"Regression with Life Data: {response_name} versus {', '.join(p_names)}",
        "response_name": response_name,
        "predictor_names": p_names,
        "distribution": dist.capitalize(),
        "n_obs": n,
        "n_failures": int(np.sum(arr_c == 1)),
        "n_censored": int(np.sum(arr_c == 0)),
        "log_likelihood": max_log_lik,
        "confidence": confidence,
        "coefficients": coefficients,
        "parameters": {
            "scale": sigma_hat,
            "se_scale": se_sigma,
            "ci_scale": ci_sigma,
            "shape": shape_hat if dist in ("weibull", "exponential") else None,
            "se_shape": se_shape if dist in ("weibull", "exponential") else None,
            "ci_shape": ci_shape if dist in ("weibull", "exponential") else None,
        },
        "percentiles": percentiles_table,
    }
