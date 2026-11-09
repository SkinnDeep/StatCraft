"""Computational engine for Orthogonal Regression (Deming Regression).

Provides 1:1 parity with Minitab Orthogonal Regression:
- Fits y = beta_0 + beta_1 * x when both X and Y contain measurement error.
- Error variance ratio: delta = Var(error_y) / Var(error_x) (default delta = 1.0).
- Analytical Deming estimator for slope and intercept.
- Jackknife standard errors and Student's t confidence intervals.
- Hypothesis tests:
    * Test for constant bias: H0: beta_0 = 0 vs H1: beta_0 != 0
    * Test for proportional bias: H0: beta_1 = 1 vs H1: beta_1 != 1
- Error variance estimates for X and Y.
- Latent true values and orthogonal residuals.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import stats


def clean_orthogonal_data(
    response: Sequence[Any],
    predictor: Sequence[Any],
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """Clean paired response and predictor measurements."""
    n_raw = min(len(response), len(predictor))
    valid_y: List[float] = []
    valid_x: List[float] = []
    valid_indices: List[int] = []

    for i in range(n_raw):
        y_val = response[i]
        x_val = predictor[i]
        if y_val is None or x_val is None:
            continue
        try:
            fy = float(y_val)
            fx = float(x_val)
            if math.isnan(fy) or math.isinf(fy) or math.isnan(fx) or math.isinf(fx):
                continue
            valid_y.append(fy)
            valid_x.append(fx)
            valid_indices.append(i)
        except (ValueError, TypeError):
            continue

    return np.asarray(valid_y, dtype=float), np.asarray(valid_x, dtype=float), valid_indices


def _deming_fit(x: np.ndarray, y: np.ndarray, delta: float) -> Tuple[float, float]:
    """Compute Deming slope and intercept for given x, y, and error variance ratio delta."""
    n = len(x)
    mx = float(np.mean(x))
    my = float(np.mean(y))

    s_xx = float(np.sum((x - mx) ** 2))
    s_yy = float(np.sum((y - my) ** 2))
    s_xy = float(np.sum((x - mx) * (y - my)))

    if abs(s_xy) < 1e-12:
        # If no covariance, slope defaults to 0 or sign of correlation
        return my, 0.0

    term1 = delta * s_yy - s_xx
    disc = term1 ** 2 + 4.0 * delta * (s_xy ** 2)
    slope = (term1 + math.sqrt(max(0.0, disc))) / (2.0 * delta * s_xy)

    # Ensure slope sign matches s_xy
    if (s_xy < 0 and slope > 0) or (s_xy > 0 and slope < 0):
        slope = (term1 - math.sqrt(max(0.0, disc))) / (2.0 * delta * s_xy)

    intercept = my - slope * mx
    return intercept, slope


def fit_orthogonal_regression(
    response: Sequence[Any],
    predictor: Sequence[Any],
    error_variance_ratio: float = 1.0,
    response_name: str = "Y",
    predictor_name: str = "X",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Fit Orthogonal (Deming) Regression matching Minitab methods and formulas."""
    y, x, valid_indices = clean_orthogonal_data(response, predictor)
    n = len(y)
    if n < 3:
        raise ValueError("At least 3 valid observations required for orthogonal regression.")

    delta = float(error_variance_ratio)
    if delta <= 0:
        raise ValueError("Error variance ratio must be a positive number.")

    # Full data fit
    b0, b1 = _deming_fit(x, y, delta)

    # Jackknife variance estimation (Minitab standard)
    jack_b0 = np.zeros(n, dtype=float)
    jack_b1 = np.zeros(n, dtype=float)

    for i in range(n):
        idx = [k for k in range(n) if k != i]
        x_sub = x[idx]
        y_sub = y[idx]
        b0_sub, b1_sub = _deming_fit(x_sub, y_sub, delta)
        jack_b0[i] = b0_sub
        jack_b1[i] = b1_sub

    mean_jb0 = float(np.mean(jack_b0))
    mean_jb1 = float(np.mean(jack_b1))

    var_b0 = ((n - 1) / n) * float(np.sum((jack_b0 - mean_jb0) ** 2))
    var_b1 = ((n - 1) / n) * float(np.sum((jack_b1 - mean_jb1) ** 2))

    se_b0 = math.sqrt(max(0.0, var_b0))
    se_b1 = math.sqrt(max(0.0, var_b1))

    df_err = n - 2
    t_crit = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, df_err)) if df_err > 0 else 1.96

    # Test H0: beta_0 = 0
    t_b0 = b0 / se_b0 if se_b0 > 1e-12 else 0.0
    p_b0 = 2.0 * float(stats.t.sf(abs(t_b0), df_err)) if df_err > 0 else 0.0
    ci_b0 = (b0 - t_crit * se_b0, b0 + t_crit * se_b0)

    # Test H0: beta_1 = 0
    t_b1 = b1 / se_b1 if se_b1 > 1e-12 else 0.0
    p_b1 = 2.0 * float(stats.t.sf(abs(t_b1), df_err)) if df_err > 0 else 0.0
    ci_b1 = (b1 - t_crit * se_b1, b1 + t_crit * se_b1)

    # Test of Slope = 1: H0: beta_1 = 1 vs H1: beta_1 != 1
    t_slope_1 = (b1 - 1.0) / se_b1 if se_b1 > 1e-12 else 0.0
    p_slope_1 = 2.0 * float(stats.t.sf(abs(t_slope_1), df_err)) if df_err > 0 else 0.0

    # Latent true coordinates (x*, y*)
    # x* = x + (b1 / (b1^2 + delta)) * (y - b0 - b1 * x)
    # y* = b0 + b1 * x*
    denom = (b1 ** 2) + delta
    if denom > 1e-12:
        d_val = (y - b0 - b1 * x) / denom
        x_star = x + b1 * d_val
        y_star = b0 + b1 * x_star
    else:
        x_star = x.copy()
        y_star = y.copy()

    # Residuals
    res_x = x - x_star
    res_y = y - y_star

    # Error variance estimates
    # s^2_e = sum(delta * res_x^2 + res_y^2) / (n - 2)
    s2_total = float(np.sum(delta * (res_x ** 2) + (res_y ** 2))) / df_err if df_err > 0 else 0.0
    var_error_x = s2_total / (2.0 * delta) if delta > 0 else 0.0
    var_error_y = delta * var_error_x

    sign_str = "+ " if b1 >= 0 else "- "
    equation = f"{response_name} = {b0:.4f} {sign_str}{abs(b1):.4f} {predictor_name}"

    coefficients = [
        {
            "term": "Constant",
            "coef": b0,
            "se_coef": se_b0,
            "t_value": t_b0,
            "p_value": p_b0,
            "ci_lower": ci_b0[0],
            "ci_upper": ci_b0[1],
        },
        {
            "term": predictor_name,
            "coef": b1,
            "se_coef": se_b1,
            "t_value": t_b1,
            "p_value": p_b1,
            "ci_lower": ci_b1[0],
            "ci_upper": ci_b1[1],
        },
    ]

    return {
        "analysis": "orthogonal_regression",
        "response_name": response_name,
        "predictor_name": predictor_name,
        "error_variance_ratio": delta,
        "n_obs": n,
        "df": df_err,
        "confidence": confidence,
        "equation": equation,
        "coefficients": coefficients,
        "test_slope_1": {
            "t_value": t_slope_1,
            "p_value": p_slope_1,
        },
        "error_variance_x": var_error_x,
        "error_variance_y": var_error_y,
        "fits_x": x_star.tolist(),
        "fits_y": y_star.tolist(),
        "residuals_x": res_x.tolist(),
        "residuals_y": res_y.tolist(),
        "title": f"Orthogonal Regression: {response_name} versus {predictor_name}",
    }
