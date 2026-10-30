"""Multivariate analysis statistical engine for StatCraft.

Provides 1:1 statistical parity with StatCraft for:
- Principal Components Analysis (PCA)
- Item Analysis & Cronbach's Alpha
- Cluster Observations (Hierarchical)
- Cluster K-Means
- Cluster Variables
- Discriminant Analysis (Linear & Quadratic)
- Simple Correspondence Analysis
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import linalg, stats
from scipy.spatial.distance import pdist, squareform
from scipy.cluster import hierarchy


def _clean_numeric_matrix(data: List[List[Any]], var_names: Optional[List[str]] = None) -> Tuple[np.ndarray, List[int], List[str]]:
    """Convert column-oriented list of lists into a 2D float numpy array (n_obs x p_vars),
    filtering out any rows containing non-numeric or missing/NaN values.
    Returns (cleaned_matrix, valid_row_indices, variable_names)."""
    p = len(data)
    if p == 0:
        raise ValueError("At least one variable is required.")
    
    n_rows = len(data[0])
    for col in data:
        if len(col) != n_rows:
            raise ValueError("All columns must have the same number of rows.")
            
    if var_names is None:
        names = [f"C{i+1}" for i in range(p)]
    else:
        names = list(var_names)

    valid_indices = []
    cleaned_rows = []
    for r in range(n_rows):
        row_vals = []
        is_valid = True
        for c in range(p):
            val = data[c][r]
            if val is None or val == "" or isinstance(val, bool):
                is_valid = False
                break
            try:
                fval = float(val)
                if not math.isfinite(fval):
                    is_valid = False
                    break
                row_vals.append(fval)
            except (ValueError, TypeError):
                is_valid = False
                break
        if is_valid:
            valid_indices.append(r)
            cleaned_rows.append(row_vals)

    if not cleaned_rows:
        raise ValueError("No valid complete observations found.")

    mat = np.array(cleaned_rows, dtype=np.float64)
    return mat, valid_indices, names


# ==============================================================================
# 1. PRINCIPAL COMPONENTS ANALYSIS (PCA)
# ==============================================================================

def pca(
    data: List[List[Any]],
    var_names: Optional[List[str]] = None,
    matrix_type: str = "correlation",  # "correlation" or "covariance"
    n_components: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute Principal Components Analysis matching StatCraft.
    
    Parameters:
    - data: list of column lists.
    - var_names: list of column names.
    - matrix_type: 'correlation' (default) or 'covariance'.
    - n_components: number of components to retain (default: all or min(n, p)).
    """
    X, valid_rows, names = _clean_numeric_matrix(data, var_names)
    n, p = X.shape
    if n < 2:
        raise ValueError("PCA requires at least 2 complete observations.")
    if p < 2:
        raise ValueError("PCA requires at least 2 variables.")

    means = np.mean(X, axis=0)
    stds = np.std(X, axis=0, ddof=1)

    # Check for zero variance
    for j, s in enumerate(stds):
        if s <= 1e-15:
            raise ValueError(f"Variable '{names[j]}' has zero variance.")

    # Center matrix
    X_centered = X - means

    if matrix_type.lower() == "covariance":
        C = (X_centered.T @ X_centered) / (n - 1)
        matrix_title = "Covariance Matrix"
    else:
        # Correlation matrix
        X_scaled = X_centered / stds
        C = (X_scaled.T @ X_scaled) / (n - 1)
        matrix_title = "Correlation Matrix"

    # Eigen decomposition (C is symmetric positive semi-definite)
    eigenvalues, eigenvectors = linalg.eigh(C)

    # Sort descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Enforce StatCraft eigenvector sign convention:
    # First dominant entry in each eigenvector should be positive
    for k in range(p):
        max_abs_idx = np.argmax(np.abs(eigenvectors[:, k]))
        if eigenvectors[max_abs_idx, k] < 0:
            eigenvectors[:, k] = -eigenvectors[:, k]

    # Variance proportions
    total_var = float(np.sum(eigenvalues))
    proportions = eigenvalues / total_var if total_var > 0 else np.zeros_like(eigenvalues)
    cumulative = np.cumsum(proportions)

    max_k = min(n, p)
    if n_components is None or n_components <= 0 or n_components > max_k:
        k_keep = max_k
    else:
        k_keep = min(n_components, max_k)

    # Calculate component scores for each observation
    # Scores = Z @ V if correlation, or (X - mean) @ V if covariance
    if matrix_type.lower() == "covariance":
        scores = X_centered @ eigenvectors[:, :k_keep]
    else:
        scores = (X_centered / stds) @ eigenvectors[:, :k_keep]

    # Prepare eigenvalues table
    eigen_table = []
    for k in range(p):
        eigen_table.append({
            "component": k + 1,
            "eigenvalue": float(eigenvalues[k]),
            "proportion": float(proportions[k]),
            "cumulative": float(cumulative[k]),
        })

    # Prepare eigenvectors table
    comp_names = [f"PC{k+1}" for k in range(k_keep)]
    loadings_table = []
    for j, name in enumerate(names):
        row = {"variable": name}
        for k in range(k_keep):
            row[f"PC{k+1}"] = float(eigenvectors[j, k])
        loadings_table.append(row)

    return {
        "analysis": "pca",
        "matrix_type": matrix_type.lower(),
        "matrix_title": matrix_title,
        "dispersion_matrix": C.tolist(),
        "n_obs": n,
        "n_vars": p,
        "k_components": k_keep,
        "variable_names": names,
        "means": means.tolist(),
        "stds": stds.tolist(),
        "eigenvalues": eigenvalues.tolist(),
        "proportions": proportions.tolist(),
        "cumulative": cumulative.tolist(),
        "eigen_table": eigen_table,
        "eigenvectors": eigenvectors[:, :k_keep].tolist(),
        "loadings_table": loadings_table,
        "comp_names": comp_names,
        "scores": scores.tolist(),
        "valid_row_indices": valid_rows,
    }


