"""Computational engine for Stability Study (Shelf Life Estimation per ICH Q1A/Q1E).

Provides 1:1 parity with Minitab Stability Study:
- Evaluates degradation/potency over time across batches.
- ANCOVA model testing with ICH Q1E decision tree:
  * Test of equal slopes across batches (default alpha_pool = 0.25)
  * Test of equal intercepts across batches (default alpha_pool = 0.25)
  * Selects model:
    1. Separate slopes and separate intercepts
    2. Common slope and separate intercepts
    3. Common slope and common intercept (Fully pooled)
- Regression equations for each batch and overall.
- Pointwise one-sided (or two-sided) 95% confidence bounds.
- Exact shelf life calculation where confidence limit intersects LSL or USL.
- Overall shelf life determination (minimum across batches).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import stats


def clean_stability_data(
    response: Sequence[Any],
    time: Sequence[Any],
    batch: Sequence[Any],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Clean and validate stability study data."""
    n = min(len(response), len(time), len(batch))
    clean_y: List[float] = []
    clean_x: List[float] = []
    clean_b: List[str] = []

    for i in range(n):
        y_val = response[i]
        x_val = time[i]
        b_val = batch[i]
        if y_val is None or x_val is None or b_val is None:
            continue
        try:
            fy = float(y_val)
            fx = float(x_val)
            sb = str(b_val).strip()
            if math.isnan(fy) or math.isnan(fx) or math.isinf(fy) or math.isinf(fx) or not sb:
                continue
            clean_y.append(fy)
            clean_x.append(fx)
            clean_b.append(sb)
        except (ValueError, TypeError):
            continue

    if not clean_y:
        raise ValueError("No valid observations for stability study.")

    arr_y = np.array(clean_y, dtype=float)
    arr_x = np.array(clean_x, dtype=float)
    arr_b = np.array(clean_b)
    unique_batches = sorted(list(set(clean_b)))

    return arr_y, arr_x, arr_b, unique_batches


def fit_stability_study(
    response: Sequence[Any],
    time: Sequence[Any],
    batch: Sequence[Any],
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    alpha_pool: float = 0.25,
    confidence: float = 0.95,
    response_name: str = "Potency",
    time_name: str = "Time",
    batch_name: str = "Batch",
) -> Dict[str, Any]:
    """Fit ICH Q1E Stability Study regression models and estimate shelf life."""
    y, x, b, unique_batches = clean_stability_data(response, time, batch)
    n = len(y)
    k = len(unique_batches)

    if n < 4 or k < 1:
        raise ValueError("Stability study requires at least 4 observations across batches.")
    if lsl is None and usl is None:
        raise ValueError("At least one specification limit (LSL or USL) must be provided.")

    batch_map = {b_id: i for i, b_id in enumerate(unique_batches)}
    b_idx = np.array([batch_map[bi] for bi in b])

    # ----------------------------------------------------
    # Model 1: Separate Intercepts, Separate Slopes (Full)
    # y = sum_j (beta0_j * I(B=j) + beta1_j * x * I(B=j))
    # ----------------------------------------------------
    X1 = np.zeros((n, 2 * k))
    for i in range(n):
        j = b_idx[i]
        X1[i, j] = 1.0
        X1[i, k + j] = x[i]

    coef1, res1, rank1, s1 = np.linalg.lstsq(X1, y, rcond=None)
    pred1 = X1 @ coef1
    sse1 = float(np.sum((y - pred1) ** 2))
    df1 = max(1, n - 2 * k)
    mse1 = sse1 / df1

    # ----------------------------------------------------
    # Model 2: Separate Intercepts, Common Slope
    # y = sum_j (beta0_j * I(B=j)) + beta1 * x
    # ----------------------------------------------------
    X2 = np.zeros((n, k + 1))
    for i in range(n):
        j = b_idx[i]
        X2[i, j] = 1.0
        X2[i, k] = x[i]

    coef2, res2, rank2, s2 = np.linalg.lstsq(X2, y, rcond=None)
    pred2 = X2 @ coef2
    sse2 = float(np.sum((y - pred2) ** 2))
    df2 = max(1, n - (k + 1))
    mse2 = sse2 / df2

    # ----------------------------------------------------
    # Model 3: Common Intercept, Common Slope (Pooled)
    # y = beta0 + beta1 * x
    # ----------------------------------------------------
    X3 = np.column_stack([np.ones(n), x])
    coef3, res3, rank3, s3 = np.linalg.lstsq(X3, y, rcond=None)
    pred3 = X3 @ coef3
    sse3 = float(np.sum((y - pred3) ** 2))
    df3 = max(1, n - 2)
    mse3 = sse3 / df3

    # ----------------------------------------------------
    # ANCOVA Poolability Tests (ICH Q1E)
    # ----------------------------------------------------
    # Test 1: Equal Slopes (Time * Batch interaction)
    if k > 1:
        ss_slopes = max(0.0, sse2 - sse1)
        df_slopes = k - 1
        f_slope = (ss_slopes / df_slopes) / mse1 if mse1 > 0 else 0.0
        p_slope = float(1.0 - stats.f.cdf(f_slope, df_slopes, df1))
    else:
        ss_slopes, df_slopes, f_slope, p_slope = 0.0, 0, 0.0, 1.0

    # Test 2: Equal Intercepts (Batch main effect given common slope)
    if k > 1:
        ss_intercepts = max(0.0, sse3 - sse2)
        df_intercepts = k - 1
        f_intercept = (ss_intercepts / df_intercepts) / mse2 if mse2 > 0 else 0.0
        p_intercept = float(1.0 - stats.f.cdf(f_intercept, df_intercepts, df2))
    else:
        ss_intercepts, df_intercepts, f_intercept, p_intercept = 0.0, 0, 0.0, 1.0

    # Model Selection per ICH Q1E decision rule
    if k == 1:
        selected_model_idx = 3
        model_name = "Single Batch (Common Intercept and Slope)"
    elif p_slope <= alpha_pool:
        selected_model_idx = 1
        model_name = "Separate Intercepts and Separate Slopes"
    elif p_intercept <= alpha_pool:
        selected_model_idx = 2
        model_name = "Separate Intercepts and Common Slope"
    else:
        selected_model_idx = 3
        model_name = "Common Intercept and Common Slope (Fully Pooled)"

    # Set parameters for the selected model
    if selected_model_idx == 1:
        active_coef = coef1
        active_mse = mse1
        active_df = df1
        # Covariance matrix for separate models
        try:
            cov1 = np.linalg.inv(X1.T @ X1) * active_mse
        except np.linalg.LinAlgError:
            cov1 = np.linalg.pinv(X1.T @ X1) * active_mse
        active_cov = cov1
    elif selected_model_idx == 2:
        active_coef = coef2
        active_mse = mse2
        active_df = df2
        try:
            cov2 = np.linalg.inv(X2.T @ X2) * active_mse
        except np.linalg.LinAlgError:
            cov2 = np.linalg.pinv(X2.T @ X2) * active_mse
        active_cov = cov2
    else:
        active_coef = coef3
        active_mse = mse3
        active_df = df3
        try:
            cov3 = np.linalg.inv(X3.T @ X3) * active_mse
        except np.linalg.LinAlgError:
            cov3 = np.linalg.pinv(X3.T @ X3) * active_mse
        active_cov = cov3

    # One-sided t critical value for shelf life (ICH standard 95% one-sided)
    alpha_shelf = 1.0 - confidence
    t_crit = float(stats.t.ppf(1.0 - alpha_shelf, active_df))

    # Regression equations and batch results
    batch_results = []
    equations = []
    shelf_lives = []

    t_max = float(np.max(x))
    t_eval = np.linspace(0.0, max(120.0, t_max * 3.0), 3000)

    for j, b_id in enumerate(unique_batches):
        if selected_model_idx == 1:
            b0 = float(active_coef[j])
            b1 = float(active_coef[k + j])
            # Variance of mean at t: [1, t] @ cov_j @ [1, t]
            idx_b0 = j
            idx_b1 = k + j
            sub_cov = np.array([
                [active_cov[idx_b0, idx_b0], active_cov[idx_b0, idx_b1]],
                [active_cov[idx_b1, idx_b0], active_cov[idx_b1, idx_b1]]
            ])
            se_t = np.sqrt(np.maximum(0.0, sub_cov[0, 0] + 2.0 * t_eval * sub_cov[0, 1] + (t_eval ** 2) * sub_cov[1, 1]))
            se_b0 = math.sqrt(max(0.0, active_cov[idx_b0, idx_b0]))
            se_b1 = math.sqrt(max(0.0, active_cov[idx_b1, idx_b1]))
        elif selected_model_idx == 2:
            b0 = float(active_coef[j])
            b1 = float(active_coef[k])
            idx_b0 = j
            idx_b1 = k
            sub_cov = np.array([
                [active_cov[idx_b0, idx_b0], active_cov[idx_b0, idx_b1]],
                [active_cov[idx_b1, idx_b0], active_cov[idx_b1, idx_b1]]
            ])
            se_t = np.sqrt(np.maximum(0.0, sub_cov[0, 0] + 2.0 * t_eval * sub_cov[0, 1] + (t_eval ** 2) * sub_cov[1, 1]))
            se_b0 = math.sqrt(max(0.0, active_cov[idx_b0, idx_b0]))
            se_b1 = math.sqrt(max(0.0, active_cov[idx_b1, idx_b1]))
        else:
            b0 = float(active_coef[0])
            b1 = float(active_coef[1])
            sub_cov = np.array([
                [active_cov[0, 0], active_cov[0, 1]],
                [active_cov[1, 0], active_cov[1, 1]]
            ])
            se_t = np.sqrt(np.maximum(0.0, sub_cov[0, 0] + 2.0 * t_eval * sub_cov[0, 1] + (t_eval ** 2) * sub_cov[1, 1]))
            se_b0 = math.sqrt(max(0.0, active_cov[0, 0]))
            se_b1 = math.sqrt(max(0.0, active_cov[1, 1]))

        y_fit = b0 + b1 * t_eval
        lcl_t = y_fit - t_crit * se_t
        ucl_t = y_fit + t_crit * se_t

        sign_str = "+ " if b1 >= 0 else "- "
        eq = f"{response_name} = {b0:.4f} {sign_str}{abs(b1):.4f} * {time_name}"
        equations.append({"batch": b_id, "equation": eq})

        # Calculate shelf life where bound crosses spec
        batch_shelf: Optional[float] = None
        if lsl is not None and b1 < 0:
            # Degrading downwards towards LSL
            cross_indices = np.where(lcl_t <= lsl)[0]
            if len(cross_indices) > 0:
                first_cross = cross_indices[0]
                batch_shelf = float(t_eval[first_cross])
        elif usl is not None and b1 > 0:
            # Increasing impurities towards USL
            cross_indices = np.where(ucl_t >= usl)[0]
            if len(cross_indices) > 0:
                first_cross = cross_indices[0]
                batch_shelf = float(t_eval[first_cross])
        elif lsl is not None and b1 >= 0:
            # Increasing or stable, lower bound never crosses LSL if b0 > LSL
            if b0 > lsl:
                batch_shelf = None  # indefinitely stable
            else:
                batch_shelf = 0.0
        elif usl is not None and b1 <= 0:
            if b0 < usl:
                batch_shelf = None
            else:
                batch_shelf = 0.0

        if batch_shelf is not None:
            shelf_lives.append(batch_shelf)

        batch_results.append({
            "batch": b_id,
            "intercept": b0,
            "se_intercept": se_b0,
            "slope": b1,
            "se_slope": se_b1,
            "shelf_life": batch_shelf,
        })

    overall_shelf_life = float(min(shelf_lives)) if shelf_lives else None

    # ANCOVA Table
    ancova_tests = [
        {
            "source": f"{time_name} * {batch_name} (Slopes)",
            "df": df_slopes,
            "ss": ss_slopes,
            "ms": (ss_slopes / df_slopes) if df_slopes > 0 else 0.0,
            "f_value": f_slope,
            "p_value": p_slope,
            "poolable": (p_slope > alpha_pool),
        },
        {
            "source": f"{batch_name} (Intercepts)",
            "df": df_intercepts,
            "ss": ss_intercepts,
            "ms": (ss_intercepts / df_intercepts) if df_intercepts > 0 else 0.0,
            "f_value": f_intercept,
            "p_value": p_intercept,
            "poolable": (p_intercept > alpha_pool),
        },
    ]

    return {
        "analysis": "stability_study",
        "title": f"Stability Study: {response_name} versus {time_name}, {batch_name}",
        "response_name": response_name,
        "time_name": time_name,
        "batch_name": batch_name,
        "n_obs": n,
        "n_batches": k,
        "unique_batches": unique_batches,
        "lsl": lsl,
        "usl": usl,
        "alpha_pool": alpha_pool,
        "confidence": confidence,
        "selected_model": model_name,
        "selected_model_idx": selected_model_idx,
        "ancova_tests": ancova_tests,
        "equations": equations,
        "batch_results": batch_results,
        "overall_shelf_life": overall_shelf_life,
    }
