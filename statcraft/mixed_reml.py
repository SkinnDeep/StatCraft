"""Mixed Effects Model (REML) Engine for StatCraft."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence
import numpy as np
from scipy import optimize, stats


def fit_mixed_reml(
    worksheet,
    response_index: int,
    fixed_indices: Sequence[int] = (),
    random_indices: Sequence[int] = (),
) -> Dict[str, Any]:
    """Fit Linear Mixed Effects Model via Restricted Maximum Likelihood (REML).

    Model: y = X*beta + sum_r(Z_r * u_r) + eps
    """
    if not random_indices:
        raise ValueError("Mixed Effects Model (REML) requires at least one Random factor.")
    if response_index in fixed_indices or response_index in random_indices:
        raise ValueError("Response variable cannot also be a fixed or random factor.")
    if set(fixed_indices) & set(random_indices):
        raise ValueError("Fixed and Random factor lists must be disjoint.")

    resp_col = worksheet.columns[response_index]
    fixed_cols = [worksheet.columns[i] for i in fixed_indices]
    rand_cols = [worksheet.columns[i] for i in random_indices]

    rows_y: List[float] = []
    rows_fixed: List[List[Any]] = []
    rows_rand: List[List[str]] = []

    for r in range(worksheet.row_count):
        yv = resp_col.values[r] if r < len(resp_col.values) else None
        fvs = [c.values[r] if r < len(c.values) else None for c in fixed_cols]
        rvs = [c.values[r] if r < len(c.values) else None for c in rand_cols]
        if yv is None or any(v is None for v in fvs) or any(v is None or (isinstance(v, str) and not v.strip()) for v in rvs):
            continue
        try:
            yf = float(yv)
        except (ValueError, TypeError):
            continue
        if not math.isfinite(yf):
            continue
        valid_f = True
        parsed_f = []
        for col, fv in zip(fixed_cols, fvs):
            if col.kind == "number":
                try:
                    num = float(fv)
                    if not math.isfinite(num):
                        valid_f = False; break
                    parsed_f.append(num)
                except (ValueError, TypeError):
                    valid_f = False; break
            else:
                s = str(fv).strip()
                if not s:
                    valid_f = False; break
                parsed_f.append(s)
        if not valid_f:
            continue
        rows_y.append(yf)
        rows_fixed.append(parsed_f)
        rows_rand.append([str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip() for v in rvs])

    n = len(rows_y)
    if n < 5:
        raise ValueError("Mixed Effects Model requires at least 5 complete observations.")

    y = np.asarray(rows_y, dtype=float)

    # Construct fixed-effect design matrix X
    X_cols = [np.ones(n, dtype=float)]
    fixed_names = ["Constant"]
    for idx_f, col in enumerate(fixed_cols):
        vals_f = [row[idx_f] for row in rows_fixed]
        if col.kind == "number":
            X_cols.append(np.asarray(vals_f, dtype=float))
            fixed_names.append(col.name)
        else:
            levels = sorted(set(vals_f))
            if len(levels) < 2:
                raise ValueError(f"Fixed factor '{col.name}' must have at least 2 distinct levels.")
            for lvl in levels[1:]:
                X_cols.append(np.array([1.0 if v == lvl else 0.0 for v in vals_f], dtype=float))
                fixed_names.append(f"{col.name} ({lvl})")

    X = np.column_stack(X_cols)
    p = X.shape[1]
    if n <= p + len(rand_cols):
        raise ValueError("Too few observations relative to model parameters.")

    # Construct random-effect Z matrices and K_r = Z_r @ Z_r.T
    Z_blocks = []
    K_mats = []
    rand_names = [c.name for c in rand_cols]
    rand_levels_map = []
    for idx_r, rname in enumerate(rand_names):
        labels = [row[idx_r] for row in rows_rand]
        levels = sorted(set(labels))
        if len(levels) < 2:
            raise ValueError(f"Random factor '{rname}' must have at least 2 distinct levels.")
        lvl_map = {lv: j for j, lv in enumerate(levels)}
        Z = np.zeros((n, len(levels)), dtype=float)
        for row_i, lbl in enumerate(labels):
            Z[row_i, lvl_map[lbl]] = 1.0
        Z_blocks.append(Z)
        K_mats.append(Z @ Z.T)
        rand_levels_map.append(levels)

    y_var = max(float(np.var(y, ddof=1)), 1e-6)
    n_rand = len(K_mats)

    def _reml_objective(log_vars: np.ndarray) -> float:
        variances = np.exp(np.clip(log_vars, -18.0, 20.0))
        sigma_e2 = variances[0]
        V = sigma_e2 * np.eye(n)
        for idx_k, K in enumerate(K_mats):
            V += variances[idx_k + 1] * K
        try:
            L = np.linalg.cholesky(V)
        except np.linalg.LinAlgError:
            return 1e18
        logdet_V = 2.0 * float(np.sum(np.log(np.diag(L))))
        V_inv_X = np.linalg.solve(L.T, np.linalg.solve(L, X))
        XtVinvX = X.T @ V_inv_X
        try:
            Lx = np.linalg.cholesky(XtVinvX)
        except np.linalg.LinAlgError:
            scale = max(1.0, float(np.trace(XtVinvX)) / max(1, p))
            XtVinvX_reg = XtVinvX + (1e-8 * scale) * np.eye(p)
            try:
                Lx = np.linalg.cholesky(XtVinvX_reg)
            except np.linalg.LinAlgError:
                return 1e18
        logdet_XtVinvX = 2.0 * float(np.sum(np.log(np.diag(Lx))))
        V_inv_y = np.linalg.solve(L.T, np.linalg.solve(L, y))
        beta = np.linalg.solve(Lx.T, np.linalg.solve(Lx, X.T @ V_inv_y))
        resid = y - X @ beta
        V_inv_r = np.linalg.solve(L.T, np.linalg.solve(L, resid))
        quad = float(resid @ V_inv_r)
        return logdet_V + logdet_XtVinvX + quad

    init_log_v = np.full(1 + n_rand, math.log(y_var / (1.0 + n_rand)))
    bounds = [(-18.0, 20.0)] * (1 + n_rand)
    opt = optimize.minimize(_reml_objective, init_log_v, method="L-BFGS-B", bounds=bounds)
    best_vars = np.exp(opt.x)
    sigma_e2 = float(best_vars[0])
    rand_vars = [float(v) for v in best_vars[1:]]

    # Compute final GLS estimates, covariance, BLUPs, and fit statistics
    V = sigma_e2 * np.eye(n)
    for rv, K in zip(rand_vars, K_mats):
        V += rv * K
    try:
        V_inv = np.linalg.inv(V)
    except np.linalg.LinAlgError:
        V_inv = np.linalg.pinv(V)
    XtVinvX = X.T @ V_inv @ X
    try:
        cov_beta = np.linalg.inv(XtVinvX)
    except np.linalg.LinAlgError:
        cov_beta = np.linalg.pinv(XtVinvX)
    beta_hat = cov_beta @ (X.T @ V_inv @ y)
    se_beta = np.sqrt(np.maximum(np.diag(cov_beta), 1e-18))

    resid = y - X @ beta_hat
    total_var = sigma_e2 + sum(rand_vars)
    df_resid = max(1, n - p)

    fixed_table = []
    for fname, b, se in zip(fixed_names, beta_hat, se_beta):
        t_val = float(b / se) if se > 0 else 0.0
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_val), df_resid)))
        fixed_table.append({
            "term": fname,
            "coef": float(b),
            "se_coef": float(se),
            "t_value": t_val,
            "p_value": p_val,
        })

    var_table = []
    for rname, rv in zip(rand_names, rand_vars):
        var_table.append({
            "source": rname,
            "var_comp": rv,
            "pct_total": 100.0 * rv / total_var if total_var > 0 else 0.0,
            "stdev": math.sqrt(rv),
        })
    var_table.append({
        "source": "Error",
        "var_comp": sigma_e2,
        "pct_total": 100.0 * sigma_e2 / total_var if total_var > 0 else 0.0,
        "stdev": math.sqrt(sigma_e2),
    })

    # BLUP predictions per random factor
    blups = {}
    V_inv_resid = V_inv @ resid
    for rname, rv, Z, levels in zip(rand_names, rand_vars, Z_blocks, rand_levels_map):
        u_hat = rv * (Z.T @ V_inv_resid)
        blups[rname] = [{"level": lvl, "blup": float(val)} for lvl, val in zip(levels, u_hat)]

    neg2_rell = float(opt.fun + (n - p) * math.log(2.0 * math.pi))
    k_reml = 1 + n_rand
    aic = neg2_rell + 2.0 * k_reml
    bic = neg2_rell + k_reml * math.log(max(1, n - p))

    return {
        "analysis": "mixed_reml",
        "response": resp_col.name,
        "fixed_factors": [c.name for c in fixed_cols],
        "random_factors": rand_names,
        "n": int(n),
        "variance_components": var_table,
        "total_variance": float(total_var),
        "fixed_effects": fixed_table,
        "blups": blups,
        "neg2_rell": neg2_rell,
        "aic": float(aic),
        "bic": float(bic),
    }


def format_mixed_reml_report(result: Dict[str, Any]) -> str:
    lines = [
        f"Mixed Effects Model (REML): {result['response']}",
        f"  N = {result['n']}   |   Random: {', '.join(result['random_factors'])}   |   Fixed: {', '.join(result['fixed_factors']) or 'None (Intercept)'}",
        f"  -2 RE Log-Likelihood = {result['neg2_rell']:.3f}   |   AIC = {result['aic']:.3f}   |   BIC = {result['bic']:.3f}",
        "",
        "  Variance Components:",
        "  Source               VarComp     % Total       StDev",
        "  " + "-" * 54,
    ]
    for vc in result["variance_components"]:
        lines.append(f"  {vc['source']:<18}  {vc['var_comp']:>10.5f}   {vc['pct_total']:>7.2f}%  {vc['stdev']:>10.5f}")
    lines.extend([
        "",
        "  Fixed Effects Coefficients:",
        "  Term                Coef      SE Coef    T-Value   P-Value",
        "  " + "-" * 60,
    ])
    for fe in result["fixed_effects"]:
        lines.append(f"  {fe['term']:<17} {fe['coef']:>9.4f}  {fe['se_coef']:>10.4f}  {fe['t_value']:>9.3f}  {fe['p_value']:>8.4f}")
    return "\n".join(lines)
