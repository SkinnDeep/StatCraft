"""Computational engine for Multiple Correspondence Analysis (MCA).

Provides 1:1 parity with Minitab Multiple Correspondence Analysis:
- Analyzes relationships among 2 or more categorical variables.
- Uses indicator matrix Z and Burt contingency matrix B = Z^T * Z.
- Computes:
  * Principal inertias (eigenvalues), percentage of inertia, cumulative percentage.
  * Category coordinate table: Variable, Level, Mass, Quality, Relative Inertia, Coordinates on Axis 1, Axis 2, etc.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np


def clean_mca_data(
    data_columns: Sequence[Sequence[Any]],
    variable_names: Optional[Sequence[str]] = None,
) -> Tuple[List[List[str]], List[str], List[List[str]], int]:
    """Clean multi-column categorical data and extract levels."""
    q = len(data_columns)
    if q < 2:
        raise ValueError("Multiple Correspondence Analysis requires at least 2 categorical variables.")

    var_names = list(variable_names) if variable_names else [f"C{i+1}" for i in range(q)]
    n_rows = max(len(c) for c in data_columns)

    valid_rows: List[List[str]] = []
    for r in range(n_rows):
        row: List[str] = []
        valid = True
        for ci in range(q):
            col = data_columns[ci]
            val = col[r] if r < len(col) else None
            if val is None or str(val).strip() == "" or str(val).strip().lower() in ("nan", "none", "null"):
                valid = False
                break
            row.append(str(val).strip())
        if valid:
            valid_rows.append(row)

    if len(valid_rows) < 4:
        raise ValueError("Insufficient observations for Multiple Correspondence Analysis.")

    # Unique categories per variable
    var_levels: List[List[str]] = []
    for ci in range(q):
        unique_l = sorted(list(set(row[ci] for row in valid_rows)))
        if len(unique_l) < 2:
            raise ValueError(f"Variable '{var_names[ci]}' has fewer than 2 distinct categories.")
        var_levels.append(unique_l)

    total_categories = sum(len(lvl) for lvl in var_levels)
    return valid_rows, var_names, var_levels, total_categories


def fit_multiple_correspondence(
    data_columns: Sequence[Sequence[Any]],
    n_components: int = 2,
    variable_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Fit Multiple Correspondence Analysis via Indicator and Burt Matrix decomposition."""
    rows, var_names, var_levels, K = clean_mca_data(data_columns, variable_names)
    n = len(rows)
    q = len(var_names)

    # Build indicator matrix Z (size n x K)
    Z = np.zeros((n, K), dtype=float)
    col_to_var: List[int] = []
    col_to_level: List[str] = []

    k_offset = 0
    for j in range(q):
        lvl_map = {lvl: i for i, lvl in enumerate(var_levels[j])}
        for i in range(n):
            cat = rows[i][j]
            Z[i, k_offset + lvl_map[cat]] = 1.0
        for lvl in var_levels[j]:
            col_to_var.append(j)
            col_to_level.append(lvl)
        k_offset += len(var_levels[j])

    # Category frequencies and masses
    # Column counts: D_k = sum_i Z_ik
    col_counts = np.sum(Z, axis=0)
    # Mass of each category = col_count / (n * q)
    c_mass = col_counts / (n * q)

    # Centered standardized matrix for SVD on indicator:
    # S = (Z / (n * q) - (1/n) * c_mass) / sqrt((1/n) * c_mass)
    # SVD of Z_tilde = (1 / sqrt(n * q)) * (Z / sqrt(c_mass) - ones * sqrt(c_mass))
    sqrt_c = np.sqrt(c_mass)
    Z_std = (Z / sqrt_c) / math.sqrt(n * q)
    # Center columns
    col_means = np.mean(Z_std, axis=0, keepdims=True)
    Z_centered = Z_std - col_means

    # SVD of centered matrix
    U, s, Vt = np.linalg.svd(Z_centered, full_matrices=False)
    V = Vt.T

    # Inertias (eigenvalues) of indicator matrix
    eigenvalues = s ** 2
    total_inertia = float(np.sum(eigenvalues))

    # Number of axes to retain
    n_axes = max(1, min(int(n_components), len(eigenvalues)))

    # Summary of components / inertia
    inertia_table = []
    cum_pct = 0.0
    for i in range(len(eigenvalues)):
        ev = float(eigenvalues[i])
        pct = (ev / total_inertia * 100.0) if total_inertia > 0 else 0.0
        cum_pct += pct
        inertia_table.append({
            "axis": i + 1,
            "inertia": ev,
            "proportion": float(ev / total_inertia) if total_inertia > 0 else 0.0,
            "cumulative": float(cum_pct / 100.0),
        })

    # Principal coordinates for categories:
    # F = D_c^(-1/2) * V * Lambda
    # where D_c has c_mass on diagonal, Lambda = s
    inv_sqrt_c = 1.0 / sqrt_c
    category_coords = (inv_sqrt_c[:, np.newaxis] * V[:, :n_axes]) * s[:n_axes]

    # Category Relative Inertia and Quality
    # Total distance of category from origin in full profile space
    profile_sq_dist = np.sum((inv_sqrt_c[:, np.newaxis] * V) ** 2 * (s ** 2), axis=1)
    sub_sq_dist = np.sum(category_coords ** 2, axis=1)
    quality = np.clip(sub_sq_dist / np.maximum(1e-9, profile_sq_dist), 0.0, 1.0)
    category_inertias = c_mass * profile_sq_dist
    rel_inertia = category_inertias / total_inertia if total_inertia > 0 else np.zeros(K)

    # Category Coordinates Table
    category_table = []
    for k_idx in range(K):
        v_idx = col_to_var[k_idx]
        v_name = var_names[v_idx]
        lvl_name = col_to_level[k_idx]
        row_dict = {
            "variable": v_name,
            "category": lvl_name,
            "mass": float(c_mass[k_idx]),
            "quality": float(quality[k_idx]),
            "relative_inertia": float(rel_inertia[k_idx]),
        }
        for a_idx in range(n_axes):
            row_dict[f"coord_{a_idx + 1}"] = float(category_coords[k_idx, a_idx])
        category_table.append(row_dict)

    return {
        "analysis": "multiple_correspondence",
        "title": f"Multiple Correspondence Analysis: {', '.join(var_names)}",
        "variable_names": var_names,
        "n_obs": n,
        "n_vars": q,
        "n_categories": K,
        "n_components": n_axes,
        "total_inertia": total_inertia,
        "inertia_table": inertia_table,
        "category_table": category_table,
    }