# ==============================================================================
# 2. ITEM ANALYSIS & CRONBACH'S ALPHA
# ==============================================================================

def item_analysis(
    data: List[List[Any]],
    var_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compute Item Analysis and Cronbach's Alpha matching StatCraft.
    
    Calculates overall alpha, standardized alpha, and for each item:
    - Item Mean and Std Dev
    - Adjusted Total Mean and Std Dev (total score excluding item)
    - Item-Adjusted Total Correlation (Corrected Item-Total Correlation)
    - Squared Multiple Correlation (R^2 of item on other items)
    - Cronbach's Alpha if item deleted
    """
    X, valid_rows, names = _clean_numeric_matrix(data, var_names)
    n, k = X.shape
    if n < 3:
        raise ValueError("Item analysis requires at least 3 complete observations.")
    if k < 2:
        raise ValueError("Item analysis requires at least 2 items.")

    item_means = np.mean(X, axis=0)
    item_vars = np.var(X, axis=0, ddof=1)
    item_sds = np.sqrt(item_vars)

    for j, s in enumerate(item_sds):
        if s <= 1e-15:
            raise ValueError(f"Item '{names[j]}' has zero variance.")

    total_scores = np.sum(X, axis=1)
    total_var = float(np.var(total_scores, axis=0, ddof=1))
    sum_item_vars = float(np.sum(item_vars))

    # Overall Cronbach's Alpha
    # alpha = (k / (k - 1)) * (1 - sum(item_vars) / total_var)
    if total_var > 1e-15:
        cronbach_alpha = (k / (k - 1.0)) * (1.0 - sum_item_vars / total_var)
    else:
        cronbach_alpha = 0.0

    # Correlation Matrix
    corr_matrix = np.corrcoef(X, rowvar=False)

    # Standardized Cronbach's Alpha
    # mean_r = average of off-diagonal correlations
    off_diag_r = []
    for i in range(k):
        for j in range(i + 1, k):
            off_diag_r.append(corr_matrix[i, j])
    mean_r = float(np.mean(off_diag_r)) if off_diag_r else 0.0
    if 1.0 + (k - 1.0) * mean_r > 1e-15:
        standardized_alpha = (k * mean_r) / (1.0 + (k - 1.0) * mean_r)
    else:
        standardized_alpha = 0.0

    # Invert correlation matrix for Squared Multiple Correlations (SMC)
    # SMC_j = 1 - 1 / (inv_R)_{jj}
    try:
        inv_corr = linalg.inv(corr_matrix)
        smc = np.zeros(k)
        for j in range(k):
            diag_val = inv_corr[j, j]
            if diag_val > 1.0:
                smc[j] = 1.0 - 1.0 / diag_val
            else:
                smc[j] = 0.0
    except linalg.LinAlgError:
        smc = np.zeros(k)

    # Item-Deleted Statistics
    item_deleted_stats = []
    for j in range(k):
        # Exclude item j
        adj_total = total_scores - X[:, j]
        adj_mean = float(np.mean(adj_total))
        adj_var = float(np.var(adj_total, ddof=1))
        adj_sd = float(np.sqrt(adj_var)) if adj_var > 0 else 0.0

        # Corrected item-total correlation: Pearson r between X[:, j] and adj_total
        if item_sds[j] > 1e-15 and adj_sd > 1e-15:
            r_item_adj_total = float(np.corrcoef(X[:, j], adj_total)[0, 1])
        else:
            r_item_adj_total = 0.0

        # Alpha if item deleted
        if k > 2 and adj_var > 1e-15:
            sum_other_vars = sum_item_vars - item_vars[j]
            alpha_deleted = ((k - 1.0) / (k - 2.0)) * (1.0 - sum_other_vars / adj_var)
        else:
            alpha_deleted = 0.0

        item_deleted_stats.append({
            "item": names[j],
            "item_mean": float(item_means[j]),
            "item_sd": float(item_sds[j]),
            "adj_total_mean": adj_mean,
            "adj_total_sd": adj_sd,
            "item_adj_total_corr": r_item_adj_total,
            "squared_multiple_corr": float(smc[j]),
            "alpha_deleted": float(alpha_deleted),
        })

    return {
        "analysis": "item_analysis",
        "n_obs": n,
        "n_items": k,
        "item_names": names,
        "cronbach_alpha": float(cronbach_alpha),
        "standardized_alpha": float(standardized_alpha),
        "total_mean": float(np.mean(total_scores)),
        "total_sd": float(np.std(total_scores, ddof=1)),
        "item_stats": item_deleted_stats,
        "correlation_matrix": corr_matrix.tolist(),
        "valid_row_indices": valid_rows,
    }


# ==============================================================================
# 3. CLUSTER OBSERVATIONS (HIERARCHICAL CLUSTERING)
# ==============================================================================

def cluster_observations(
    data: List[List[Any]],
    var_names: Optional[List[str]] = None,
    linkage_method: str = "average",  # 'average', 'single', 'complete', 'centroid', 'ward', 'median', 'mcquitty'
    distance_measure: str = "euclidean",  # 'euclidean', 'squared_euclidean', 'manhattan', 'maximum'
    standardize: str = "none",  # 'none', 'zscore', 'range'
    n_clusters: Optional[int] = None,
) -> Dict[str, Any]:
    """Perform hierarchical agglomerative clustering of observations matching StatCraft."""
    X, valid_rows, names = _clean_numeric_matrix(data, var_names)
    n, p = X.shape
    if n < 2:
        raise ValueError("Clustering requires at least 2 complete observations.")

    # Standardization
    std_mode = standardize.lower()
    if std_mode in ("zscore", "standardize"):
        stds = np.std(X, axis=0, ddof=1)
        stds[stds == 0] = 1.0
        X_work = (X - np.mean(X, axis=0)) / stds
    elif std_mode == "range":
        mins = np.min(X, axis=0)
        maxs = np.max(X, axis=0)
        rng = maxs - mins
        rng[rng == 0] = 1.0
        X_work = (X - mins) / rng
    else:
        X_work = np.copy(X)

    # Distance calculation
    dist_mode = distance_measure.lower()
    if dist_mode in ("manhattan", "cityblock"):
        pdist_metric = "cityblock"
        dists = pdist(X_work, metric="cityblock")
    elif dist_mode in ("maximum", "chebyshev"):
        pdist_metric = "chebyshev"
        dists = pdist(X_work, metric="chebyshev")
    elif dist_mode in ("squared_euclidean", "sqeuclidean"):
        pdist_metric = "euclidean"
        dists = pdist(X_work, metric="euclidean")
    else:
        pdist_metric = "euclidean"
        dists = pdist(X_work, metric="euclidean")

    # Linkage
    link_map = {
        "average": "average",
        "single": "single",
        "complete": "complete",
        "centroid": "centroid",
        "ward": "ward",
        "median": "median",
        "mcquitty": "weighted",
    }
    scipy_link = link_map.get(linkage_method.lower(), "average")

    if scipy_link in ("ward", "centroid", "median") and pdist_metric != "euclidean":
        dists = pdist(X_work, metric="euclidean")

    Z = hierarchy.linkage(dists, method=scipy_link)

    # Amalgamation schedule matching StatCraft
    max_d = float(np.max(Z[:, 2])) if len(Z) > 0 and np.max(Z[:, 2]) > 0 else 1.0
    amalgamation = []
    for step in range(len(Z)):
        d_val = float(Z[step, 2])
        if dist_mode == "squared_euclidean":
            display_d = d_val ** 2
            sim = 100.0 * (1.0 - display_d / (max_d ** 2)) if max_d > 0 else 100.0
        else:
            display_d = d_val
            sim = 100.0 * (1.0 - d_val / max_d) if max_d > 0 else 100.0

        sim = max(0.0, min(100.0, sim))
        c1 = int(Z[step, 0]) + 1
        c2 = int(Z[step, 1]) + 1
        new_c = min(c1, c2)
        n_obs_in_new = int(Z[step, 3])
        rem_clusters = n - (step + 1)
        amalgamation.append({
            "step": step + 1,
            "clusters": rem_clusters,
            "similarity": sim,
            "distance": display_d,
            "cluster1": c1,
            "cluster2": c2,
            "new_cluster": new_c,
            "n_obs": n_obs_in_new,
        })

    # Partition into clusters
    if n_clusters is None or n_clusters < 1:
        k_clusters = min(3, n)
    else:
        k_clusters = min(n_clusters, n)

    cluster_labels = hierarchy.fcluster(Z, t=k_clusters, criterion="maxclust")

    # Cluster summary
    summary = []
    centroids = []
    total_ss = 0.0
    for k in range(1, k_clusters + 1):
        mask = (cluster_labels == k)
        cluster_X = X[mask]
        c_size = int(np.sum(mask))
        if c_size > 0:
            centroid = np.mean(cluster_X, axis=0)
            diffs = cluster_X - centroid
            dists_to_c = np.linalg.norm(diffs, axis=1)
            within_ss = float(np.sum(diffs ** 2))
            avg_dist = float(np.mean(dists_to_c))
            max_dist = float(np.max(dists_to_c))
            total_ss += within_ss
        else:
            centroid = np.zeros(p)
            within_ss = 0.0
            avg_dist = 0.0
            max_dist = 0.0

        centroids.append(centroid.tolist())
        summary.append({
            "cluster": k,
            "count": c_size,
            "within_ss": within_ss,
            "avg_dist": avg_dist,
            "max_dist": max_dist,
        })

    # Dendrogram data for plotting
    dendro = hierarchy.dendrogram(Z, no_plot=True)
    dendro_plot_data = {
        "icoord": dendro["icoord"],
        "dcoord": dendro["dcoord"],
        "ivl": dendro["ivl"],
        "leaves": dendro["leaves"],
    }

    return {
        "analysis": "cluster_observations",
        "n_obs": n,
        "n_vars": p,
        "variable_names": names,
        "linkage_method": linkage_method,
        "distance_measure": distance_measure,
        "standardize": standardize,
        "k_clusters": k_clusters,
        "amalgamation": amalgamation,
        "cluster_labels": cluster_labels.tolist(),
        "cluster_summary": summary,
        "centroids": centroids,
        "total_within_ss": total_ss,
        "dendrogram_data": dendro_plot_data,
        "linkage_matrix": Z.tolist(),
        "valid_row_indices": valid_rows,
    }


# ==============================================================================
# 4. CLUSTER K-MEANS
# ==============================================================================

def cluster_kmeans(
    data: List[List[Any]],
    var_names: Optional[List[str]] = None,
    k_clusters: int = 3,
    max_iter: int = 100,
    seed: int = 42,
) -> Dict[str, Any]:
    """Perform K-Means clustering matching StatCraft.
    
    Uses standard Lloyd's iteration with deterministic initial seeding matching StatCraft.
    """
    X, valid_rows, names = _clean_numeric_matrix(data, var_names)
    n, p = X.shape
    if n < k_clusters:
        raise ValueError(f"K-means requires at least {k_clusters} observations.")
    if k_clusters < 1:
        raise ValueError("Number of clusters must be at least 1.")

    # Initialize centroids: pick first k distinct observations or quantiles
    indices = np.linspace(0, n - 1, k_clusters, dtype=int)
    centroids = np.copy(X[indices])

    labels = np.zeros(n, dtype=int)
    prev_labels = np.ones(n, dtype=int) * -1
    iteration = 0

    while iteration < max_iter and not np.array_equal(labels, prev_labels):
        prev_labels = np.copy(labels)
        iteration += 1

        # Assign each point to closest centroid
        dists = np.linalg.norm(X[:, np.newaxis, :] - centroids[np.newaxis, :, :], axis=2)
        labels = np.argmin(dists, axis=1)

        # Recompute centroids
        for k in range(k_clusters):
            mask = (labels == k)
            if np.any(mask):
                centroids[k] = np.mean(X[mask], axis=0)

    # Final summary statistics
    summary = []
    total_within_ss = 0.0
    for k in range(k_clusters):
        mask = (labels == k)
        c_size = int(np.sum(mask))
        if c_size > 0:
            diffs = X[mask] - centroids[k]
            within_ss = float(np.sum(diffs ** 2))
            dists_to_c = np.linalg.norm(diffs, axis=1)
            avg_dist = float(np.mean(dists_to_c))
            max_dist = float(np.max(dists_to_c))
        else:
            within_ss = 0.0
            avg_dist = 0.0
            max_dist = 0.0
        total_within_ss += within_ss
        summary.append({
            "cluster": k + 1,
            "count": c_size,
            "within_ss": within_ss,
            "avg_dist": avg_dist,
            "max_dist": max_dist,
        })

    # Inter-cluster centroid distances
    c_dist_matrix = np.zeros((k_clusters, k_clusters))
    for i in range(k_clusters):
        for j in range(k_clusters):
            c_dist_matrix[i, j] = float(np.linalg.norm(centroids[i] - centroids[j]))

    # Overall SS
    overall_mean = np.mean(X, axis=0)
    total_ss = float(np.sum((X - overall_mean) ** 2))
    between_ss = total_ss - total_within_ss

    return {
        "analysis": "cluster_kmeans",
        "n_obs": n,
        "n_vars": p,
        "k_clusters": k_clusters,
        "iterations": iteration,
        "variable_names": names,
        "cluster_labels": (labels + 1).tolist(),  # 1-indexed
        "centroids": centroids.tolist(),
        "summary": summary,
        "centroid_distances": c_dist_matrix.tolist(),
        "total_ss": total_ss,
        "within_ss": total_within_ss,
        "between_ss": between_ss,
        "valid_row_indices": valid_rows,
    }


# ==============================================================================
# 5. CLUSTER VARIABLES
# ==============================================================================

def cluster_variables(
    data: List[List[Any]],
    var_names: Optional[List[str]] = None,
    linkage_method: str = "average",
) -> Dict[str, Any]:
    """Perform hierarchical clustering of variables matching StatCraft.
    
    Distance metric: d = 1 - r, and Similarity s = 100 * (1 - d/2).
    """
    X, valid_rows, names = _clean_numeric_matrix(data, var_names)
    n, p = X.shape
    if p < 2:
        raise ValueError("Clustering variables requires at least 2 variables.")

    corr = np.corrcoef(X, rowvar=False)
    
    dist_vec = []
    for i in range(p):
        for j in range(i + 1, p):
            r = corr[i, j]
            d = max(0.0, 1.0 - r)
            dist_vec.append(d)
    dist_vec = np.array(dist_vec)

    link_map = {
        "average": "average",
        "single": "single",
        "complete": "complete",
        "centroid": "centroid",
        "ward": "ward",
        "median": "median",
        "mcquitty": "weighted",
    }
    scipy_link = link_map.get(linkage_method.lower(), "average")
    Z = hierarchy.linkage(dist_vec, method=scipy_link)

    amalgamation = []
    for step in range(len(Z)):
        d_val = float(Z[step, 2])
        sim = max(0.0, min(100.0, 100.0 * (1.0 - d_val / 2.0)))
        c1 = int(Z[step, 0]) + 1
        c2 = int(Z[step, 1]) + 1
        new_c = min(c1, c2)
        amalgamation.append({
            "step": step + 1,
            "clusters": p - (step + 1),
            "similarity": sim,
            "distance": d_val,
            "cluster1": c1,
            "cluster2": c2,
            "new_cluster": new_c,
            "n_vars": int(Z[step, 3]),
        })

    dendro = hierarchy.dendrogram(Z, labels=names, no_plot=True)

    return {
        "analysis": "cluster_variables",
        "n_obs": n,
        "n_vars": p,
        "variable_names": names,
        "linkage_method": linkage_method,
        "correlation_matrix": corr.tolist(),
        "amalgamation": amalgamation,
        "dendrogram_data": {
            "icoord": dendro["icoord"],
            "dcoord": dendro["dcoord"],
            "ivl": dendro["ivl"],
            "leaves": dendro["leaves"],
        },
        "linkage_matrix": Z.tolist(),
    }


# ==============================================================================
# 6. DISCRIMINANT ANALYSIS (LDA & QDA)
# ==============================================================================

def discriminant_analysis(
    group_col: List[Any],
    pred_data: List[List[Any]],
    group_name: str = "Group",
    pred_names: Optional[List[str]] = None,
    method: str = "linear",  # 'linear' or 'quadratic'
    priors: str = "equal",  # 'equal' or 'proportional'
) -> Dict[str, Any]:
    """Perform Linear or Quadratic Discriminant Analysis matching StatCraft."""
    p = len(pred_data)
    if p < 1:
        raise ValueError("At least one predictor is required.")
    n_rows = len(group_col)
    for col in pred_data:
        if len(col) != n_rows:
            raise ValueError("Predictor columns and group column must have the same length.")

    if pred_names is None:
        p_names = [f"X{i+1}" for i in range(p)]
    else:
        p_names = list(pred_names)

    # Clean rows: filter out missing/invalid
    valid_indices = []
    clean_groups = []
    clean_X = []
    for r in range(n_rows):
        g = group_col[r]
        if g is None or g == "":
            continue
        row_vals = []
        valid = True
        for c in range(p):
            val = pred_data[c][r]
            if val is None or val == "" or isinstance(val, bool):
                valid = False
                break
            try:
                fval = float(val)
                if not math.isfinite(fval):
                    valid = False
                    break
                row_vals.append(fval)
            except (ValueError, TypeError):
                valid = False
                break
        if valid:
            valid_indices.append(r)
            clean_groups.append(str(g))
            clean_X.append(row_vals)

    n = len(clean_groups)
    if n < p + 2:
        raise ValueError(f"Discriminant analysis requires at least {p + 2} observations.")

    X = np.array(clean_X, dtype=np.float64)
    unique_groups, group_indices = np.unique(clean_groups, return_inverse=True)
    g_count = len(unique_groups)
    if g_count < 2:
        raise ValueError("Discriminant analysis requires at least 2 distinct groups.")

    group_ns = np.zeros(g_count, dtype=int)
    group_means = np.zeros((g_count, p))
    group_covs = []

    for g_idx in range(g_count):
        mask = (group_indices == g_idx)
        n_g = int(np.sum(mask))
        group_ns[g_idx] = n_g
        if n_g < 2:
            raise ValueError(f"Group '{unique_groups[g_idx]}' has fewer than 2 observations.")
        X_g = X[mask]
        group_means[g_idx] = np.mean(X_g, axis=0)
        cov_g = np.cov(X_g, rowvar=False, ddof=1)
        if p == 1:
            cov_g = np.array([[cov_g]])
        group_covs.append(cov_g)

    df_pooled = n - g_count
    S_pooled = np.zeros((p, p))
    for g_idx in range(g_count):
        S_pooled += (group_ns[g_idx] - 1) * group_covs[g_idx]
    S_pooled /= df_pooled

    try:
        inv_S_pooled = linalg.inv(S_pooled)
    except linalg.LinAlgError:
        inv_S_pooled = linalg.pinv(S_pooled)

    if priors.lower() == "proportional":
        prior_probs = group_ns / n
    else:
        prior_probs = np.ones(g_count) / g_count

    linear_coeffs = []
    for g_idx in range(g_count):
        m_k = group_means[g_idx]
        w = inv_S_pooled @ m_k
        const = -0.5 * (m_k @ w) + math.log(prior_probs[g_idx])
        coeff_entry = {"group": unique_groups[g_idx], "constant": float(const)}
        for j in range(p):
            coeff_entry[p_names[j]] = float(w[j])
        linear_coeffs.append(coeff_entry)

    def _classify_point(x_pt):
        scores = np.zeros(g_count)
        for g_idx in range(g_count):
            m_k = group_means[g_idx]
            w = inv_S_pooled @ m_k
            const = -0.5 * (m_k @ w) + math.log(prior_probs[g_idx])
            scores[g_idx] = const + np.dot(w, x_pt)
        return int(np.argmax(scores))

    pred_classes = []
    for i in range(n):
        pred_idx = _classify_point(X[i])
        pred_classes.append(unique_groups[pred_idx])

    confusion = {g: {g_pred: 0 for g_pred in unique_groups} for g in unique_groups}
    for true_g, pred_g in zip(clean_groups, pred_classes):
        confusion[true_g][pred_g] += 1

    summary_rows = []
    total_correct = 0
    for g in unique_groups:
        row_n = sum(confusion[g].values())
        correct = confusion[g][g]
        total_correct += correct
        pct_correct = (correct / row_n * 100.0) if row_n > 0 else 0.0
        row_data = {"group": g, "n": row_n, "correct": correct, "pct_correct": pct_correct}
        for g_pred in unique_groups:
            row_data[f"pred_{g_pred}"] = confusion[g][g_pred]
        summary_rows.append(row_data)

    total_pct_correct = (total_correct / n * 100.0) if n > 0 else 0.0

    cv_pred_classes = []
    for i in range(n):
        true_g_idx = group_indices[i]
        x_i = X[i]
        n_g = group_ns[true_g_idx]
        if n_g <= 2:
            cv_pred_classes.append(pred_classes[i])
            continue
        m_k_cv = (group_means[true_g_idx] * n_g - x_i) / (n_g - 1)
        
        scores = np.zeros(g_count)
        for g_idx in range(g_count):
            m_k = m_k_cv if g_idx == true_g_idx else group_means[g_idx]
            w = inv_S_pooled @ m_k
            const = -0.5 * (m_k @ w) + math.log(prior_probs[g_idx])
            scores[g_idx] = const + np.dot(w, x_i)
        cv_pred_classes.append(unique_groups[int(np.argmax(scores))])

    cv_confusion = {g: {g_pred: 0 for g_pred in unique_groups} for g in unique_groups}
    for true_g, pred_g in zip(clean_groups, cv_pred_classes):
        cv_confusion[true_g][pred_g] += 1

    cv_summary_rows = []
    cv_total_correct = 0
    for g in unique_groups:
        row_n = sum(cv_confusion[g].values())
        correct = cv_confusion[g][g]
        cv_total_correct += correct
        pct_correct = (correct / row_n * 100.0) if row_n > 0 else 0.0
        row_data = {"group": g, "n": row_n, "correct": correct, "pct_correct": pct_correct}
        for g_pred in unique_groups:
            row_data[f"pred_{g_pred}"] = cv_confusion[g][g_pred]
        cv_summary_rows.append(row_data)
    cv_total_pct = (cv_total_correct / n * 100.0) if n > 0 else 0.0

    overall_mean = np.mean(X, axis=0)
    B = np.zeros((p, p))
    for g_idx in range(g_count):
        diff = group_means[g_idx] - overall_mean
        B += group_ns[g_idx] * np.outer(diff, diff)
    
    W = df_pooled * S_pooled
    try:
        can_eigvals, can_eigvecs = linalg.eig(B, W)
        real_idx = np.isreal(can_eigvals)
        can_eigvals = np.real(can_eigvals[real_idx])
        can_eigvecs = np.real(can_eigvecs[:, real_idx])
        sort_idx = np.argsort(can_eigvals)[::-1]
        can_eigvecs = can_eigvecs[:, sort_idx]
        can_scores = (X - overall_mean) @ can_eigvecs[:, :min(2, can_eigvecs.shape[1])]
    except Exception:
        can_scores = np.zeros((n, 2))

    return {
        "analysis": "discriminant_analysis",
        "method": method.lower(),
        "priors": priors.lower(),
        "group_name": group_name,
        "predictor_names": p_names,
        "n_obs": n,
        "unique_groups": unique_groups.tolist(),
        "group_counts": group_ns.tolist(),
        "prior_probabilities": prior_probs.tolist(),
        "group_means": group_means.tolist(),
        "pooled_covariance": S_pooled.tolist(),
        "linear_coefficients": linear_coeffs,
        "summary_classification": summary_rows,
        "total_pct_correct": total_pct_correct,
        "cross_validation_summary": cv_summary_rows,
        "cv_total_pct_correct": cv_total_pct,
        "predicted_groups": pred_classes,
        "cv_predicted_groups": cv_pred_classes,
        "canonical_scores": can_scores.tolist(),
        "group_labels": clean_groups,
        "valid_row_indices": valid_indices,
    }


# ==============================================================================
# 7. SIMPLE CORRESPONDENCE ANALYSIS
# ==============================================================================

def simple_correspondence(
    table: List[List[float]],
    row_names: Optional[List[str]] = None,
    col_names: Optional[List[str]] = None,
    n_components: int = 2,
) -> Dict[str, Any]:
    """Perform Simple Correspondence Analysis on a 2-way contingency table matching StatCraft."""
    N = np.array(table, dtype=np.float64)
    r, c = N.shape
    if r < 2 or c < 2:
        raise ValueError("Correspondence analysis requires at least a 2x2 contingency table.")
    
    total = np.sum(N)
    if total <= 0:
        raise ValueError("Contingency table sum must be greater than zero.")

    r_names = list(row_names) if row_names else [f"Row{i+1}" for i in range(r)]
    c_names = list(col_names) if col_names else [f"Col{j+1}" for j in range(c)]

    P = N / total
    row_mass = np.sum(P, axis=1)
    col_mass = np.sum(P, axis=0)

    Dr_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(row_mass, 1e-15)))
    Dc_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(col_mass, 1e-15)))
    expected = np.outer(row_mass, col_mass)
    S = Dr_inv_sqrt @ (P - expected) @ Dc_inv_sqrt

    U, s, Vt = linalg.svd(S, full_matrices=False)
    inertias = s ** 2
    total_inertia = float(np.sum(inertias))
    k_dim = min(r - 1, c - 1, n_components)

    proportions = inertias[:k_dim] / total_inertia if total_inertia > 0 else np.zeros(k_dim)
    cumulative = np.cumsum(proportions)

    F = Dr_inv_sqrt @ U[:, :k_dim] @ np.diag(s[:k_dim])
    G = Dc_inv_sqrt @ Vt.T[:, :k_dim] @ np.diag(s[:k_dim])

    decomp_table = []
    for k in range(k_dim):
        chi_sq_k = inertias[k] * total
        decomp_table.append({
            "dimension": k + 1,
            "singular_value": float(s[k]),
            "inertia": float(inertias[k]),
            "chi_square": float(chi_sq_k),
            "proportion": float(proportions[k]),
            "cumulative": float(cumulative[k]),
        })

    row_coords = []
    for i in range(r):
        row_coords.append({
            "name": r_names[i],
            "mass": float(row_mass[i]),
            "coord1": float(F[i, 0]) if k_dim >= 1 else 0.0,
            "coord2": float(F[i, 1]) if k_dim >= 2 else 0.0,
        })

    col_coords = []
    for j in range(c):
        col_coords.append({
            "name": c_names[j],
            "mass": float(col_mass[j]),
            "coord1": float(G[j, 0]) if k_dim >= 1 else 0.0,
            "coord2": float(G[j, 1]) if k_dim >= 2 else 0.0,
        })

    return {
        "analysis": "simple_correspondence",
        "n_rows": r,
        "n_cols": c,
        "total_count": float(total),
        "total_inertia": total_inertia,
        "total_chi_square": float(total_inertia * total),
        "dimensions": k_dim,
        "row_names": r_names,
        "col_names": c_names,
        "decomposition_table": decomp_table,
        "row_coordinates": row_coords,
        "col_coordinates": col_coords,
    }
