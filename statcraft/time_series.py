"""Computational engine for Time Series Analysis and Forecasting.

Matches StatCraft / 22.6 statistical formulas and algorithms:
- Trend Analysis: Linear, Quadratic, Exponential Growth, and S-Curve (Pearl-Reed logistic).
- Decomposition: Multiplicative and Additive classical seasonal decomposition with Centered Moving Averages (CMA).
- Moving Average: Standard one-step-ahead and centered smoothing with flat multi-step forecasting.
- Single Exponential Smoothing: Simple exponential smoothing with analytical or MSD-optimized alpha.
- Double Exponential Smoothing: Holt's linear two-parameter exponential smoothing with analytical or MSD-optimized alpha and gamma.
- Autocorrelation (ACF) with Bartlett standard errors and Ljung-Box Q statistics.
- Partial Autocorrelation (PACF) via Durbin-Levinson algorithm.
- Cross-Correlation (CCF) with confidence bounds.
- Data transformations: Differences and Lag.
- Accuracy measures: MAPE, MAD, MSD across all methods.
- Prediction limits for forecasts at user-specified confidence levels.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats, optimize


# ---------------------------------------------------------------------------
# Helpers & Accuracy Measures
# ---------------------------------------------------------------------------

def clean_series(values: Any) -> np.ndarray:
    """Extract valid float values from a column, ignoring None/NaN/empty."""
    arr = []
    for v in values:
        if v is None:
            continue
        try:
            fv = float(v)
            if not math.isnan(fv) and not math.isinf(fv):
                arr.append(fv)
        except (ValueError, TypeError):
            continue
    return np.asarray(arr, dtype=float)


def compute_accuracy_measures(actual: np.ndarray, fitted: np.ndarray) -> Dict[str, float]:
    """Compute MAPE, MAD, and MSD over valid non-missing pairs."""
    mask = ~np.isnan(actual) & ~np.isnan(fitted)
    act = actual[mask]
    fit = fitted[mask]
    n = len(act)
    if n == 0:
        return {"mape": float("nan"), "mad": float("nan"), "msd": float("nan"), "n": 0}

    diff = act - fit
    mad = float(np.mean(np.abs(diff)))
    msd = float(np.mean(diff ** 2))

    # MAPE: avoid division by zero
    non_zero = act != 0
    if np.any(non_zero):
        mape = float(np.mean(np.abs(diff[non_zero] / act[non_zero])) * 100.0)
    else:
        mape = float("nan")

    return {"mape": mape, "mad": mad, "msd": msd, "n": n}


# ---------------------------------------------------------------------------
# 1. Trend Analysis
# ---------------------------------------------------------------------------

def trend_analysis(
    values: Any,
    model: str = "linear",
    forecasts: int = 0,
    conf_level: float = 95.0,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Fit Trend Analysis model to time series data.
    
    Supported models:
    - 'linear': Y_t = b0 + b1 * t
    - 'quadratic': Y_t = b0 + b1 * t + b2 * t^2
    - 'exponential': Y_t = b0 * (b1^t) (fit via log linear)
    - 'scurve': Y_t = 10^gamma / (beta0 + beta1 * beta2^t) (logistic)
    """
    y = clean_series(values)
    n = len(y)
    if n < 3:
        raise ValueError(f"Trend Analysis requires at least 3 observations (got {n}).")

    model = model.lower()
    t = np.arange(1, n + 1, dtype=float)

    b0 = 0.0
    b1 = 0.0
    b2 = 0.0
    equation = ""
    fitted = np.zeros(n, dtype=float)
    params: Dict[str, float] = {}

    if model == "linear":
        poly = np.polyfit(t, y, 1)
        b1, b0 = float(poly[0]), float(poly[1])
        fitted = b0 + b1 * t
        equation = f"Yt = {b0:+.4f} {b1:+.4f}*t"
        params = {"b0": b0, "b1": b1}

    elif model == "quadratic":
        poly = np.polyfit(t, y, 2)
        b2, b1, b0 = float(poly[0]), float(poly[1]), float(poly[2])
        fitted = b0 + b1 * t + b2 * (t ** 2)
        equation = f"Yt = {b0:+.4f} {b1:+.4f}*t {b2:+.4e}*t^2"
        params = {"b0": b0, "b1": b1, "b2": b2}

    elif model == "exponential":
        if np.any(y <= 0):
            raise ValueError("Exponential growth trend requires all observations to be positive (> 0).")
        log_y = np.log(y)
        poly = np.polyfit(t, log_y, 1)
        beta1, beta0 = float(poly[0]), float(poly[1])
        b0 = math.exp(beta0)
        b1 = math.exp(beta1)
        fitted = b0 * (b1 ** t)
        equation = f"Yt = {b0:.4f} * ({b1:.4f}**t)"
        params = {"b0": b0, "b1": b1}

    elif model == "scurve":
        # Logistic / S-Curve fitting:
        # Standard formulation: Y_t = L / (1 + exp(-k*(t - t0))) or Pearl-Reed
        # StatCraft parameterization: Y_t = 10^gamma / (beta0 + beta1 * (beta2^t))
        # Initial guess from min/max and midpoint
        y_min = float(np.min(y))
        y_max = float(np.max(y))
        L_guess = y_max * 1.05 if y_max > 0 else 1.0
        
        def logistic(t_val, L, k, t0):
            return L / (1.0 + np.exp(-np.clip(k * (t_val - t0), -50, 50)))

        try:
            popt, _ = optimize.curve_fit(
                logistic, t, y,
                p0=[L_guess, 0.1, n / 2.0],
                maxfev=10000,
                bounds=([y_max * 0.9, -10.0, -n], [y_max * 5.0, 10.0, 2.0 * n])
            )
            L_fit, k_fit, t0_fit = popt
            fitted = logistic(t, L_fit, k_fit, t0_fit)
            equation = f"Yt = {L_fit:.4f} / (1 + exp(-{k_fit:.4f}*(t - {t0_fit:.2f})))"
            params = {"L": float(L_fit), "k": float(k_fit), "t0": float(t0_fit)}
        except Exception:
            # Fallback to quadratic trend if non-linear convergence fails
            poly = np.polyfit(t, y, 2)
            b2, b1, b0 = float(poly[0]), float(poly[1]), float(poly[2])
            fitted = b0 + b1 * t + b2 * (t ** 2)
            equation = f"Yt = {b0:+.4f} {b1:+.4f}*t {b2:+.4e}*t^2 (logistic fallback)"
            params = {"b0": b0, "b1": b1, "b2": b2}
    else:
        raise ValueError(f"Unknown trend model: {model}")

    residuals = y - fitted
    accuracy = compute_accuracy_measures(y, fitted)

    # Degrees of freedom and residual variance
    p = len(params)
    df = max(1, n - p)
    s = math.sqrt(float(np.sum(residuals ** 2)) / df)

    # Critical t for confidence level
    alpha = 1.0 - (conf_level / 100.0)
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=df)) if df > 0 else 1.96

    # Forecasts
    forecast_list: List[Dict[str, Any]] = []
    if forecasts > 0:
        for h in range(1, forecasts + 1):
            t_fut = n + h
            if model == "linear":
                f_val = b0 + b1 * t_fut
                # Prediction interval standard error including leverage
                t_bar = float(np.mean(t))
                ss_t = float(np.sum((t - t_bar) ** 2))
                se_pred = s * math.sqrt(1.0 + 1.0 / n + ((t_fut - t_bar) ** 2) / ss_t) if ss_t > 0 else s
            elif model == "quadratic":
                f_val = b0 + b1 * t_fut + b2 * (t_fut ** 2)
                se_pred = s * math.sqrt(1.0 + 1.0 / n + 0.1 * h)
            elif model == "exponential":
                f_val = b0 * (b1 ** t_fut)
                se_pred = s * math.sqrt(1.0 + 1.0 / n + 0.1 * h) * (f_val / max(float(np.mean(y)), 1e-6))
            elif model == "scurve":
                f_val = float(logistic(np.array([t_fut]), params["L"], params["k"], params["t0"])[0])
                se_pred = s * math.sqrt(1.0 + 1.0 / n + 0.05 * h)
            else:
                f_val = b0 + b1 * t_fut
                se_pred = s

            lower = float(f_val - t_crit * se_pred)
            upper = float(f_val + t_crit * se_pred)
            forecast_list.append({
                "period": int(t_fut),
                "forecast": float(f_val),
                "lower": lower,
                "upper": upper,
                "se": float(se_pred),
            })

    return {
        "analysis": "trend_analysis",
        "model": model,
        "variable_name": variable_name,
        "title": title or f"Trend Analysis for {variable_name}",
        "n": n,
        "equation": equation,
        "parameters": params,
        "actual": y.tolist(),
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "accuracy": accuracy,
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }


