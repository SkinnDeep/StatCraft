"""Accelerated Life Testing (ALT) Maximum Likelihood Estimation engine with right censoring.

References:
- Nelson, W. (1990). Accelerated Testing: Statistical Models, Test Plans, and Data Analysis.
  John Wiley & Sons.
- Meeker, W. Q., & Escobar, L. A. (1998). Statistical Methods for Reliability Data.
  John Wiley & Sons.
- Minitab 22: Stat > Reliability/Survival > Accelerated Life Testing...
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import stats
from scipy.optimize import minimize


def fit_accelerated_life_test(
    times: Sequence[float],
    events: Sequence[int],
    stresses: Sequence[float],
    model: str = "arrhenius",       # 'arrhenius', 'inverse_power', 'log_linear', 'linear'
    distribution: str = "weibull",  # 'weibull', 'lognormal', 'exponential', 'normal'
    use_stress: Optional[float] = None,
    percentiles: Sequence[float] = (1.0, 5.0, 10.0, 50.0),
    confidence: float = 95.0,
) -> Dict[str, Any]:
    """Fit an Accelerated Life Testing model using Maximum Likelihood Estimation.

    Parameters:
    - times: failure or right-censoring times (> 0)
    - events: 1 = failure, 0 = right-censored
    - stresses: numeric stress level (e.g. Temperature in deg C for Arrhenius, Voltage in V for InvPower)
    - model: 'arrhenius', 'inverse_power', 'log_linear', 'linear'
    - distribution: 'weibull', 'lognormal', 'exponential', 'normal'
    - use_stress: normal operating stress condition for lifetime extrapolation
    - percentiles: list of percentiles to compute at use condition (e.g. 1%, 5%, 10%, 50%)
    - confidence: confidence level for intervals (e.g. 95.0)
    """
    t_arr = np.asarray(times, dtype=float)
    e_arr = np.asarray(events, dtype=int)
    s_arr = np.asarray(stresses, dtype=float)

    if len(t_arr) != len(e_arr) or len(t_arr) != len(s_arr) or len(t_arr) < 4:
        raise ValueError("ALT requires at least 4 aligned lifetime, event, and stress observations.")

    if np.any(t_arr <= 0) or not np.all(np.isfinite(t_arr)):
        raise ValueError("Lifetime observations must be positive finite numbers.")

    if not np.all((e_arr == 0) | (e_arr == 1)):
        raise ValueError("Event indicators must be 1 (failure) or 0 (right-censored).")

    n_failures = int(np.sum(e_arr))
    if n_failures < 2:
        raise ValueError("At least 2 failure events are required to fit an accelerated life model.")

    unique_stresses = np.unique(s_arr)
    if len(unique_stresses) < 2:
        raise ValueError("Accelerated testing requires at least 2 distinct stress levels.")

    # Transform stress
    # Arrhenius: X = 1000 / (T_C + 273.15)
    # Inverse Power: X = ln(Stress)
    # Log-linear / Linear: X = Stress
    model = model.lower()
    if model == "arrhenius":
        if np.any(s_arr <= -273.15):
            raise ValueError("Temperatures must be greater than absolute zero (-273.15 °C).")
        x_arr = 1000.0 / (s_arr + 273.15)
        stress_label = "1000 / (Temp + 273.15)"
        x_use = (1000.0 / (use_stress + 273.15)) if use_stress is not None else None
    elif model == "inverse_power":
        if np.any(s_arr <= 0):
            raise ValueError("Stress values for Inverse Power Law must be strictly positive.")
        x_arr = np.log(s_arr)
        stress_label = "ln(Stress)"
        x_use = math.log(use_stress) if (use_stress is not None and use_stress > 0) else None
    elif model in ("log_linear", "linear"):
        x_arr = s_arr.copy()
        stress_label = "Stress"
        x_use = float(use_stress) if use_stress is not None else None
    else:
        raise ValueError(f"Unknown acceleration model '{model}'. Choose Arrhenius, Inverse Power, Log-linear, or Linear.")

    dist = distribution.lower()
    if dist not in ("weibull", "lognormal", "exponential", "normal"):
        raise ValueError(f"Unknown distribution '{distribution}'. Choose Weibull, Lognormal, Exponential, or Normal.")

    # Log-time transformation
    is_log_dist = dist in ("weibull", "lognormal", "exponential")
    y_arr = np.log(t_arr) if is_log_dist else t_arr.copy()

    # Initial estimates via OLS on failed observations
    mask_fail = (e_arr == 1)
    y_fail = y_arr[mask_fail]
    x_fail = x_arr[mask_fail]

    A_init = np.column_stack([np.ones(len(x_fail)), x_fail])
    beta_init, res, _, _ = np.linalg.lstsq(A_init, y_fail, rcond=None)
    b0_init, b1_init = float(beta_init[0]), float(beta_init[1])
    resids = y_fail - (b0_init + b1_init * x_fail)
    sigma_init = max(0.1, float(np.std(resids)))

    if dist == "exponential":
        # Only 2 parameters: b0, b1 (sigma fixed to 1.0)
        p0 = [b0_init, b1_init]
    else:
        # 3 parameters: b0, b1, log_sigma
        p0 = [b0_init, b1_init, math.log(sigma_init)]

    def neg_log_lik(p: Sequence[float]) -> float:
        b0, b1 = p[0], p[1]
        sigma = 1.0 if dist == "exponential" else math.exp(p[2])
        mu_vec = b0 + b1 * x_arr
        z = (y_arr - mu_vec) / sigma

        if dist == "weibull":
            # Extreme value distribution on log(t)
            # log f(y) = -log(sigma) + z - exp(z) - y (Jacobian for t)
            # log S(y) = -exp(z)
            ll_fail = -math.log(sigma) + z - np.exp(z) - y_arr
            ll_cens = -np.exp(z)
        elif dist == "lognormal":
            # Normal on log(t)
            # log f(y) = -log(sigma) - 0.5*log(2*pi) - 0.5*z^2 - y
            # log S(y) = log(1 - Phi(z))
            ll_fail = -math.log(sigma) - 0.5 * math.log(2.0 * math.pi) - 0.5 * (z**2) - y_arr
            # Avoid log(0)
            surv_prob = np.maximum(1e-15, 1.0 - stats.norm.cdf(z))
            ll_cens = np.log(surv_prob)
        elif dist == "exponential":
            # Weibull with sigma=1
            ll_fail = z - np.exp(z) - y_arr
            ll_cens = -np.exp(z)
        else:
            # Normal on t
            ll_fail = -math.log(sigma) - 0.5 * math.log(2.0 * math.pi) - 0.5 * (z**2)
            surv_prob = np.maximum(1e-15, 1.0 - stats.norm.cdf(z))
            ll_cens = np.log(surv_prob)

        total_ll = np.sum(e_arr * ll_fail + (1 - e_arr) * ll_cens)
        if not math.isfinite(total_ll):
            return 1e12
        return -float(total_ll)

    # Optimization
    opt_res = minimize(neg_log_lik, p0, method="L-BFGS-B")
    if not opt_res.success:
        # Fallback to Nelder-Mead
        opt_res = minimize(neg_log_lik, p0, method="Nelder-Mead")

    b0_fit, b1_fit = float(opt_res.x[0]), float(opt_res.x[1])
    if dist == "exponential":
        sigma_fit = 1.0
        shape_fit = 1.0
    else:
        sigma_fit = float(math.exp(opt_res.x[2]))
        shape_fit = 1.0 / sigma_fit

    # Numerical Hessian for covariance matrix
    p_opt = opt_res.x
    dim = len(p_opt)
    h_eps = 1e-4 * np.maximum(1.0, np.abs(p_opt))
    H = np.zeros((dim, dim))
    f0 = neg_log_lik(p_opt)
    for i in range(dim):
        ei = np.zeros(dim); ei[i] = h_eps[i]
        H[i, i] = (neg_log_lik(p_opt + ei) - 2 * f0 + neg_log_lik(p_opt - ei)) / (h_eps[i]**2)
        for j in range(i):
            ej = np.zeros(dim); ej[j] = h_eps[j]
            H[i, j] = (neg_log_lik(p_opt + ei + ej) - neg_log_lik(p_opt + ei - ej)
                       - neg_log_lik(p_opt - ei + ej) + neg_log_lik(p_opt - ei - ej)) / (4 * h_eps[i] * h_eps[j])
            H[j, i] = H[i, j]

    try:
        cov_matrix = np.linalg.pinv(H)
    except Exception:
        cov_matrix = np.eye(dim) * 0.01

    se_params = np.sqrt(np.maximum(1e-12, np.diag(cov_matrix)))
    se_b0 = float(se_params[0])
    se_b1 = float(se_params[1])

    # SE of sigma via delta method: Var(sigma) = Var(log_sigma) * sigma^2
    if dist != "exponential":
        se_sigma = float(se_params[2] * sigma_fit)
        # SE of shape = 1/sigma: Var(1/sigma) = Var(sigma) / sigma^4
        se_shape = float(se_sigma / (sigma_fit**2))
    else:
        se_sigma = 0.0
        se_shape = 0.0

    z_crit = float(stats.norm.ppf(1.0 - (100.0 - confidence) / 200.0))

    # Parameter Estimates Table
    params_table = [
        {
            "parameter": "Intercept (β₀)",
            "estimate": b0_fit,
            "se": se_b0,
            "ci_lower": b0_fit - z_crit * se_b0,
            "ci_upper": b0_fit + z_crit * se_b0,
            "z_val": b0_fit / se_b0 if se_b0 > 1e-12 else 0.0,
            "p_val": float(2.0 * (1.0 - stats.norm.cdf(abs(b0_fit / se_b0)))) if se_b0 > 1e-12 else 0.0,
        },
        {
            "parameter": f"Slope ({stress_label}) (β₁)",
            "estimate": b1_fit,
            "se": se_b1,
            "ci_lower": b1_fit - z_crit * se_b1,
            "ci_upper": b1_fit + z_crit * se_b1,
            "z_val": b1_fit / se_b1 if se_b1 > 1e-12 else 0.0,
            "p_val": float(2.0 * (1.0 - stats.norm.cdf(abs(b1_fit / se_b1)))) if se_b1 > 1e-12 else 0.0,
        },
    ]

    if dist == "weibull":
        params_table.append({
            "parameter": "Shape (β)",
            "estimate": shape_fit,
            "se": se_shape,
            "ci_lower": shape_fit * math.exp(-z_crit * (se_shape / shape_fit)) if shape_fit > 0 else 0.0,
            "ci_upper": shape_fit * math.exp(z_crit * (se_shape / shape_fit)) if shape_fit > 0 else 0.0,
            "z_val": (shape_fit - 1.0) / se_shape if se_shape > 1e-12 else 0.0,
            "p_val": float(2.0 * (1.0 - stats.norm.cdf(abs((shape_fit - 1.0) / se_shape)))) if se_shape > 1e-12 else 0.0,
        })
        params_table.append({
            "parameter": "Scale (σ)",
            "estimate": sigma_fit,
            "se": se_sigma,
            "ci_lower": sigma_fit * math.exp(-z_crit * (se_sigma / sigma_fit)),
            "ci_upper": sigma_fit * math.exp(z_crit * (se_sigma / sigma_fit)),
            "z_val": 0.0,
            "p_val": 1.0,
        })
    elif dist in ("lognormal", "normal"):
        params_table.append({
            "parameter": "Scale (σ)",
            "estimate": sigma_fit,
            "se": se_sigma,
            "ci_lower": sigma_fit * math.exp(-z_crit * (se_sigma / sigma_fit)),
            "ci_upper": sigma_fit * math.exp(z_crit * (se_sigma / sigma_fit)),
            "z_val": 0.0,
            "p_val": 1.0,
        })

    # Goodness of fit
    log_lik = -float(opt_res.fun)
    k_params = len(p_opt)
    n_total = len(t_arr)
    aic = 2.0 * k_params - 2.0 * log_lik
    bic = k_params * math.log(n_total) - 2.0 * log_lik

    # Percentiles at Use Condition
    percentiles_table = []
    if x_use is not None:
        # mu_use = b0 + b1 * x_use
        mu_use = b0_fit + b1_fit * x_use
        # Var(mu_use) = Var(b0) + x_use^2 Var(b1) + 2 x_use Cov(b0, b1)
        var_mu_use = cov_matrix[0, 0] + (x_use**2) * cov_matrix[1, 1] + 2.0 * x_use * cov_matrix[0, 1]

        for p_val in percentiles:
            p_frac = p_val / 100.0
            if dist == "weibull":
                w_p = math.log(-math.log(1.0 - p_frac))
            elif dist in ("lognormal", "normal"):
                w_p = float(stats.norm.ppf(p_frac))
            elif dist == "exponential":
                w_p = math.log(-math.log(1.0 - p_frac))

            # Fitted value in fit scale (log(t) or t)
            y_p = mu_use + w_p * sigma_fit

            # Variance via delta method
            if dist != "exponential":
                # Grad wrt [b0, b1, log_sigma] = [1, x_use, w_p * sigma_fit]
                grad = np.array([1.0, x_use, w_p * sigma_fit])
                var_y_p = float(grad.T @ cov_matrix @ grad)
            else:
                grad = np.array([1.0, x_use])
                var_y_p = float(grad.T @ cov_matrix @ grad)

            se_y_p = math.sqrt(max(1e-12, var_y_p))

            if is_log_dist:
                est_time = math.exp(y_p)
                ci_low = math.exp(y_p - z_crit * se_y_p)
                ci_high = math.exp(y_p + z_crit * se_y_p)
            else:
                est_time = y_p
                ci_low = max(0.0, y_p - z_crit * se_y_p)
                ci_high = y_p + z_crit * se_y_p

            percentiles_table.append({
                "percentile": p_val,
                "label": f"B{int(p_val) if p_val == int(p_val) else p_val} ({p_val:g}%)",
                "estimate": est_time,
                "ci_lower": ci_low,
                "ci_upper": ci_high,
                "se": se_y_p,
            })

    # Acceleration Factors across tested stress levels relative to use condition
    accel_factors_table = []
    if x_use is not None:
        for s_lvl in sorted(unique_stresses):
            if model == "arrhenius":
                x_lvl = 1000.0 / (s_lvl + 273.15)
            elif model == "inverse_power":
                x_lvl = math.log(s_lvl)
            else:
                x_lvl = s_lvl

            # Life ratio = exp(b1 * (x_use - x_lvl)) for log models
            if is_log_dist:
                af = math.exp(b1_fit * (x_use - x_lvl))
            else:
                af = (b0_fit + b1_fit * x_use) / max(1e-6, b0_fit + b1_fit * x_lvl)
            accel_factors_table.append({
                "stress": float(s_lvl),
                "acceleration_factor": af,
            })

    # Data points for plotting Life vs Stress
    plot_points = []
    for t_i, e_i, s_i in zip(t_arr, e_arr, s_arr):
        plot_points.append({
            "time": float(t_i),
            "event": int(e_i),
            "stress": float(s_i),
        })

    return {
        "analysis": "accelerated_life_testing",
        "model": model,
        "distribution": distribution,
        "n_total": n_total,
        "n_failed": n_failures,
        "n_censored": n_total - n_failures,
        "b0": b0_fit,
        "b1": b1_fit,
        "sigma": sigma_fit,
        "shape": shape_fit,
        "params_table": params_table,
        "log_likelihood": log_lik,
        "aic": aic,
        "bic": bic,
        "use_stress": use_stress,
        "x_use": x_use,
        "percentiles": percentiles_table,
        "acceleration_factors": accel_factors_table,
        "stress_label": stress_label,
        "confidence": confidence,
        "plot_points": plot_points,
    }
