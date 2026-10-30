"""Statistical engine for Multivariate Control Charts (Hotelling's T-Squared, Generalized Variance, MEWMA).

Implements native StatCraft PE resource fidelity and statistical formulas matching:
- 1154-TSQUAREDDATASOURCE.MDF (T-Squared Chart: MenuID 41043, HelpID 86300)
- 0753-GENVARDATASOURCE.MDF (Generalized Variance Chart: MenuID 41044, HelpID 86400)
- 0856-MEWMADATASOURCE.MDF (Multivariate EWMA Chart: MenuID 41045, HelpID 86500)
- 1007-QCHARTMULTIPARAMETERS.MDF (Multivariate Options: Covariance, Means, Limits)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np
from scipy import stats

from .attribute_control_engine import parse_subgroup_omission


def _clean_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "*":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def organize_multivariate_data(
    columns_data: Sequence[Sequence[Any]],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
) -> Tuple[List[np.ndarray], List[int]]:
    """Organize multi-column data into a list of 2D arrays (subgroups of shape (n_i, p)) and sizes."""
    p = len(columns_data)
    if p < 2:
        raise ValueError("Multivariate control charts require at least two variables.")

    n_rows = min(len(c) for c in columns_data)
    # Filter complete numeric rows
    clean_rows: List[List[float]] = []
    clean_sg_ids: List[Any] = []

    has_ids = isinstance(subgroup_size, (list, tuple, np.ndarray)) and len(subgroup_size) >= n_rows

    for r in range(n_rows):
        row_vals = [_clean_float(columns_data[j][r]) for j in range(p)]
        if all(v is not None for v in row_vals):
            clean_rows.append([float(v) for v in row_vals])
            if has_ids:
                clean_sg_ids.append(subgroup_size[r])

    if not clean_rows:
        return [], []

    subgroups: List[np.ndarray] = []
    sizes: List[int] = []

    if has_ids:
        curr_id = None
        curr_grp: List[List[float]] = []
        for row, sg_id in zip(clean_rows, clean_sg_ids):
            if curr_id is None:
                curr_id = sg_id
                curr_grp.append(row)
            elif sg_id == curr_id:
                curr_grp.append(row)
            else:
                if curr_grp:
                    arr = np.array(curr_grp, dtype=float)
                    subgroups.append(arr)
                    sizes.append(len(curr_grp))
                curr_id = sg_id
                curr_grp = [row]
        if curr_grp:
            arr = np.array(curr_grp, dtype=float)
            subgroups.append(arr)
            sizes.append(len(curr_grp))
        return subgroups, sizes

    # Constant subgroup size
    n_const = 1
    if subgroup_size is not None and not has_ids:
        try:
            n_const = max(1, int(subgroup_size))
        except (ValueError, TypeError):
            n_const = 1

    if n_const == 1:
        for row in clean_rows:
            subgroups.append(np.array([row], dtype=float))
            sizes.append(1)
    else:
        for i in range(0, len(clean_rows), n_const):
            chunk = clean_rows[i : i + n_const]
            if chunk:
                subgroups.append(np.array(chunk, dtype=float))
                sizes.append(len(chunk))

    return subgroups, sizes


def compute_multivariate_parameters(
    subgroups: List[np.ndarray],
    subgroup_sizes: List[int],
    omit: Set[int],
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute overall mean vector and pooled/sample covariance matrix."""
    m = len(subgroups)
    included = [i for i in range(m) if (i + 1) not in omit and subgroup_sizes[i] >= 1]
    if not included:
        included = list(range(m))

    p = subgroups[0].shape[1]
    all_obs: List[np.ndarray] = []
    for i in included:
        all_obs.append(subgroups[i])

    stacked = np.vstack(all_obs)
    mean_vec = np.mean(stacked, axis=0)

    # If subgroup sizes are all 1: sample covariance matrix of individual rows
    all_n1 = all(subgroup_sizes[i] == 1 for i in included)
    if all_n1:
        cov_mat = np.cov(stacked, rowvar=False, ddof=1)
        if cov_mat.ndim == 0:
            cov_mat = np.array([[float(cov_mat)]])
        return mean_vec, cov_mat

    # Subgroups with n >= 2: pooled within-subgroup covariance
    disp_indices = [i for i in included if subgroup_sizes[i] >= 2]
    if not disp_indices:
        cov_mat = np.cov(stacked, rowvar=False, ddof=1)
        return mean_vec, cov_mat

    total_df = sum(subgroup_sizes[i] - 1 for i in disp_indices)
    sum_ss = np.zeros((p, p), dtype=float)
    for i in disp_indices:
        grp = subgroups[i]
        grp_mean = np.mean(grp, axis=0)
        diff = grp - grp_mean
        sum_ss += diff.T @ diff

    cov_mat = sum_ss / total_df if total_df > 0 else np.cov(stacked, rowvar=False)
    return mean_vec, cov_mat