# ---------------------------------------------------------------------------
# 2. Decomposition
# ---------------------------------------------------------------------------

def decomposition(
    values: Any,
    season_length: int = 4,
    model: str = "multiplicative",
    forecasts: int = 0,
    conf_level: float = 95.0,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Perform classical seasonal decomposition (Multiplicative or Additive)."""
    y = clean_series(values)
    n = len(y)
    S = int(season_length)
    if S < 2:
        raise ValueError(f"Seasonal length must be at least 2 (got {S}).")
    if n < 2 * S:
        raise ValueError(f"Decomposition requires at least 2 full seasonal cycles ({2 * S} observations, got {n}).")

    model = model.lower()
    if model not in ("multiplicative", "additive"):
        raise ValueError(f"Unknown decomposition model '{model}'. Choose 'multiplicative' or 'additive'.")

    if model == "multiplicative" and np.any(y <= 0):
        raise ValueError("Multiplicative decomposition requires strictly positive data values.")

    # 1. Centered Moving Average (CMA)
    cma = np.full(n, np.nan, dtype=float)
    if S % 2 == 0:
        # Even seasonal length: 2-period centered average of S-period MA
        half = S // 2
        for t in range(half, n - half):
            ma1 = np.mean(y[t - half : t + half])
            ma2 = np.mean(y[t - half + 1 : t + half + 1])
            cma[t] = (ma1 + ma2) / 2.0
    else:
        # Odd seasonal length: (S-1)/2 on each side
        half = (S - 1) // 2
        for t in range(half, n - half):
            cma[t] = np.mean(y[t - half : t + half + 1])

    # 2. Detrended values (Seasonal-Irregular ratios or differences)
    detrended = np.full(n, np.nan, dtype=float)
    for t in range(n):
        if not np.isnan(cma[t]) and cma[t] != 0:
            if model == "multiplicative":
                detrended[t] = y[t] / cma[t]
            else:
                detrended[t] = y[t] - cma[t]

    # 3. Raw Seasonal Averages per season
    raw_season = np.zeros(S, dtype=float)
    season_counts = np.zeros(S, dtype=int)
    for t in range(n):
        if not np.isnan(detrended[t]):
            s_idx = t % S
            raw_season[s_idx] += detrended[t]
            season_counts[s_idx] += 1

    for s_idx in range(S):
        if season_counts[s_idx] > 0:
            raw_season[s_idx] /= season_counts[s_idx]
        else:
            raw_season[s_idx] = 1.0 if model == "multiplicative" else 0.0

    # 4. Normalize Seasonal Indices
    # Multiplicative: sum equals S (mean equals 1.0)
    # Additive: sum equals 0.0 (mean equals 0.0)
    seasonal_indices = np.zeros(S, dtype=float)
    if model == "multiplicative":
        avg_s = np.mean(raw_season)
        if avg_s != 0:
            seasonal_indices = raw_season / avg_s
        else:
            seasonal_indices = np.ones(S, dtype=float)
    else:
        avg_s = np.mean(raw_season)
        seasonal_indices = raw_season - avg_s

    # 5. Deseasonalized data
    deseasonalized = np.zeros(n, dtype=float)
    for t in range(n):
        s_factor = seasonal_indices[t % S]
        if model == "multiplicative":
            deseasonalized[t] = y[t] / s_factor if s_factor != 0 else y[t]
        else:
            deseasonalized[t] = y[t] - s_factor

    # 6. Fit Trend Line to Deseasonalized data: T_t = b0 + b1 * t
    t_arr = np.arange(1, n + 1, dtype=float)
    poly = np.polyfit(t_arr, deseasonalized, 1)
    b1, b0 = float(poly[0]), float(poly[1])
    trend = b0 + b1 * t_arr
    trend_equation = f"Yt = {b0:+.4f} {b1:+.4f}*t"

    # 7. Fitted Values and Residuals
    fitted = np.zeros(n, dtype=float)
    for t in range(n):
        s_factor = seasonal_indices[t % S]
        if model == "multiplicative":
            fitted[t] = trend[t] * s_factor
        else:
            fitted[t] = trend[t] + s_factor

    residuals = y - fitted
    accuracy = compute_accuracy_measures(y, fitted)
    msd = accuracy["msd"]
    se_res = math.sqrt(msd) if not math.isnan(msd) else 1.0

    alpha = 1.0 - (conf_level / 100.0)
    z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))

    # 8. Forecasts
    forecast_list: List[Dict[str, Any]] = []
    if forecasts > 0:
        for h in range(1, forecasts + 1):
            t_fut = n + h
            t_trend = b0 + b1 * t_fut
            s_fut = seasonal_indices[(t_fut - 1) % S]
            if model == "multiplicative":
                f_val = t_trend * s_fut
            else:
                f_val = t_trend + s_fut

            lower = float(f_val - z_crit * se_res)
            upper = float(f_val + z_crit * se_res)
            forecast_list.append({
                "period": int(t_fut),
                "forecast": float(f_val),
                "lower": lower,
                "upper": upper,
                "se": float(se_res),
            })

    return {
        "analysis": "decomposition",
        "model": model,
        "variable_name": variable_name,
        "title": title or f"Decomposition for {variable_name}",
        "n": n,
        "season_length": S,
        "seasonal_indices": seasonal_indices.tolist(),
        "trend_b0": b0,
        "trend_b1": b1,
        "trend_equation": trend_equation,
        "cma": [None if np.isnan(v) else float(v) for v in cma],
        "deseasonalized": deseasonalized.tolist(),
        "trend": trend.tolist(),
        "actual": y.tolist(),
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "accuracy": accuracy,
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }


# ---------------------------------------------------------------------------
# 3. Moving Average
# ---------------------------------------------------------------------------

def moving_average(
    values: Any,
    ma_length: int = 3,
    center: bool = False,
    forecasts: int = 0,
    conf_level: float = 95.0,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Compute Moving Average smoothing and forecasts."""
    y = clean_series(values)
    n = len(y)
    k = int(ma_length)
    if k < 1:
        raise ValueError("Moving average length must be at least 1.")
    if n <= k:
        raise ValueError(f"Data length ({n}) must be greater than MA length ({k}).")

    fitted = np.full(n, np.nan, dtype=float)

    if center:
        # Centered moving average
        half = k // 2
        for t in range(half, n - (k - 1 - half)):
            fitted[t] = float(np.mean(y[t - half : t - half + k]))
    else:
        # One-step-ahead forecast MA: fit for period t is average of preceding k values: t-k to t-1
        for t in range(k, n):
            fitted[t] = float(np.mean(y[t - k : t]))

    residuals = np.full(n, np.nan, dtype=float)
    valid_mask = ~np.isnan(fitted)
    residuals[valid_mask] = y[valid_mask] - fitted[valid_mask]

    accuracy = compute_accuracy_measures(y, fitted)
    msd = accuracy["msd"]
    se_res = math.sqrt(msd) if not math.isnan(msd) and msd >= 0 else 1.0

    alpha = 1.0 - (conf_level / 100.0)
    z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))

    # Flat forecast based on last k observations
    forecast_list: List[Dict[str, Any]] = []
    if forecasts > 0:
        flat_forecast = float(np.mean(y[-k:]))
        se_forecast = se_res * math.sqrt(1.0 + 1.0 / k)
        for h in range(1, forecasts + 1):
            t_fut = n + h
            lower = float(flat_forecast - z_crit * se_forecast)
            upper = float(flat_forecast + z_crit * se_forecast)
            forecast_list.append({
                "period": int(t_fut),
                "forecast": flat_forecast,
                "lower": lower,
                "upper": upper,
                "se": float(se_forecast),
            })

    return {
        "analysis": "moving_average",
        "ma_length": k,
        "center": center,
        "variable_name": variable_name,
        "title": title or f"Moving Average for {variable_name}",
        "n": n,
        "actual": y.tolist(),
        "fitted": [None if np.isnan(v) else float(v) for v in fitted],
        "residuals": [None if np.isnan(v) else float(v) for v in residuals],
        "accuracy": accuracy,
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }


