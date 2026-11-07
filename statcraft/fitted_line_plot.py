"""Minitab-parity Fitted Line Plot Engine.

Performs Linear, Quadratic, and Cubic polynomial regression with confidence and prediction
bands, sequential ANOVA decomposition, coefficients, model summary, and unusual observations.
"""
from __future__ import annotations

import math
from typing import Any
import numpy as np
from scipy import stats

from .engine import normalize_numeric
from .inference import _confidence


def fit_fitted_line_plot(
    x_vals: list[Any],
    y_vals: list[Any],
    model_type: str = "linear",
    confidence: float = 0.95,
    x_name: str = "X",
    y_name: str = "Y",
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fit polynomial regression for Fitted Line Plot matching Minitab 22."""
    confidence = _confidence(confidence)
    model_type = str(model_type).lower().strip()
    if model_type not in ("linear", "quadratic", "cubic"):
        model_type = "linear"

    degree = 1 if model_type == "linear" else 2 if model_type == "quadratic" else 3

    # Filter aligned rows
    clean_x: list[float] = []
    clean_y: list[float] = []
    row_indices: list[int] = []

    for idx, (xv, yv) in enumerate(zip(x_vals, y_vals)):
        nx = normalize_numeric(xv)
        ny = normalize_numeric(yv)
        if nx is not None and ny is not None:
            clean_x.append(float(nx))
            clean_y.append(float(ny))
            row_indices.append(idx)

    n = len(clean_x)
    p = degree + 1  # Parameters including intercept

    if n < p + 2:
        raise ValueError(f"Fitted Line Plot requires at least {p + 2} complete observations for a {model_type} fit.")

    x_arr = np.asarray(clean_x, dtype=float)
    y_arr = np.asarray(clean_y, dtype=float)

    if np.all(x_arr == x_arr[0]):
        raise ValueError("Predictor X must have variation (cannot be constant).")
    if np.all(y_arr == y_arr[0]):
        raise ValueError("Response Y must have variation (cannot be constant).")

    # Build design matrix X for full degree
    X = np.column_stack([x_arr ** d for d in range(degree + 1)])

    # Solve OLS
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (X.T @ y_arr)

    # Fitted values and residuals
    y_hat = X @ beta
    residuals = y_arr - y_hat

    # Hat matrix diagonal (leverages)
    H_diag = np.sum(X * (X @ XtX_inv), axis=1)

    # Sum of squares
    mean_y = float(np.mean(y_arr))
    ss_total = float(np.sum((y_arr - mean_y) ** 2))
    ss_error = float(np.sum(residuals ** 2))
    ss_regression = max(0.0, ss_total - ss_error)

    df_total = n - 1
    df_error = n - p
    df_regression = degree

    ms_error = ss_error / max(1, df_error)
    ms_regression = ss_regression / max(1, df_regression)
    s = math.sqrt(ms_error)

    f_stat = ms_regression / ms_error if ms_error > 0 else float("inf")
    p_val = float(1.0 - stats.f.cdf(f_stat, df_regression, df_error)) if ms_error > 0 else 0.0

    # Model Summary metrics
    r2 = max(0.0, min(1.0, 1.0 - (ss_error / ss_total))) if ss_total > 0 else 1.0
    r2_adj = max(0.0, min(1.0, 1.0 - (ms_error / (ss_total / df_total)))) if ss_total > 0 else 1.0

    # PRESS and R2_pred
    press = 0.0
    for e_i, h_i in zip(residuals, H_diag):
        denom = 1.0 - h_i
        if denom > 1e-6:
            press += (e_i / denom) ** 2
        else:
            press += e_i ** 2
    r2_pred = max(0.0, min(1.0, 1.0 - (press / ss_total))) if ss_total > 0 else 1.0

    # Standardized and Deleted Residuals
    std_residuals = []
    del_residuals = []
    for e_i, h_i in zip(residuals, H_diag):
        denom = math.sqrt(max(1e-12, 1.0 - h_i))
        # Standardized
        std_r = e_i / (s * denom) if s > 0 else 0.0
        std_residuals.append(float(std_r))

        # Deleted Studentized
        if df_error > 1 and s > 0:
            s_i_sq = max(1e-12, ((df_error * ms_error) - (e_i ** 2 / max(1e-12, 1.0 - h_i))) / (df_error - 1))
            del_r = e_i / (math.sqrt(s_i_sq) * denom)
        else:
            del_r = std_r
        del_residuals.append(float(del_r))

    # Sequential ANOVA Decomposition
    sequential_anova = []
    current_ss_prev = 0.0
    for d in range(1, degree + 1):
        Xd = np.column_stack([x_arr ** k for k in range(d + 1)])
        beta_d = np.linalg.pinv(Xd.T @ Xd) @ (Xd.T @ y_arr)
        ss_reg_d = float(np.sum((Xd @ beta_d - mean_y) ** 2))
        ss_term = max(0.0, ss_reg_d - current_ss_prev)
        current_ss_prev = ss_reg_d
        f_term = ss_term / ms_error if ms_error > 0 else float("inf")
        p_term = float(1.0 - stats.f.cdf(f_term, 1, df_error)) if ms_error > 0 else 0.0
        term_name = "Linear" if d == 1 else "Quadratic" if d == 2 else "Cubic"
        sequential_anova.append({
            "source": term_name,
            "df": 1,
            "ss": ss_term,
            "ms": ss_term,
            "f": f_term,
            "p": p_term,
        })

    # Coefficients table
    terms_info = []
    t_crit = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, df_error))
    for d in range(degree + 1):
        c_val = float(beta[d])
        se_val = float(s * math.sqrt(max(0.0, XtX_inv[d, d])))
        t_val = c_val / se_val if se_val > 0 else float("inf")
        p_coef = float(2.0 * (1.0 - stats.t.cdf(abs(t_val), df_error))) if se_val > 0 else 0.0
        tname = "Constant" if d == 0 else x_name if d == 1 else f"{x_name}²" if d == 2 else f"{x_name}³"
        terms_info.append({
            "term": tname,
            "coef": c_val,
            "se_coef": se_val,
            "t": t_val,
            "p": p_coef,
        })

    # Formatted Equation string
    eq_parts = [f"{beta[0]:.4f}"]
    for d in range(1, degree + 1):
        coef = beta[d]
        var_symbol = x_name if d == 1 else f"{x_name}²" if d == 2 else f"{x_name}³"
        sign = " + " if coef >= 0 else " - "
        eq_parts.append(f"{sign}{abs(coef):.4f} {var_symbol}")
    equation = f"{y_name} = " + "".join(eq_parts)

    # Unusual observations
    unusual = []
    leverage_threshold = 3.0 * p / n
    for i, (r_idx, yi, fit_i, res_i, sres_i, hi) in enumerate(
        zip(row_indices, clean_y, y_hat, residuals, std_residuals, H_diag)
    ):
        is_large_resid = abs(sres_i) >= 2.0
        is_high_leverage = hi > leverage_threshold
        if is_large_resid or is_high_leverage:
            flags = []
            if is_large_resid:
                flags.append("R")
            if is_high_leverage:
                flags.append("X")
            unusual.append({
                "obs": r_idx + 1,
                "y": float(yi),
                "fit": float(fit_i),
                "resid": float(res_i),
                "std_resid": float(sres_i),
                "leverage": float(hi),
                "flag": "".join(flags),
            })

    # Evaluation Curve & Bands across X range (120 points)
    min_x = float(np.min(x_arr))
    max_x = float(np.max(x_arr))
    x_range = max(1e-9, max_x - min_x)
    grid_x = np.linspace(min_x - 0.03 * x_range, max_x + 0.03 * x_range, 120)

    grid_X = np.column_stack([grid_x ** d for d in range(degree + 1)])
    grid_fit = grid_X @ beta

    ci_low = []
    ci_high = []
    pi_low = []
    pi_high = []

    for i in range(len(grid_x)):
        x0 = grid_X[i, :]
        se_fit_i = float(s * math.sqrt(max(0.0, x0 @ XtX_inv @ x0.T)))
        fit_i = float(grid_fit[i])
        ci_margin = t_crit * se_fit_i
        se_pred_i = math.sqrt(max(0.0, s ** 2 + se_fit_i ** 2))
        pi_margin = t_crit * se_pred_i

        ci_low.append(fit_i - ci_margin)
        ci_high.append(fit_i + ci_margin)
        pi_low.append(fit_i - pi_margin)
        pi_high.append(fit_i + pi_margin)

    return {
        "analysis": "fitted_line_plot",
        "model_type": model_type,
        "degree": degree,
        "x_name": x_name,
        "y_name": y_name,
        "n": n,
        "confidence": confidence,
        "s": s,
        "r_squared": r2,
        "r_squared_adj": r2_adj,
        "r_squared_pred": r2_pred,
        "equation": equation,
        "coefficients": terms_info,
        "anova": {
            "regression": {"df": df_regression, "ss": ss_regression, "ms": ms_regression, "f": f_stat, "p": p_val},
            "sequential": sequential_anova,
            "error": {"df": df_error, "ss": ss_error, "ms": ms_error},
            "total": {"df": df_total, "ss": ss_total},
        },
        "unusual_observations": unusual,
        "points": {"x": clean_x, "y": clean_y, "row_indices": row_indices},
        "curve": {
            "x": grid_x.tolist(),
            "fit": grid_fit.tolist(),
            "ci_low": ci_low,
            "ci_high": ci_high,
            "pi_low": pi_low,
            "pi_high": pi_high,
        },
        "fits": y_hat.tolist(),
        "residuals": residuals.tolist(),
        "std_residuals": std_residuals,
        "del_residuals": del_residuals,
        "leverages": H_diag.tolist(),
        "options": options or {},
    }
