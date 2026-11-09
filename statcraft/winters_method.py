"""Computational engine for Winters' Method Exponential Smoothing (Triple Exponential Smoothing).

Matches Minitab statistical formulas and algorithms:
- Multiplicative and Additive Holt-Winters triple exponential smoothing.
- Initial Level (L0) and Trend (T0) estimated from linear trend on first 2*S observations.
- Initial Seasonal components normalized to average 1.0 (multiplicative) or sum 0.0 (additive).
- Recursive updates for Level (alpha), Trend (gamma), and Seasonal (delta).
- Global optimization of smoothing parameters (alpha, gamma, delta) minimizing MSD.
- Accuracy measures: MAPE, MAD, MSD.
- Multi-step out-of-sample forecasting with prediction intervals.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats, optimize


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

    non_zero = act != 0
    if np.any(non_zero):
        mape = float(np.mean(np.abs(diff[non_zero] / act[non_zero])) * 100.0)
    else:
        mape = float("nan")

    return {"mape": mape, "mad": mad, "msd": msd, "n": n}


def winters_method(
    values: Any,
    season_length: int = 4,
    model: str = "multiplicative",
    alpha: Optional[float] = None,
    gamma: Optional[float] = None,
    delta: Optional[float] = None,
    forecasts: int = 0,
    conf_level: float = 95.0,
    variable_name: str = "Series",
    title: str = "",
) -> Dict[str, Any]:
    """Winters' Method Triple Exponential Smoothing with Level, Trend, and Seasonal parameters.
    
    Supports Multiplicative and Additive formulations, optimal parameter estimation,
    one-step-ahead within-sample fits, and out-of-sample multi-step forecasts with prediction limits.
    """
    y = clean_series(values)
    n = len(y)
    S = int(season_length)
    if S < 2:
        raise ValueError(f"Seasonal length must be at least 2 (got {S}).")
    if n < 2 * S:
        raise ValueError(f"Winters' Method requires at least two full seasonal cycles ({2 * S} observations, got {n}).")

    model = str(model).lower().strip()
    if model not in ("multiplicative", "additive"):
        raise ValueError(f"Unknown model '{model}'. Choose 'multiplicative' or 'additive'.")

    if model == "multiplicative" and np.any(y <= 0):
        raise ValueError("Multiplicative Winters' method requires strictly positive data values.")

    # 1. Initial values from first 2 seasonal cycles (2*S points)
    k_init = 2 * S
    t_init = np.arange(1, k_init + 1, dtype=float)
    poly = np.polyfit(t_init, y[:k_init], 1)
    t0_initial = float(poly[0])
    l0_initial = float(poly[1])

    trend_init_line = l0_initial + t0_initial * t_init
    if model == "multiplicative":
        detrended_init = y[:k_init] / trend_init_line
    else:
        detrended_init = y[:k_init] - trend_init_line

    # Average detrended values per season
    raw_s = np.zeros(S, dtype=float)
    for s_idx in range(S):
        raw_s[s_idx] = (detrended_init[s_idx] + detrended_init[s_idx + S]) / 2.0

    # Normalize initial seasonal factors
    initial_seasonals = np.zeros(S, dtype=float)
    if model == "multiplicative":
        avg_s = float(np.mean(raw_s))
        if avg_s != 0:
            initial_seasonals = raw_s / avg_s
        else:
            initial_seasonals = np.ones(S, dtype=float)
    else:
        avg_s = float(np.mean(raw_s))
        initial_seasonals = raw_s - avg_s

    def run_winters(
        a_val: float, g_val: float, d_val: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        level = np.zeros(n, dtype=float)
        trend = np.zeros(n, dtype=float)
        season = np.zeros(n + S, dtype=float)
        fit = np.zeros(n, dtype=float)

        season[:S] = initial_seasonals

        l_prev = l0_initial
        t_prev = t0_initial

        for t in range(n):
            s_prev = season[t]

            # Fit for period t (one-step-ahead forecast using information up to t-1)
            if model == "multiplicative":
                fit_t = (l_prev + t_prev) * s_prev
            else:
                fit_t = l_prev + t_prev + s_prev
            fit[t] = fit_t

            # Level update
            if model == "multiplicative":
                s_safe = s_prev if abs(s_prev) > 1e-12 else 1e-12
                l_curr = a_val * (y[t] / s_safe) + (1.0 - a_val) * (l_prev + t_prev)
            else:
                l_curr = a_val * (y[t] - s_prev) + (1.0 - a_val) * (l_prev + t_prev)

            # Trend update
            t_curr = g_val * (l_curr - l_prev) + (1.0 - g_val) * t_prev

            # Seasonal update
            if model == "multiplicative":
                l_safe = l_curr if abs(l_curr) > 1e-12 else 1e-12
                s_curr = d_val * (y[t] / l_safe) + (1.0 - d_val) * s_prev
            else:
                s_curr = d_val * (y[t] - l_curr) + (1.0 - d_val) * s_prev

            level[t] = l_curr
            trend[t] = t_curr
            season[t + S] = s_curr

            l_prev = l_curr
            t_prev = t_curr

        diff = y - fit
        msd_val = float(np.mean(diff ** 2))
        return level, trend, season, fit, msd_val

    is_optimal = False
    if alpha is None or gamma is None or delta is None:
        is_optimal = True
        best_msd = float("inf")
        best_a, best_g, best_d = 0.2, 0.2, 0.2

        grid_pts = [0.1, 0.3, 0.5, 0.7, 0.9]
        for a_try in grid_pts:
            for g_try in grid_pts:
                for d_try in grid_pts:
                    _, _, _, _, cur_msd = run_winters(a_try, g_try, d_try)
                    if cur_msd < best_msd:
                        best_msd = cur_msd
                        best_a, best_g, best_d = a_try, g_try, d_try

        opt_res = optimize.minimize(
            lambda p: run_winters(
                float(np.clip(p[0], 0.001, 0.999)),
                float(np.clip(p[1], 0.001, 0.999)),
                float(np.clip(p[2], 0.001, 0.999)),
            )[4],
            x0=[best_a, best_g, best_d],
            bounds=[(0.001, 0.999), (0.001, 0.999), (0.001, 0.999)],
            method="L-BFGS-B",
        )
        final_alpha = float(np.clip(opt_res.x[0], 0.001, 0.999))
        final_gamma = float(np.clip(opt_res.x[1], 0.001, 0.999))
        final_delta = float(np.clip(opt_res.x[2], 0.001, 0.999))
    else:
        final_alpha = float(alpha)
        final_gamma = float(gamma)
        final_delta = float(delta)
        if not (0.0 < final_alpha <= 1.0 and 0.0 < final_gamma <= 1.0 and 0.0 < final_delta <= 1.0):
            raise ValueError("Alpha, Gamma, and Delta must all be between 0 and 1.")

    levels, trends, seasons, fitted, msd = run_winters(final_alpha, final_gamma, final_delta)
    residuals = y - fitted
    accuracy = compute_accuracy_measures(y, fitted)

    se_res = math.sqrt(accuracy["msd"]) if not math.isnan(accuracy["msd"]) else 1.0
    alpha_signif = 1.0 - (conf_level / 100.0)
    z_crit = float(stats.norm.ppf(1.0 - alpha_signif / 2.0))

    # Forecasts: L_n + h * T_n combined with seasonal factor S_{n+h}
    forecast_list: List[Dict[str, Any]] = []
    if forecasts > 0:
        ln = float(levels[-1])
        tn = float(trends[-1])
        for h in range(1, forecasts + 1):
            t_fut = n + h
            # Find seasonal component: cycle index in most recent S seasonal factors
            s_idx = n + ((h - 1) % S)
            s_factor = float(seasons[s_idx])

            if model == "multiplicative":
                f_val = (ln + h * tn) * s_factor
            else:
                f_val = ln + h * tn + s_factor

            # Prediction SE accounts for horizon uncertainty
            var_mult = 1.0 + (h - 1) * (final_alpha ** 2)
            se_h = se_res * math.sqrt(var_mult)
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
        "analysis": "winters_method",
        "model": model,
        "season_length": S,
        "alpha": final_alpha,
        "gamma": final_gamma,
        "delta": final_delta,
        "is_optimal": is_optimal,
        "variable_name": variable_name,
        "title": title or f"Winters' Method Plot for {variable_name}",
        "n": n,
        "actual": y.tolist(),
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "levels": levels.tolist(),
        "trends": trends.tolist(),
        "seasonals": seasons[-S:].tolist(),
        "accuracy": accuracy,
        "forecasts": forecast_list,
        "conf_level": conf_level,
    }