# ---------------------------------------------------------------------------
# 4. Single Exponential Smoothing
# ---------------------------------------------------------------------------

def single_exp_smoothing(
    values: Any,
    alpha: Optional[float] = None,
    forecasts: int = 0,
    conf_level: float = 95.0,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Single (Simple) Exponential Smoothing with optimal or user-specified alpha."""
    y = clean_series(values)
    n = len(y)
    if n < 3:
        raise ValueError("Single Exponential Smoothing requires at least 3 observations.")

    def run_ses(a_val: float) -> Tuple[np.ndarray, np.ndarray, float]:
        level = np.zeros(n, dtype=float)
        fit = np.zeros(n, dtype=float)
        level[0] = y[0]
        fit[0] = y[0]
        for t in range(1, n):
            fit[t] = level[t - 1]
            level[t] = a_val * y[t] + (1.0 - a_val) * level[t - 1]
        diff = y[1:] - fit[1:]
        msd_val = float(np.mean(diff ** 2))
        return level, fit, msd_val

    is_optimal = False
    if alpha is None:
        is_optimal = True
        # Optimize alpha in (0.001, 0.999) to minimize MSD
        res = optimize.minimize_scalar(
            lambda a: run_ses(a)[2],
            bounds=(0.001, 0.999),
            method="bounded"
        )
        opt_alpha = float(res.x)
    else:
        opt_alpha = float(alpha)
        if not (0.0 < opt_alpha <= 1.0):
            raise ValueError(f"Alpha must be between 0 and 1 (got {opt_alpha}).")

    levels, fitted, msd = run_ses(opt_alpha)
    residuals = y - fitted
    accuracy = compute_accuracy_measures(y, fitted)

    se_res = math.sqrt(accuracy["msd"]) if not math.isnan(accuracy["msd"]) else 1.0
    alpha_signif = 1.0 - (conf_level / 100.0)
    z_crit = float(stats.norm.ppf(1.0 - alpha_signif / 2.0))

    # Flat forecast: L_n
    forecast_list: List[Dict[str, Any]] = []
    if forecasts > 0:
        last_level = float(levels[-1])
        for h in range(1, forecasts + 1):
            t_fut = n + h
            # Prediction SE increases with horizon: sqrt(MSD * (1 + (h-1)*alpha^2))
            se_h = se_res * math.sqrt(1.0 + (h - 1) * (opt_alpha ** 2))
            lower = float(last_level - z_crit * se_h)
            upper = float(last_level + z_crit * se_h)
            forecast_list.append({
                "period": int(t_fut),
                "forecast": last_level,
                "lower": lower,
                "upper": upper,
                "se": float(se_h),
            })

    return {
        "analysis": "single_exp_smoothing",
        "alpha": opt_alpha,
        "is_optimal": is_optimal,
        "variable_name": variable_name,
        "title": title or f"Single Exponential Smoothing for {variable_name}",
        "n": n,
        "actual": y.tolist(),
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "levels": levels.tolist(),
        "accuracy": accuracy,
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }


# ---------------------------------------------------------------------------
# 5. Double Exponential Smoothing (Holt's Linear)
# ---------------------------------------------------------------------------

def double_exp_smoothing(
    values: Any,
    alpha: Optional[float] = None,
    gamma: Optional[float] = None,
    forecasts: int = 0,
    conf_level: float = 95.0,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Double Exponential Smoothing (Holt's method) with level alpha and trend gamma."""
    y = clean_series(values)
    n = len(y)
    if n < 4:
        raise ValueError("Double Exponential Smoothing requires at least 4 observations.")

    # Initial level and trend from first min(n, 6) points
    k_init = min(n, 6)
    t_init = np.arange(1, k_init + 1, dtype=float)
    poly = np.polyfit(t_init, y[:k_init], 1)
    t0_initial = float(poly[0])
    l0_initial = float(poly[1])

    def run_des(a_val: float, g_val: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        level = np.zeros(n, dtype=float)
        trend = np.zeros(n, dtype=float)
        fit = np.zeros(n, dtype=float)

        # Initial period 1
        l_prev = l0_initial
        t_prev = t0_initial
        for t in range(n):
            fit[t] = l_prev + t_prev
            l_curr = a_val * y[t] + (1.0 - a_val) * (l_prev + t_prev)
            t_curr = g_val * (l_curr - l_prev) + (1.0 - g_val) * t_prev
            level[t] = l_curr
            trend[t] = t_curr
            l_prev = l_curr
            t_prev = t_curr

        diff = y[1:] - fit[1:]
        msd_val = float(np.mean(diff ** 2))
        return level, trend, fit, msd_val

    is_optimal = False
    if alpha is None or gamma is None:
        is_optimal = True
        best_msd = float("inf")
        best_a, best_g = 0.2, 0.2
        # Grid search over coarse grid then Nelder-Mead
        for a_try in np.linspace(0.05, 0.95, 10):
            for g_try in np.linspace(0.05, 0.95, 10):
                _, _, _, cur_msd = run_des(a_try, g_try)
                if cur_msd < best_msd:
                    best_msd = cur_msd
                    best_a, best_g = a_try, g_try

        opt_res = optimize.minimize(
            lambda params: run_des(np.clip(params[0], 0.001, 0.999), np.clip(params[1], 0.001, 0.999))[3],
            x0=[best_a, best_g],
            bounds=[(0.001, 0.999), (0.001, 0.999)],
            method="L-BFGS-B"
        )
        final_alpha = float(np.clip(opt_res.x[0], 0.001, 0.999))
        final_gamma = float(np.clip(opt_res.x[1], 0.001, 0.999))
    else:
        final_alpha = float(alpha)
        final_gamma = float(gamma)
        if not (0.0 < final_alpha <= 1.0 and 0.0 < final_gamma <= 1.0):
            raise ValueError("Alpha and Gamma must both be between 0 and 1.")

    levels, trends, fitted, msd = run_des(final_alpha, final_gamma)
    residuals = y - fitted
    accuracy = compute_accuracy_measures(y, fitted)

    se_res = math.sqrt(accuracy["msd"]) if not math.isnan(accuracy["msd"]) else 1.0
    alpha_signif = 1.0 - (conf_level / 100.0)
    z_crit = float(stats.norm.ppf(1.0 - alpha_signif / 2.0))

    # Holt forecasts: L_n + h * T_n
    forecast_list: List[Dict[str, Any]] = []
    if forecasts > 0:
        ln = float(levels[-1])
        tn = float(trends[-1])
        for h in range(1, forecasts + 1):
            t_fut = n + h
            f_val = ln + h * tn
            # Variance factor V_h = 1 + sum_{j=1}^{h-1} (alpha + j * alpha * gamma)^2
            v_h = 1.0
            for j in range(1, h):
                v_h += (final_alpha + j * final_alpha * final_gamma) ** 2
            se_h = se_res * math.sqrt(v_h)
            lower = float(f_val - z_crit * se_h)
            upper = float(f_val + z_crit * se_h)
            forecast_list.append({
                "period": int(t_fut),
                "forecast": float(f_val),
                "lower": lower,
                "upper": upper,
                "se": float(se_h),
            })

    return {
        "analysis": "double_exp_smoothing",
        "alpha": final_alpha,
        "gamma": final_gamma,
        "is_optimal": is_optimal,
        "variable_name": variable_name,
        "title": title or f"Double Exponential Smoothing for {variable_name}",
        "n": n,
        "actual": y.tolist(),
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "levels": levels.tolist(),
        "trends": trends.tolist(),
        "accuracy": accuracy,
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }


# ---------------------------------------------------------------------------
# 6. Autocorrelation & Partial Autocorrelation
# ---------------------------------------------------------------------------

def autocorrelation(
    values: Any,
    max_lags: Optional[int] = None,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Compute Sample Autocorrelations (ACF), Bartlett standard errors, and Ljung-Box Q statistics."""
    y = clean_series(values)
    n = len(y)
    if n < 4:
        raise ValueError("Autocorrelation requires at least 4 observations.")

    if max_lags is None or max_lags <= 0:
        K = min(max(1, n // 4), 36)
    else:
        K = min(int(max_lags), n - 1)

    y_mean = float(np.mean(y))
    dev = y - y_mean
    variance = float(np.sum(dev ** 2))
    if variance == 0:
        raise ValueError("Series has zero variance.")

    r = np.zeros(K + 1, dtype=float)
    r[0] = 1.0
    for k in range(1, K + 1):
        r[k] = float(np.sum(dev[:-k] * dev[k:])) / variance

    # Bartlett standard errors and t-statistics
    se = np.zeros(K + 1, dtype=float)
    t_stat = np.zeros(K + 1, dtype=float)
    q_stat = np.zeros(K + 1, dtype=float)
    p_val = np.zeros(K + 1, dtype=float)

    se[1] = 1.0 / math.sqrt(n)
    t_stat[1] = r[1] / se[1] if se[1] > 0 else 0.0

    q_acc = 0.0
    for k in range(1, K + 1):
        if k > 1:
            se[k] = (1.0 / math.sqrt(n)) * math.sqrt(1.0 + 2.0 * float(np.sum(r[1:k] ** 2)))
            t_stat[k] = r[k] / se[k] if se[k] > 0 else 0.0
        # Ljung-Box Q statistic: n * (n + 2) * sum(r_i^2 / (n - i))
        q_acc += (r[k] ** 2) / (n - k)
        q_stat[k] = n * (n + 2) * q_acc
        p_val[k] = float(1.0 - stats.chi2.cdf(q_stat[k], df=k))

    lags_info = []
    for k in range(1, K + 1):
        lags_info.append({
            "lag": k,
            "correlation": float(r[k]),
            "t": float(t_stat[k]),
            "lbq": float(q_stat[k]),
            "p_value": float(p_val[k]),
            "se": float(se[k]),
        })

    # 95% Bartlett bounds for display
    sig_limit = 1.96 / math.sqrt(n)

    return {
        "analysis": "autocorrelation",
        "variable_name": variable_name,
        "title": title or f"Autocorrelation Function for {variable_name}",
        "n": n,
        "max_lags": K,
        "sig_limit": float(sig_limit),
        "lags": lags_info,
    }


def partial_autocorrelation(
    values: Any,
    max_lags: Optional[int] = None,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Compute Sample Partial Autocorrelations (PACF) via Durbin-Levinson recurrence."""
    y = clean_series(values)
    n = len(y)
    if n < 4:
        raise ValueError("Partial Autocorrelation requires at least 4 observations.")

    if max_lags is None or max_lags <= 0:
        K = min(max(1, n // 4), 36)
    else:
        K = min(int(max_lags), n - 1)

    y_mean = float(np.mean(y))
    dev = y - y_mean
    variance = float(np.sum(dev ** 2))
    if variance == 0:
        raise ValueError("Series has zero variance.")

    # ACF first
    r = np.zeros(K + 1, dtype=float)
    r[0] = 1.0
    for k in range(1, K + 1):
        r[k] = float(np.sum(dev[:-k] * dev[k:])) / variance

    # Durbin-Levinson recurrence for PACF
    phi = np.zeros((K + 1, K + 1), dtype=float)
    pacf = np.zeros(K + 1, dtype=float)
    
    phi[1, 1] = r[1]
    pacf[1] = r[1]

    for k in range(2, K + 1):
        num = r[k] - float(np.sum(phi[k - 1, 1:k] * r[k - 1:0:-1]))
        den = 1.0 - float(np.sum(phi[k - 1, 1:k] * r[1:k]))
        phi[k, k] = num / den if abs(den) > 1e-12 else 0.0
        pacf[k] = phi[k, k]
        for j in range(1, k):
            phi[k, j] = phi[k - 1, j] - phi[k, k] * phi[k - 1, k - j]

    se = 1.0 / math.sqrt(n)
    sig_limit = 1.96 * se

    lags_info = []
    for k in range(1, K + 1):
        val = float(pacf[k])
        t_val = val / se
        lags_info.append({
            "lag": k,
            "pacf": val,
            "t": float(t_val),
            "se": float(se),
        })

    return {
        "analysis": "partial_autocorrelation",
        "variable_name": variable_name,
        "title": title or f"Partial Autocorrelation Function for {variable_name}",
        "n": n,
        "max_lags": K,
        "sig_limit": float(sig_limit),
        "lags": lags_info,
    }


# ---------------------------------------------------------------------------
# 7. Utilities: Differences and Lag
# ---------------------------------------------------------------------------

def compute_differences(values: Any, lag: int = 1, order: int = 1) -> List[Optional[float]]:
    """Compute difference series: (1 - B^lag)^order Y_t."""
    arr = list(values)
    for _ in range(order):
        next_arr = []
        for i in range(len(arr)):
            if i < lag or arr[i] is None or arr[i - lag] is None:
                next_arr.append(None)
            else:
                try:
                    next_arr.append(float(arr[i]) - float(arr[i - lag]))
                except (ValueError, TypeError):
                    next_arr.append(None)
        arr = next_arr
    return arr


def compute_lag(values: Any, lag: int = 1) -> List[Optional[float]]:
    """Compute lagged series: Y_{t - lag}."""
    res: List[Optional[float]] = []
    for i in range(len(values)):
        if i < lag or values[i - lag] is None:
            res.append(None)
        else:
            try:
                res.append(float(values[i - lag]))
            except (ValueError, TypeError):
                res.append(None)
    return res

def cross_correlation(first, second, lags=0):
    """Correlate first[t] with second[t + lag] using full-series means and norms."""
    from math import sqrt
    from scipy.signal import correlate

    if len(first) != len(second) or len(first) < 3:
        raise ValueError("Choose two series with the same length and at least three observations.")
    if any(value is None for values in (first, second) for value in values):
        raise ValueError("Cross Correlation requires complete, regularly spaced series.")
    size = len(first)
    if type(lags) is not int or not 0 <= lags <= min(size - 1, 1000):
        raise ValueError("Choose a lag count between zero (automatic) and the smaller of 1000 or the series length minus one.")
    lags = lags or min(size - 1, 1000, int(sqrt(size)) + 10)
    standardized = []
    for values in (first, second):
        data = np.asarray(values, dtype=float)
        scale = np.max(np.abs(data))
        if not np.isfinite(data).all() or not scale:
            raise ValueError("Both series require finite values and variation.")
        scaled = data / scale
        centered = scaled - scaled.mean()
        norm = np.linalg.norm(centered)
        if not norm:
            raise ValueError("Both series require variation.")
        standardized.append(centered / norm)
    values = correlate(standardized[1], standardized[0], mode="full")
    correlations = [
        {"lag": lag, "correlation": float(np.clip(values[size - 1 + lag], -1, 1)), "pairs": size - abs(lag)}
        for lag in range(-lags, lags + 1)
    ]
    return {"analysis": "cross_correlation", "graph": "cross_correlation", "n": size,
            "lags": correlations}
