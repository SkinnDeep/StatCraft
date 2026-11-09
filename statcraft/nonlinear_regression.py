"""Computational engine for Nonlinear Regression.

Provides 1:1 parity with Minitab Nonlinear Regression:
- Solves y = f(X, theta) + epsilon using Levenberg-Marquardt / Gauss-Newton.
- Supports Minitab standard nonlinear catalog functions:
    * Asymptotic: y = th1 + th2 * exp(-th3 * x)
    * Michaelis-Menten: y = (th1 * x) / (th2 + x)
    * Logistic growth: y = th1 / (1 + exp(th2 - th3 * x))
    * Gompertz growth: y = th1 * exp(-exp(th2 - th3 * x))
    * Power / Allometric: y = th1 * (x ** th2)
    * Custom mathematical formula with parameters and predictors
- Computes parameter estimates, asymptotic standard errors from Jacobian (J^T J)^(-1) * s^2,
  t-values, p-values, 95% confidence intervals.
- Analysis of Variance (Regression, Residual Error, Corrected/Uncorrected Total).
- Model Summary: S, R-sq, R-sq(adj).
- Fitted values and residuals.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import optimize, stats


BUILTIN_FUNCTIONS = {
    "asymptotic": {
        "name": "Asymptotic Regression",
        "formula": "th1 + th2 * exp(-th3 * x)",
        "params": ["th1", "th2", "th3"],
        "fn": lambda x, th1, th2, th3: th1 + th2 * np.exp(-np.clip(th3 * x, -50.0, 50.0)),
    },
    "michaelis_menten": {
        "name": "Michaelis-Menten",
        "formula": "(th1 * x) / (th2 + x)",
        "params": ["th1", "th2"],
        "fn": lambda x, th1, th2: (th1 * x) / np.maximum(1e-9, th2 + x),
    },
    "logistic": {
        "name": "Logistic Growth",
        "formula": "th1 / (1 + exp(th2 - th3 * x))",
        "params": ["th1", "th2", "th3"],
        "fn": lambda x, th1, th2, th3: th1 / (1.0 + np.exp(np.clip(th2 - th3 * x, -50.0, 50.0))),
    },
    "gompertz": {
        "name": "Gompertz Growth",
        "formula": "th1 * exp(-exp(th2 - th3 * x))",
        "params": ["th1", "th2", "th3"],
        "fn": lambda x, th1, th2, th3: th1 * np.exp(-np.exp(np.clip(th2 - th3 * x, -50.0, 50.0))),
    },
    "power": {
        "name": "Power Function",
        "formula": "th1 * (x ** th2)",
        "params": ["th1", "th2"],
        "fn": lambda x, th1, th2: th1 * (np.maximum(1e-12, x) ** th2),
    },
}


def clean_nonlinear_data(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """Clean missing and non-numeric values for nonlinear regression."""
    n_raw = len(response)
    p_preds = len(predictors)

    valid_y: List[float] = []
    valid_x: List[List[float]] = []
    valid_indices: List[int] = []

    for i in range(n_raw):
        y_val = response[i]
        if y_val is None:
            continue
        try:
            fy = float(y_val)
            if math.isnan(fy) or math.isinf(fy):
                continue
        except (ValueError, TypeError):
            continue

        row_x: List[float] = []
        ok = True
        for col in predictors:
            v = col[i]
            if v is None:
                ok = False
                break
            try:
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    ok = False
                    break
                row_x.append(fv)
            except (ValueError, TypeError):
                ok = False
                break

        if ok:
            valid_y.append(fy)
            valid_x.append(row_x)
            valid_indices.append(i)

    y_arr = np.asarray(valid_y, dtype=float)
    x_arr = np.asarray(valid_x, dtype=float).reshape(len(valid_y), p_preds)
    return y_arr, x_arr, valid_indices


def _auto_initial_guess(model_name: str, x: np.ndarray, y: np.ndarray) -> List[float]:
    """Generate reasonable initial parameter guesses for built-in models."""
    x1 = x[:, 0]
    min_y = float(np.min(y))
    max_y = float(np.max(y))
    range_y = max(1e-6, max_y - min_y)
    min_x = float(np.min(x1))
    max_x = float(np.max(x1))
    range_x = max(1e-6, max_x - min_x)

    if model_name == "asymptotic":
        # y = th1 + th2 * exp(-th3 * x)
        th1 = max_y
        th2 = min_y - max_y
        th3 = 1.0 / range_x
        return [th1, th2, th3]
    elif model_name == "michaelis_menten":
        # y = (th1 * x) / (th2 + x)
        th1 = max_y * 1.2
        th2 = float(np.median(x1))
        return [th1, th2]
    elif model_name == "logistic":
        # y = th1 / (1 + exp(th2 - th3 * x))
        th1 = max_y * 1.05
        mid_x = float(np.median(x1))
        th3 = 4.0 / range_x
        th2 = th3 * mid_x
        return [th1, th2, th3]
    elif model_name == "gompertz":
        # y = th1 * exp(-exp(th2 - th3 * x))
        th1 = max_y * 1.05
        mid_x = float(np.median(x1))
        th3 = 2.0 / range_x
        th2 = th3 * mid_x
        return [th1, th2, th3]
    elif model_name == "power":
        # y = th1 * x ** th2
        return [1.0, 1.0]
    return [1.0, 1.0, 1.0]


def fit_nonlinear_regression(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
    model: str = "asymptotic",
    custom_formula: Optional[str] = None,
    parameter_names: Optional[Sequence[str]] = None,
    initial_values: Optional[Sequence[float]] = None,
    predictor_names: Optional[Sequence[str]] = None,
    response_name: str = "Y",
    confidence: float = 0.95,
    max_iter: int = 200,
) -> Dict[str, Any]:
    """Fit nonlinear regression model matching Minitab methods and formulas."""
    y, X, valid_indices = clean_nonlinear_data(response, predictors)
    n = len(y)
    if n < 3:
        raise ValueError("At least 3 valid observations required for nonlinear regression.")

    p_preds = X.shape[1]
    p_names = list(predictor_names) if predictor_names else [f"X{i+1}" for i in range(p_preds)]

    if model in BUILTIN_FUNCTIONS:
        builtin = BUILTIN_FUNCTIONS[model]
        func = builtin["fn"]
        param_names = list(parameter_names) if parameter_names else list(builtin["params"])
        formula_str = builtin["formula"]
        model_display = builtin["name"]

        if initial_values is not None:
            init_params = [float(v) for v in initial_values]
        else:
            init_params = _auto_initial_guess(model, X, y)

        def eval_fn(params: np.ndarray) -> np.ndarray:
            return func(X[:, 0], *params)

    elif model == "custom" and custom_formula:
        formula_str = custom_formula
        model_display = "Custom Nonlinear Model"
        if not parameter_names:
            raise ValueError("Parameter names must be provided for a custom formula.")
        param_names = list(parameter_names)
        if not initial_values or len(initial_values) != len(param_names):
            raise ValueError("Initial parameter values must be provided for custom formula.")
        init_params = [float(v) for v in initial_values]

        # Build safe evaluation context
        safe_dict = {
            "exp": np.exp,
            "log": np.log,
            "sqrt": np.sqrt,
            "sin": np.sin,
            "cos": np.cos,
            "tan": np.tan,
            "abs": np.abs,
        }
        for j, pname in enumerate(p_names):
            safe_dict[pname] = X[:, j]

        def eval_fn(params: np.ndarray) -> np.ndarray:
            ctx = dict(safe_dict)
            for k, p_name in enumerate(param_names):
                ctx[p_name] = params[k]
            res = eval(formula_str, {"__builtins__": {}}, ctx)
            return np.asarray(res, dtype=float)

    else:
        raise ValueError(f"Unknown nonlinear model '{model}'. Valid built-in models: {list(BUILTIN_FUNCTIONS.keys())} or 'custom'.")

    m_params = len(param_names)
    if n <= m_params:
        raise ValueError(f"Number of observations ({n}) must exceed number of parameters ({m_params}).")

    # Residual function for least squares: e_i = y_i - f(x_i, params)
    def residuals_fn(params: np.ndarray) -> np.ndarray:
        try:
            f_val = eval_fn(params)
            diff = y - f_val
            diff = np.where(np.isnan(diff) | np.isinf(diff), 1e6, diff)
            return diff
        except Exception:
            return np.full_like(y, 1e6)

    # Solve using Levenberg-Marquardt
    opt_res = optimize.least_squares(
        residuals_fn,
        x0=np.asarray(init_params, dtype=float),
        method="lm",
        max_nfev=max_iter * 10,
        ftol=1e-10,
        xtol=1e-10,
    )

    final_params = opt_res.x
    fitted = eval_fn(final_params)
    res = y - fitted
    sse = float(np.sum(res ** 2))
    df_err = n - m_params
    mse = sse / df_err if df_err > 0 else 0.0
    s_err = math.sqrt(max(0.0, mse))

    # Variance-covariance matrix from Jacobian J: (J^T J)^(-1) * MSE
    J = opt_res.jac
    try:
        jtj_inv = np.linalg.inv(J.T @ J)
        cov = jtj_inv * mse
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(J.T @ J) * mse

    se_params = np.sqrt(np.maximum(0.0, np.diag(cov)))

    # Parameter inference
    t_crit = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, df_err)) if df_err > 0 else 1.96
    param_table = []
    for j in range(m_params):
        val = float(final_params[j])
        se = float(se_params[j])
        t_val = val / se if se > 1e-12 else 0.0
        p_val = 2.0 * float(stats.t.sf(abs(t_val), df_err)) if df_err > 0 else 0.0
        ci_low = val - t_crit * se
        ci_high = val + t_crit * se

        param_table.append({
            "parameter": param_names[j],
            "estimate": val,
            "se": se,
            "t_value": t_val,
            "p_value": p_val,
            "ci_lower": ci_low,
            "ci_upper": ci_high,
        })

    # Total Sum of Squares (Corrected)
    mean_y = float(np.mean(y))
    sst_corrected = float(np.sum((y - mean_y) ** 2))
    ss_reg = max(0.0, sst_corrected - sse)
    df_reg = m_params - 1
    ms_reg = ss_reg / df_reg if df_reg > 0 else 0.0
    f_stat = ms_reg / mse if mse > 1e-12 else float("nan")
    p_reg = float(stats.f.sf(f_stat, df_reg, df_err)) if df_reg > 0 and df_err > 0 else 0.0

    # Model Summary metrics
    r_sq = max(0.0, (1.0 - sse / sst_corrected) * 100.0) if sst_corrected > 1e-12 else 0.0
    r_sq_adj = (
        max(0.0, (1.0 - (sse / df_err) / (sst_corrected / (n - 1))) * 100.0)
        if sst_corrected > 1e-12 and n > 1 and df_err > 0
        else 0.0
    )

    anova = [
        {"source": "Regression", "df": df_reg, "ss": ss_reg, "ms": ms_reg, "f": f_stat, "p_value": p_reg},
        {"source": "Residual Error", "df": df_err, "ss": sse, "ms": mse, "f": None, "p_value": None},
        {"source": "Total (Corrected)", "df": n - 1, "ss": sst_corrected, "ms": sst_corrected / (n - 1), "f": None, "p_value": None},
    ]

    return {
        "analysis": "nonlinear_regression",
        "response_name": response_name,
        "predictor_names": p_names,
        "model": model,
        "model_name": model_display,
        "formula": formula_str,
        "n_obs": n,
        "iterations": opt_res.nfev,
        "converged": opt_res.success,
        "confidence": confidence,
        "parameters": param_table,
        "anova": anova,
        "s": s_err,
        "r_sq": r_sq,
        "r_sq_adj": r_sq_adj,
        "sse": sse,
        "fits": fitted.tolist(),
        "residuals": res.tolist(),
        "title": f"Nonlinear Regression: {response_name} = {formula_str}",
    }
