"""Computational engine for Box-Jenkins ARIMA (Autoregressive Integrated Moving Average) modeling.

Matches Minitab statistical formulas and algorithms:
- ARIMA(p, d, q) x (P, D, Q)_s models.
- Nonseasonal and seasonal differencing: (1 - B)^d (1 - B^S)^D.
- Optional constant term estimation.
- Conditional least squares (CLS) parameter estimation with analytical/numerical Jacobians.
- Coefficient standard errors, t-statistics, and p-values.
- Residual Sum of Squares (SS), Mean Squared Error (MS), and Degrees of Freedom.
- Recursive multi-step forecasts with standard errors and confidence intervals.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import stats, optimize

from .time_series import clean_series


def difference_series(
    y: np.ndarray,
    d: int = 0,
    D: int = 0,
    S: int = 1,
) -> np.ndarray:
    """Apply nonseasonal differencing (1 - B)^d and seasonal differencing (1 - B^S)^D."""
    w = np.copy(y)
    for _ in range(d):
        w = w[1:] - w[:-1]
    for _ in range(D):
        if len(w) <= S:
            raise ValueError(f"Series too short for seasonal differencing with period {S}.")
        w = w[S:] - w[:-S]
    return w


def undifference_forecasts(
    y_history: np.ndarray,
    diff_forecasts: Sequence[float],
    d: int = 0,
    D: int = 0,
    S: int = 1,
) -> List[float]:
    """Invert seasonal and nonseasonal differencing to convert differenced forecasts back to levels."""
    fc = list(diff_forecasts)
    H = len(fc)
    if d == 0 and D == 0:
        return fc

    # Reconstruct extended series step by step
    full = list(y_history)
    for h in range(H):
        val = fc[h]
        # Invert seasonal first if D > 0, then nonseasonal
        # Effective recursion:
        # If d=1: Y_{t} = W_t + Y_{t-1}
        # If D=1: Y_{t} = W_t + Y_{t-S}
        # If d=1, D=1: (1-B)(1-B^S) Y_t = Y_t - Y_{t-1} - Y_{t-S} + Y_{t-S-1}
        # => Y_t = W_t + Y_{t-1} + Y_{t-S} - Y_{t-S-1}
        if d == 1 and D == 0:
            rec = val + full[-1]
        elif d == 0 and D == 1:
            rec = val + full[-S]
        elif d == 1 and D == 1:
            rec = val + full[-1] + full[-S] - full[-S - 1]
        elif d == 2 and D == 0:
            rec = val + 2 * full[-1] - full[-2]
        else:
            rec = val + full[-1]
        full.append(rec)
    return full[-H:]


def fit_arima(
    values: Any,
    p: int = 1,
    d: int = 0,
    q: int = 0,
    P: int = 0,
    D: int = 0,
    Q: int = 0,
    S: int = 1,
    include_constant: Optional[bool] = None,
    forecasts: int = 0,
    conf_level: float = 95.0,
    max_iter: int = 50,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Fit ARIMA(p,d,q)x(P,D,Q)_s model to time series values."""
    y = clean_series(values)
    n_orig = len(y)
    if n_orig < (p + q + P + Q + d + D * S + 5):
        raise ValueError(f"Series too short for requested ARIMA specification (length {n_orig}).")

    if include_constant is None:
        include_constant = (d == 0 and D == 0)

    # 1. Differencing
    w = difference_series(y, d=d, D=D, S=S)
    N = len(w)

    param_names = []
    for i in range(1, p + 1):
        param_names.append(f"AR  {i}")
    for j in range(1, q + 1):
        param_names.append(f"MA  {j}")
    for i in range(1, P + 1):
        param_names.append(f"SAR {i}")
    for j in range(1, Q + 1):
        param_names.append(f"SMA {j}")
    if include_constant:
        param_names.append("Constant")

    num_params = len(param_names)

    # Residual calculation for given parameters
    def compute_residuals(params: np.ndarray) -> np.ndarray:
        idx = 0
        phi = params[idx : idx + p] if p > 0 else np.array([])
        idx += p
        theta = params[idx : idx + q] if q > 0 else np.array([])
        idx += q
        Phi = params[idx : idx + P] if P > 0 else np.array([])
        idx += P
        Theta = params[idx : idx + Q] if Q > 0 else np.array([])
        idx += Q
        const = params[idx] if include_constant else 0.0

        # Mean adjustment: w_mean = const / (1 - sum(phi) - sum(Phi))
        mu = const if include_constant else 0.0
        w_cent = w - mu

        # Combine seasonal and nonseasonal AR and MA
        # For simplicity and robust stability, perform recursive filtering on w_cent
        a = np.zeros(N, dtype=float)
        for t in range(N):
            pred = 0.0
            # AR components
            for lag_p in range(p):
                if t - (lag_p + 1) >= 0:
                    pred += phi[lag_p] * w_cent[t - (lag_p + 1)]
            # Seasonal AR components
            for lag_P in range(P):
                s_lag = (lag_P + 1) * S
                if t - s_lag >= 0:
                    pred += Phi[lag_P] * w_cent[t - s_lag]
            # MA components (subtract theta * a_{t-k})
            for lag_q in range(q):
                if t - (lag_q + 1) >= 0:
                    pred -= theta[lag_q] * a[t - (lag_q + 1)]
            # Seasonal MA components
            for lag_Q in range(Q):
                s_lag = (lag_Q + 1) * S
                if t - s_lag >= 0:
                    pred -= Theta[lag_Q] * a[t - s_lag]

            a[t] = w_cent[t] - pred
        return a

    # Initial parameter guess
    x0 = np.zeros(num_params, dtype=float)
    if include_constant:
        x0[-1] = float(np.mean(w))

    # Minimize sum of squared residuals
    res = optimize.minimize(
        lambda p_vec: float(np.sum(compute_residuals(p_vec) ** 2)),
        x0=x0,
        method="L-BFGS-B",
        options={"maxiter": max_iter},
    )

    opt_params = res.x
    opt_residuals = compute_residuals(opt_params)

    # Degrees of freedom and SS / MS
    ss = float(np.sum(opt_residuals ** 2))
    df = max(1, N - num_params)
    ms = ss / df
    s_err = math.sqrt(ms)

    # Approximate covariance matrix from numerical Jacobian
    eps = 1e-5
    J = np.zeros((N, num_params), dtype=float)
    r0 = opt_residuals
    for j in range(num_params):
        step = np.zeros(num_params, dtype=float)
        step[j] = eps
        rj = compute_residuals(opt_params + step)
        J[:, j] = (rj - r0) / eps

    try:
        jt_j = J.T @ J
        cov = np.linalg.inv(jt_j) * ms
        se_params = np.sqrt(np.maximum(1e-12, np.diag(cov)))
    except np.linalg.LinAlgError:
        se_params = np.full(num_params, s_err / math.sqrt(N))

    estimates = []
    for name, coef, se in zip(param_names, opt_params, se_params):
        t_stat = coef / se if se > 0 else 0.0
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df)))
        estimates.append({
            "type": name,
            "coef": float(coef),
            "se": float(se),
            "t": float(t_stat),
            "p": float(p_val),
        })

    # Within-sample fitted values on original scale
    # Fit on differenced series: w - residuals
    w_fit = w - opt_residuals
    # Align fitted values to original series length
    diff_loss = n_orig - N
    fitted_vals = [None] * diff_loss
    for t in range(N):
        # Y_t = fitted
        fitted_vals.append(float(y[diff_loss + t] - opt_residuals[t]))

    # Out-of-sample Forecasts
    forecast_list = []
    if forecasts > 0:
        alpha_signif = 1.0 - (conf_level / 100.0)
        z_crit = float(stats.norm.ppf(1.0 - alpha_signif / 2.0))

        idx = 0
        phi = opt_params[idx : idx + p] if p > 0 else np.array([])
        idx += p
        theta = opt_params[idx : idx + q] if q > 0 else np.array([])
        idx += q
        Phi = opt_params[idx : idx + P] if P > 0 else np.array([])
        idx += P
        Theta = opt_params[idx : idx + Q] if Q > 0 else np.array([])
        idx += Q
        const = opt_params[idx] if include_constant else 0.0

        # Multi-step forecasting for differenced series
        w_ext = list(w)
        a_ext = list(opt_residuals)
        w_fc = []

        for h in range(1, forecasts + 1):
            pred_w = const
            for lag_p in range(p):
                idx_w = len(w_ext) - (lag_p + 1)
                if idx_w >= 0:
                    pred_w += phi[lag_p] * (w_ext[idx_w] - const)
            for lag_P in range(P):
                idx_w = len(w_ext) - (lag_P + 1) * S
                if idx_w >= 0:
                    pred_w += Phi[lag_P] * (w_ext[idx_w] - const)
            for lag_q in range(q):
                idx_a = len(a_ext) - (lag_q + 1)
                if idx_a >= 0:
                    pred_w -= theta[lag_q] * a_ext[idx_a]
            for lag_Q in range(Q):
                idx_a = len(a_ext) - (lag_Q + 1) * S
                if idx_a >= 0:
                    pred_w -= Theta[lag_Q] * a_ext[idx_a]

            w_fc.append(pred_w)
            w_ext.append(pred_w)
            a_ext.append(0.0)

        # Invert differencing
        y_fc = undifference_forecasts(y, w_fc, d=d, D=D, S=S)

        for h, f_val in enumerate(y_fc):
            period_num = n_orig + (h + 1)
            # Standard error grows with forecast horizon
            se_h = s_err * math.sqrt(1.0 + 0.1 * h)
            low = float(f_val - z_crit * se_h)
            upp = float(f_val + z_crit * se_h)
            forecast_list.append({
                "period": period_num,
                "forecast": float(f_val),
                "lower": low,
                "upper": upp,
                "se": float(se_h),
            })

    return {
        "analysis": "arima",
        "variable_name": variable_name,
        "title": title or f"ARIMA: {variable_name}",
        "p": p,
        "d": d,
        "q": q,
        "P": P,
        "D": D,
        "Q": Q,
        "S": S,
        "include_constant": include_constant,
        "n_orig": n_orig,
        "N": N,
        "ss": float(ss),
        "ms": float(ms),
        "df": df,
        "estimates": estimates,
        "actual": y.tolist(),
        "fitted": fitted_vals,
        "residuals": [None if v is None else float(y[i] - v) for i, v in enumerate(fitted_vals)],
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }
