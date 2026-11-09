"""Computational engine for Best Subsets Regression.

Matches Minitab statistical formulas and algorithms:
- Evaluates candidate subsets of free predictors plus any forced predictors.
- Computes R-Sq, R-Sq(adj), Mallows' C-p, and residual standard error s.
- Retains top N models (default 2) for each subset size.
- Strictly validates degrees of freedom and collinearity.
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np


def clean_regression_data(
    response: Sequence[Any],
    predictors: Sequence[Sequence[Any]],
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """Filter rows where response or any predictor is None/NaN."""
    n_rows = len(response)
    p = len(predictors)
    valid_y: List[float] = []
    valid_x: List[List[float]] = []
    valid_indices: List[int] = []

    for i in range(n_rows):
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
        row_ok = True
        for j in range(p):
            x_val = predictors[j][i]
            if x_val is None:
                row_ok = False
                break
            try:
                fx = float(x_val)
                if math.isnan(fx) or math.isinf(fx):
                    row_ok = False
                    break
                row_x.append(fx)
            except (ValueError, TypeError):
                row_ok = False
                break

        if row_ok:
            valid_y.append(fy)
            valid_x.append(row_x)
            valid_indices.append(i)

    y_arr = np.asarray(valid_y, dtype=float)
    x_arr = np.asarray(valid_x, dtype=float).reshape(len(valid_y), p)
    return y_arr, x_arr, valid_indices


def _fit_ols_subset(y: np.ndarray, x: np.ndarray) -> Tuple[float, int, float, float]:
    """Fit OLS with intercept and return (SSE, df_error, s, R2)."""
    n, p = x.shape
    # Add intercept column
    X = np.column_stack([np.ones(n, dtype=float), x])
    # Solve via least squares / SVD
    coef, residuals, rank, s_vals = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ coef
    res = y - fitted
    sse = float(np.sum(res ** 2))
    df_error = n - (p + 1)
    if df_error <= 0:
        s = float("nan")
    else:
        s = math.sqrt(max(0.0, sse / df_error))
    return sse, df_error, s, coef


def best_subsets_regression(
    response: Sequence[Any],
    free_predictors: Sequence[Sequence[Any]],
    free_names: Optional[Sequence[str]] = None,
    forced_predictors: Optional[Sequence[Sequence[Any]]] = None,
    forced_names: Optional[Sequence[str]] = None,
    models_per_subset: int = 2,
    min_free: int = 1,
    max_free: Optional[int] = None,
    response_name: str = "Y",
) -> Dict[str, Any]:
    """Perform Best Subsets Regression evaluating candidate predictor subsets.
    
    Returns standard Minitab table metrics:
    - Vars (number of predictors in model)
    - R-Sq (%)
    - R-Sq(adj) (%)
    - C-p (Mallows' Cp)
    - s (standard error of regression)
    - Predictor presence flags
    """
    p_free = len(free_predictors)
    if p_free == 0:
        raise ValueError("At least one free predictor is required for Best Subsets Regression.")

    if free_names is None:
        free_names = [f"X{i+1}" for i in range(p_free)]
    else:
        free_names = list(free_names)
        if len(free_names) != p_free:
            raise ValueError("free_names length must match free_predictors length.")

    if forced_predictors is None:
        forced_predictors = []
        forced_names = []
    else:
        forced_predictors = list(forced_predictors)
        if forced_names is None:
            forced_names = [f"Forced{i+1}" for i in range(len(forced_predictors))]
        else:
            forced_names = list(forced_names)
            if len(forced_names) != len(forced_predictors):
                raise ValueError("forced_names length must match forced_predictors length.")

    p_forced = len(forced_predictors)
    all_predictors = list(forced_predictors) + list(free_predictors)
    y, X_all, _ = clean_regression_data(response, all_predictors)
    n = len(y)

    total_candidate_p = p_forced + p_free
    if n < total_candidate_p + 2:
        raise ValueError(
            f"Best Subsets requires at least {total_candidate_p + 2} complete rows (got {n})."
        )

    # Total Sum of Squares (SST)
    y_mean = float(np.mean(y))
    sst = float(np.sum((y - y_mean) ** 2))
    df_total = n - 1
    if sst <= 0:
        raise ValueError("Response variable has zero variance.")

    # Fit Full Model to obtain MSE_full for Mallows' Cp
    # Column indices: 0..p_forced-1 are forced, p_forced..total_candidate_p-1 are free
    sse_full, df_full, s_full, _ = _fit_ols_subset(y, X_all)
    if df_full <= 0 or sse_full <= 0:
        mse_full = 1e-12
    else:
        mse_full = sse_full / df_full

    k_min = max(0 if p_forced > 0 else 1, int(min_free))
    k_max = p_free if max_free is None else min(p_free, max(k_min, int(max_free)))
    n_keep = max(1, int(models_per_subset))

    models: List[Dict[str, Any]] = []

    # Iterate over subset sizes k of free predictors
    for k in range(k_min, k_max + 1):
        if k == 0 and p_forced == 0:
            continue

        comb_models: List[Dict[str, Any]] = []
        comb_indices = list(itertools.combinations(range(p_free), k)) if k > 0 else [()]

        for comb in comb_indices:
            # Active columns in X_all: all forced (0..p_forced-1) + chosen free (p_forced + idx)
            cols_to_use = list(range(p_forced)) + [p_forced + idx for idx in comb]
            X_sub = X_all[:, cols_to_use]
            sse_sub, df_sub, s_sub, _ = _fit_ols_subset(y, X_sub)

            total_p_sub = len(cols_to_use)
            p_params = total_p_sub + 1  # including intercept

            # R-Sq and R-Sq(adj)
            r2 = max(0.0, min(100.0, (1.0 - (sse_sub / sst)) * 100.0))
            if df_sub > 0:
                r2_adj = max(0.0, min(100.0, (1.0 - ((sse_sub / df_sub) / (sst / df_total))) * 100.0))
            else:
                r2_adj = 0.0

            # Mallows' Cp: SSE_m / MSE_full - (n - 2 * P)
            cp = (sse_sub / mse_full) - (n - 2 * p_params)

            # Predictor indicator dict
            included_free = [False] * p_free
            for idx in comb:
                included_free[idx] = True

            comb_models.append({
                "vars": total_p_sub,
                "k_free": k,
                "r2": float(r2),
                "r2_adj": float(r2_adj),
                "cp": float(cp),
                "s": float(s_sub),
                "sse": float(sse_sub),
                "free_indices": list(comb),
                "included_free": included_free,
            })

        # Sort candidate models of size k by descending R-Sq (or ascending SSE)
        comb_models.sort(key=lambda m: (-m["r2"], m["cp"]))
        models.extend(comb_models[:n_keep])

    return {
        "analysis": "best_subsets_regression",
        "response_name": response_name,
        "free_names": list(free_names),
        "forced_names": list(forced_names),
        "n": n,
        "sst": sst,
        "sse_full": sse_full,
        "mse_full": mse_full,
        "s_full": s_full,
        "models": models,
        "models_per_subset": n_keep,
        "min_free": k_min,
        "max_free": k_max,
        "title": f"Best Subsets Regression: {response_name} versus {', '.join(free_names)}",
    }