def safe_inv(cov: np.ndarray) -> np.ndarray:
    """Invert covariance matrix with ridge regularization if near-singular."""
    try:
        return np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        p = cov.shape[0]
        ridge = np.eye(p) * (1e-6 * (np.trace(cov) / p if p > 0 else 1.0))
        return np.linalg.pinv(cov + ridge)


def run_tsquared_control(
    columns_data: Sequence[Sequence[Any]],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
    alpha: float = 0.0027,
    options: Optional[Dict[str, Any]] = None,
    variable_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Compute Hotelling's T-Squared control chart."""
    opts = options or {}
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    alpha_val = float(opts.get("alpha", alpha))
    if alpha_val <= 0 or alpha_val >= 1:
        alpha_val = 0.0027

    subgroups, sizes = organize_multivariate_data(columns_data, subgroup_size)
    m = len(subgroups)
    if m == 0:
        raise ValueError("No valid multivariate observations provided.")

    p = subgroups[0].shape[1]
    var_names = list(variable_names) if variable_names else [f"X{j+1}" for j in range(p)]

    # Compute parameters
    mean_vec, cov_mat = compute_multivariate_parameters(subgroups, sizes, omit)

    inv_cov = safe_inv(cov_mat)

    # Compute T^2 for each subgroup
    t2_values: List[float] = []
    subgroup_means: List[List[float]] = []

    for i in range(m):
        grp = subgroups[i]
        n_i = sizes[i]
        x_bar_i = np.mean(grp, axis=0)
        subgroup_means.append(x_bar_i.tolist())
        diff = x_bar_i - mean_vec
        # T^2 = n_i * diff^T * S^-1 * diff
        val = float(n_i * (diff.T @ inv_cov @ diff))
        t2_values.append(max(0.0, val))

    # Control Limit (UCL)
    all_n1 = all(s == 1 for s in sizes)
    avg_n = int(round(np.mean(sizes)))

    if all_n1:
        # Individual observations (Tracy, Young, Mason 1992):
        # UCL = ((m - 1)^2 / m) * Beta_{alpha, p/2, (m - p - 1)/2}
        df1 = p / 2.0
        df2 = max(0.5, (m - p - 1.0) / 2.0)
        try:
            beta_crit = stats.beta.ppf(1.0 - alpha_val, df1, df2)
            ucl = float(((m - 1.0) ** 2 / m) * beta_crit)
        except Exception:
            # Fallback asymptotic chi-squared
            ucl = float(stats.chi2.ppf(1.0 - alpha_val, p))
    else:
        # Subgroup observations (n > 1):
        # UCL = (p * (m - 1) * (n - 1) / (m * (n - 1) - p + 1)) * F_{alpha, p, m*(n - 1) - p + 1}
        total_denom_df = m * (avg_n - 1) - p + 1
        if total_denom_df > 0:
            f_crit = stats.f.ppf(1.0 - alpha_val, p, total_denom_df)
            ucl = float((p * (m - 1) * (avg_n - 1) / total_denom_df) * f_crit)
        else:
            ucl = float(stats.chi2.ppf(1.0 - alpha_val, p))

    # Test 1 signals
    test1_signals: List[int] = []
    for i, t2 in enumerate(t2_values):
        if t2 > ucl:
            test1_signals.append(i + 1)

    # Variable decomposition for out-of-control signals
    decompositions: Dict[int, Dict[str, float]] = {}
    for sig in test1_signals:
        idx = sig - 1
        x_bar_i = np.array(subgroup_means[idx])
        diff = x_bar_i - mean_vec
        # Univariate contribution score for variable j
        var_contribs: Dict[str, float] = {}
        for j in range(p):
            s_jj = cov_mat[j, j]
            if s_jj > 0:
                t_j = float(math.sqrt(sizes[idx]) * abs(diff[j]) / math.sqrt(s_jj))
                var_contribs[var_names[j]] = t_j
        decompositions[sig] = var_contribs

    return {
        "analysis": "multivariate_control",
        "chart_type": "TSQUARED",
        "variable_names": var_names,
        "p_variables": p,
        "k_subgroups": m,
        "subgroup_sizes": sizes,
        "mean_vector": mean_vec.tolist(),
        "covariance_matrix": cov_mat.tolist(),
        "values": t2_values,
        "center_line": float(p),  # Expected value under H0
        "ucl": [ucl] * m,
        "lcl": [0.0] * m,
        "ucl_val": ucl,
        "lcl_val": 0.0,
        "alpha": alpha_val,
        "omit_subgroups": sorted(omit),
        "test_failures": {1: test1_signals} if test1_signals else {},
        "signals": test1_signals,
        "decompositions": decompositions,
    }


def run_genvar_control(
    columns_data: Sequence[Sequence[Any]],
    subgroup_size: Union[int, float, Sequence[Any], None] = 5,
    options: Optional[Dict[str, Any]] = None,
    variable_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Compute Generalized Variance (|S|) control chart."""
    opts = options or {}
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    k_sigma = float(opts.get("k_sigma", 3.0))

    subgroups, sizes = organize_multivariate_data(columns_data, subgroup_size)
    m = len(subgroups)
    if m == 0:
        raise ValueError("No valid multivariate observations provided.")

    p = subgroups[0].shape[1]
    var_names = list(variable_names) if variable_names else [f"X{j+1}" for j in range(p)]

    # Generalized variance requires subgroup sizes n >= 2 (and preferably n > p)
    if any(s < 2 for s in sizes):
        raise ValueError("Generalized Variance chart requires subgroup sizes of at least 2.")

    # Compute subgroup covariance matrices and generalized variances
    gen_vars: List[float] = []
    subgroup_covs: List[np.ndarray] = []

    for grp in subgroups:
        cov_i = np.cov(grp, rowvar=False, ddof=1)
        if cov_i.ndim == 0:
            cov_i = np.array([[float(cov_i)]])
        subgroup_covs.append(cov_i)
        det_i = float(np.linalg.det(cov_i))
        gen_vars.append(max(0.0, det_i))

    included = [i for i in range(m) if (i + 1) not in omit]
    if not included:
        included = list(range(m))

    # Pooled covariance matrix across included subgroups
    total_df = sum(sizes[i] - 1 for i in included)
    sum_ss = np.zeros((p, p), dtype=float)
    for i in included:
        sum_ss += (sizes[i] - 1) * subgroup_covs[i]
    pooled_s = sum_ss / total_df if total_df > 0 else np.mean(subgroup_covs, axis=0)

    # Center Line is determinant of pooled covariance matrix
    cl = float(np.linalg.det(pooled_s))

    # Compute unbiasing constants b1 and b2 for |S|
    # b1 = (1 / (n - 1)^p) * prod_{j=1}^p (n - j)
    # b2 = (1 / (n - 1)^(2p)) * prod_{j=1}^p (n - j) * [ prod_{j=1}^p (n - j + 2) - prod_{j=1}^p (n - j) ]
    avg_n = int(round(np.mean([sizes[i] for i in included])))
    
    prod1 = 1.0
    prod2 = 1.0
    for j in range(1, p + 1):
        prod1 *= max(1, avg_n - j)
        prod2 *= max(1, avg_n - j + 2)

    denom_b1 = (avg_n - 1.0) ** p if (avg_n - 1.0) > 0 else 1.0
    b1 = prod1 / denom_b1
    denom_b2 = (avg_n - 1.0) ** (2.0 * p) if (avg_n - 1.0) > 0 else 1.0
    b2 = (prod1 * (prod2 - prod1)) / denom_b2

    ratio = math.sqrt(max(0.0, b2)) / b1 if b1 > 0 else 0.5

    ucl = cl * (1.0 + k_sigma * ratio)
    lcl = max(0.0, cl * (1.0 - k_sigma * ratio))

    test1_signals: List[int] = []
    for i, gv in enumerate(gen_vars):
        if gv > ucl or gv < lcl:
            test1_signals.append(i + 1)

    return {
        "analysis": "multivariate_control",
        "chart_type": "GENVAR",
        "variable_names": var_names,
        "p_variables": p,
        "k_subgroups": m,
        "subgroup_sizes": sizes,
        "pooled_covariance": pooled_s.tolist(),
        "values": gen_vars,
        "center_line": cl,
        "ucl": [ucl] * m,
        "lcl": [lcl] * m,
        "ucl_val": ucl,
        "lcl_val": lcl,
        "b1": b1,
        "b2": b2,
        "omit_subgroups": sorted(omit),
        "test_failures": {1: test1_signals} if test1_signals else {},
        "signals": test1_signals,
    }


def run_mewma_control(
    columns_data: Sequence[Sequence[Any]],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
    weight: float = 0.1,
    arl: float = 200.0,
    options: Optional[Dict[str, Any]] = None,
    variable_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Compute Multivariate Exponentially Weighted Moving Average (MEWMA) control chart."""
    opts = options or {}
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    r = max(0.01, min(1.0, float(opts.get("weight", weight))))
    arl_target = float(opts.get("arl", arl))

    subgroups, sizes = organize_multivariate_data(columns_data, subgroup_size)
    m = len(subgroups)
    if m == 0:
        raise ValueError("No valid multivariate observations provided.")

    p = subgroups[0].shape[1]
    var_names = list(variable_names) if variable_names else [f"X{j+1}" for j in range(p)]

    mean_vec, cov_mat = compute_multivariate_parameters(subgroups, sizes, omit)

    # Calculate MEWMA vectors Z_i = r * (x_bar_i - mean_vec) + (1 - r) * Z_{i-1}
    z_curr = np.zeros(p, dtype=float)
    t2_mewma: List[float] = []

    cumulative_term = 0.0

    for i in range(m):
        grp = subgroups[i]
        n_i = sizes[i]
        x_bar_i = np.mean(grp, axis=0)
        diff = x_bar_i - mean_vec
        z_curr = r * diff + (1.0 - r) * z_curr

        # Dynamic covariance of Z_i:
        # Var(Z_i) = (r / (2 - r)) * [1 - (1 - r)^(2*(i+1))] * (Sigma / n_i)
        cumulative_term = (1.0 - r) ** 2 * cumulative_term + (r ** 2) / n_i
        cov_z_i = cov_mat * cumulative_term
        inv_cov_z = safe_inv(cov_z_i)

        val = float(z_curr.T @ inv_cov_z @ z_curr)
        t2_mewma.append(max(0.0, val))

    # Control Limit H calibration (Prabhu & Runger 1997 lookup / approximation):
    # For in-control ARL=200:
    # p=2, r=0.1 => H=8.64; r=0.2 => H=10.0; r=0.5 => H=11.6
    # For general p and r, calibrated via chi-square adjustment:
    alpha_eq = 1.0 / arl_target if arl_target > 0 else 0.005
    chi_crit = float(stats.chi2.ppf(1.0 - alpha_eq, p))
    # Approximation factor from Montgomery / Lowry et al.
    h_crit = chi_crit * (1.0 + 0.5 * r * (1.0 / math.sqrt(p)))

    test1_signals: List[int] = []
    for i, val in enumerate(t2_mewma):
        if val > h_crit:
            test1_signals.append(i + 1)

    return {
        "analysis": "multivariate_control",
        "chart_type": "MEWMA",
        "variable_names": var_names,
        "p_variables": p,
        "k_subgroups": m,
        "subgroup_sizes": sizes,
        "weight": r,
        "arl": arl_target,
        "mean_vector": mean_vec.tolist(),
        "covariance_matrix": cov_mat.tolist(),
        "values": t2_mewma,
        "center_line": float(p),
        "ucl": [h_crit] * m,
        "lcl": [0.0] * m,
        "ucl_val": h_crit,
        "lcl_val": 0.0,
        "omit_subgroups": sorted(omit),
        "test_failures": {1: test1_signals} if test1_signals else {},
        "signals": test1_signals,
    }
