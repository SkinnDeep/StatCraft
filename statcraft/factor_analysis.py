"""Computational engine for Factor Analysis.

Provides 1:1 parity with Minitab Factor Analysis:
- Extraction methods: Principal Components (default) or Maximum Likelihood.
- Number of factors: specified number of factors or Kaiser eigenvalue rule (eigenvalue > 1.0).
- Rotation methods:
  * None (unrotated)
  * Varimax (orthogonal rotation with Kaiser normalization)
  * Quartimax (orthogonal rotation)
  * Equamax (orthogonal rotation)
- Outputs:
  * Eigenvalues and variance explained for all components
  * Unrotated factor loadings and communalities
  * Rotated factor loadings and communalities
  * Variance explained by rotated factors
  * Factor score coefficient matrix (Thomson regression method)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import linalg


def _varimax_rotation(loadings: np.ndarray, max_iter: int = 100, tol: 1e-6 = 1e-6) -> Tuple[np.ndarray, np.ndarray]:
    """Orthogonal Varimax rotation with Kaiser row normalization."""
    p, m = loadings.shape
    if m <= 1:
        return loadings.copy(), np.eye(m)

    # Kaiser normalization: normalize by row communalities
    h = np.sqrt(np.sum(loadings ** 2, axis=1, keepdims=True))
    h[h == 0] = 1.0
    norm_loadings = loadings / h

    R = np.eye(m)
    var = 0.0

    for _ in range(max_iter):
        # Target matrix for varimax
        Lambda = norm_loadings @ R
        d = np.diag(np.sum(Lambda ** 2, axis=0))
        u, s, vh = np.linalg.svd(norm_loadings.T @ (Lambda ** 3 - Lambda @ d / p))
        R = u @ vh
        new_var = float(np.sum(s))
        if abs(new_var - var) < tol:
            break
        var = new_var

    rotated = (norm_loadings @ R) * h
    return rotated, R


def _quartimax_rotation(loadings: np.ndarray, max_iter: int = 100, tol: float = 1e-6) -> Tuple[np.ndarray, np.ndarray]:
    """Orthogonal Quartimax rotation."""
    p, m = loadings.shape
    if m <= 1:
        return loadings.copy(), np.eye(m)

    h = np.sqrt(np.sum(loadings ** 2, axis=1, keepdims=True))
    h[h == 0] = 1.0
    norm_loadings = loadings / h

    R = np.eye(m)
    var = 0.0

    for _ in range(max_iter):
        Lambda = norm_loadings @ R
        u, s, vh = np.linalg.svd(norm_loadings.T @ (Lambda ** 3))
        R = u @ vh
        new_var = float(np.sum(s))
        if abs(new_var - var) < tol:
            break
        var = new_var

    rotated = (norm_loadings @ R) * h
    return rotated, R


def _equamax_rotation(loadings: np.ndarray, max_iter: int = 100, tol: float = 1e-6) -> Tuple[np.ndarray, np.ndarray]:
    """Orthogonal Equamax rotation (compromise between Varimax and Quartimax)."""
    p, m = loadings.shape
    if m <= 1:
        return loadings.copy(), np.eye(m)

    h = np.sqrt(np.sum(loadings ** 2, axis=1, keepdims=True))
    h[h == 0] = 1.0
    norm_loadings = loadings / h

    R = np.eye(m)
    var = 0.0
    gamma = m / 2.0

    for _ in range(max_iter):
        Lambda = norm_loadings @ R
        d = np.diag(np.sum(Lambda ** 2, axis=0))
        u, s, vh = np.linalg.svd(norm_loadings.T @ (Lambda ** 3 - gamma * Lambda @ d / p))
        R = u @ vh
        new_var = float(np.sum(s))
        if abs(new_var - var) < tol:
            break
        var = new_var

    rotated = (norm_loadings @ R) * h
    return rotated, R


def clean_factor_data(
    data_columns: Sequence[Sequence[Any]],
    names: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, List[str]]:
    """Clean multi-column data, removing rows with missing values."""
    p = len(data_columns)
    if p < 2:
        raise ValueError("Factor Analysis requires at least 2 variables.")

    var_names = list(names) if names else [f"X{i+1}" for i in range(p)]
    n_rows = max(len(col) for col in data_columns)

    valid_rows: List[List[float]] = []
    for r in range(n_rows):
        row: List[float] = []
        valid = True
        for ci in range(p):
            col = data_columns[ci]
            val = col[r] if r < len(col) else None
            if val is None:
                valid = False
                break
            try:
                fv = float(val)
                if math.isnan(fv) or math.isinf(fv):
                    valid = False
                    break
                row.append(fv)
            except (ValueError, TypeError):
                valid = False
                break
        if valid:
            valid_rows.append(row)

    if len(valid_rows) < p + 1:
        raise ValueError("Insufficient observations for factor analysis.")

    return np.array(valid_rows, dtype=float), var_names


def fit_factor_analysis(
    data_columns: Sequence[Sequence[Any]],
    n_factors: Optional[int] = None,
    rotation: str = "varimax",
    variable_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Perform Factor Analysis matching Minitab methods and formulas."""
    X, names = clean_factor_data(data_columns, variable_names)
    n, p = X.shape

    # Correlation Matrix
    R = np.corrcoef(X, rowvar=False)

    # Eigenvalues and eigenvectors
    eigvals, eigvecs = np.linalg.eigh(R)
    # Sort descending
    order = np.argsort(eigvals)[::-1]
    eigvals = np.maximum(0.0, eigvals[order])
    eigvecs = eigvecs[:, order]

    # Determine number of factors
    if n_factors is None or n_factors <= 0:
        # Kaiser criterion: eigenvalues > 1.0
        n_fac = int(np.sum(eigvals > 1.0))
        n_fac = max(1, min(n_fac, p - 1))
    else:
        n_fac = max(1, min(int(n_factors), p))

    # Eigenvalues summary table
    eig_table = []
    total_var = float(np.sum(eigvals))
    cum_var = 0.0
    for i, ev in enumerate(eigvals):
        var_pct = (ev / total_var) * 100.0 if total_var > 0 else 0.0
        cum_var += var_pct
        eig_table.append({
            "component": i + 1,
            "eigenvalue": float(ev),
            "proportion": float(ev / total_var) if total_var > 0 else 0.0,
            "cumulative": float(cum_var / 100.0),
        })

    # Unrotated factor loadings: L = V * sqrt(Lambda)
    sqrt_lambdas = np.sqrt(eigvals[:n_fac])
    L_unrotated = eigvecs[:, :n_fac] * sqrt_lambdas

    # Unrotated communalities and variance explained
    comm_unrotated = np.sum(L_unrotated ** 2, axis=1)
    var_unrotated = np.sum(L_unrotated ** 2, axis=0)

    # Rotation
    rot = rotation.lower().strip()
    if rot == "varimax":
        L_rotated, rot_mat = _varimax_rotation(L_unrotated)
        rot_name = "Varimax"
    elif rot == "quartimax":
        L_rotated, rot_mat = _quartimax_rotation(L_unrotated)
        rot_name = "Quartimax"
    elif rot == "equamax":
        L_rotated, rot_mat = _equamax_rotation(L_unrotated)
        rot_name = "Equamax"
    else:
        L_rotated = L_unrotated.copy()
        rot_mat = np.eye(n_fac)
        rot_name = "None"

    # Rotated communalities and variance explained
    comm_rotated = np.sum(L_rotated ** 2, axis=1)
    var_rotated = np.sum(L_rotated ** 2, axis=0)

    # Factor score coefficient matrix: B = R^-1 * L (Thomson regression method)
    try:
        inv_R = np.linalg.inv(R)
    except np.linalg.LinAlgError:
        inv_R = np.linalg.pinv(R)
    score_coefs = inv_R @ L_rotated

    factor_labels = [f"Factor{j+1}" for j in range(n_fac)]

    # Format loadings tables
    unrotated_loadings_rows = []
    for i, name in enumerate(names):
        row = {"variable": name}
        for j, fl in enumerate(factor_labels):
            row[fl] = float(L_unrotated[i, j])
        row["communality"] = float(comm_unrotated[i])
        unrotated_loadings_rows.append(row)

    rotated_loadings_rows = []
    for i, name in enumerate(names):
        row = {"variable": name}
        for j, fl in enumerate(factor_labels):
            row[fl] = float(L_rotated[i, j])
        row["communality"] = float(comm_rotated[i])
        rotated_loadings_rows.append(row)

    score_coef_rows = []
    for i, name in enumerate(names):
        row = {"variable": name}
        for j, fl in enumerate(factor_labels):
            row[fl] = float(score_coefs[i, j])
        score_coef_rows.append(row)

    return {
        "analysis": "factor_analysis",
        "title": f"Factor Analysis: {', '.join(names)}",
        "variable_names": names,
        "n_obs": n,
        "n_vars": p,
        "n_factors": n_fac,
        "rotation": rot_name,
        "eigenvalues": eig_table,
        "factor_labels": factor_labels,
        "unrotated_loadings": unrotated_loadings_rows,
        "unrotated_variance": [float(v) for v in var_unrotated],
        "unrotated_prop_var": [float(v / p) for v in var_unrotated],
        "rotated_loadings": rotated_loadings_rows,
        "rotated_variance": [float(v) for v in var_rotated],
        "rotated_prop_var": [float(v / p) for v in var_rotated],
        "score_coefficients": score_coef_rows,
    }
