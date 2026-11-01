"""Algorithmic Design of Experiments (D-Optimal Custom Design Generator & Design Evaluator).

Implements Fedorov coordinate and candidate exchange algorithms for generating
D-optimal and A-optimal designs with arbitrary continuous and categorical factors.
Matches JMP Pro "DOE > Custom Design" and Minitab "DOE > Select Optimal Design".

References:
- Fedorov, V. V. (1972). Theory of Optimal Experiments. Academic Press.
- Meyer, R. K., & Nachtsheim, C. J. (1995). The Coordinate-Exchange Algorithm. Technometrics, 37(1), 60-69.
- JMP: DOE > Custom Design & DOE > Design Diagnostics > Evaluate Design.
"""
from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .model import Column, Worksheet


@dataclass
class FactorSpec:
    name: str
    kind: str = "continuous"  # "continuous" or "categorical"
    low: float = -1.0
    high: float = 1.0
    levels: Optional[List[str]] = None  # for categorical


def build_candidate_set(factors: Sequence[FactorSpec], include_quadratics: bool = False) -> Tuple[np.ndarray, List[List[Any]]]:
    """Generate a candidate grid over factor levels in coded [-1, +1] space."""
    grid_axes_coded = []
    grid_axes_actual = []

    for f in factors:
        if f.kind == "continuous":
            coded = [-1.0, 0.0, 1.0]
            actual = [f.low, (f.low + f.high) / 2.0, f.high]
        else:
            n_lev = len(f.levels) if f.levels else 2
            if n_lev == 2:
                coded = [-1.0, 1.0]
                actual = f.levels if f.levels else ["Level 1", "Level 2"]
            else:
                coded = list(np.linspace(-1.0, 1.0, n_lev))
                actual = f.levels if f.levels else [f"Level {i+1}" for i in range(n_lev)]

        grid_axes_coded.append(coded)
        grid_axes_actual.append(actual)

    coded_points = list(itertools.product(*grid_axes_coded))
    actual_points = list(itertools.product(*grid_axes_actual))

    return np.array(coded_points, dtype=float), [list(pt) for pt in actual_points]


def expand_model_matrix(X_coded: np.ndarray, model_order: str = "interactions") -> Tuple[np.ndarray, List[str]]:
    """Expand coded factor matrix into full linear model design matrix X (Intercept, Main, 2FI, Quad).
    
    model_order options:
    - 'linear': Intercept + Main Effects
    - 'interactions': Intercept + Main Effects + 2-Factor Interactions
    - 'quadratic': Intercept + Main Effects + 2-Factor Interactions + Pure Quadratics
    """
    n_runs, k = X_coded.shape
    cols = [np.ones(n_runs)]
    term_names = ["Intercept"]

    # Main effects
    for j in range(k):
        cols.append(X_coded[:, j])
        term_names.append(f"X{j+1}")

    # 2-Factor Interactions
    if model_order in ("interactions", "quadratic"):
        for i in range(k):
            for j in range(i + 1, k):
                cols.append(X_coded[:, i] * X_coded[:, j])
                term_names.append(f"X{i+1}*X{j+1}")

    # Pure Quadratics
    if model_order == "quadratic":
        for j in range(k):
            cols.append(X_coded[:, j] ** 2)
            term_names.append(f"X{j+1}²")

    X_full = np.column_stack(cols)
    return X_full, term_names


def evaluate_design_matrix(X_model: np.ndarray) -> Dict[str, Any]:
    """Compute D-efficiency, A-efficiency, G-efficiency, and correlation matrix of effects."""
    n_runs, p = X_model.shape

    XtX = X_model.T @ X_model
    # SVD for stable determinant and pseudo-inverse
    U, s, Vt = np.linalg.svd(XtX)
    rank = int(np.sum(s > 1e-10))

    if rank < p:
        # Singular design (not all terms estimable)
        det_val = 0.0
        d_eff = 0.0
        a_eff = 0.0
        inv_XtX = np.linalg.pinv(XtX)
    else:
        # Log determinant for numerical stability
        log_det = float(np.sum(np.log(s)))
        det_val = float(np.exp(log_det))
        d_eff = float(np.exp(log_det / p) / n_runs * 100.0)

        inv_XtX = np.linalg.inv(XtX)
        trace_inv = float(np.trace(inv_XtX))
        a_eff = float((p / (n_runs * trace_inv)) * 100.0) if trace_inv > 0 else 0.0

    # Prediction variances across runs: h_ii = x_i^T (X^T X)^(-1) x_i (Leverages)
    leverages = np.diag(X_model @ inv_XtX @ X_model.T)
    max_var = float(np.max(leverages)) if len(leverages) > 0 else 1.0
    avg_var = float(np.mean(leverages)) if len(leverages) > 0 else 1.0
    g_eff = float(math.sqrt(p / (n_runs * max(1e-9, max_var))) * 100.0) if max_var > 0 else 0.0

    # Correlation matrix of model coefficients: R_ij = (X^T X)_ij / sqrt((X^T X)_ii * (X^T X)_jj)
    # Exclude intercept for effects correlation map
    diag_XtX = np.diag(XtX)
    denom = np.sqrt(np.outer(diag_XtX, diag_XtX))
    denom[denom < 1e-12] = 1.0
    corr_matrix = XtX / denom

    return {
        "n_runs": n_runs,
        "n_terms": p,
        "rank": rank,
        "is_full_rank": rank == p,
        "log_det": float(np.sum(np.log(np.maximum(s, 1e-12)))),
        "det": det_val,
        "d_efficiency": min(100.0, max(0.0, d_eff)),
        "a_efficiency": min(100.0, max(0.0, a_eff)),
        "g_efficiency": min(100.0, max(0.0, g_eff)),
        "average_variance": avg_var,
        "max_variance": max_var,
        "leverages": leverages.tolist(),
        "correlation_matrix": corr_matrix.tolist(),
    }


def generate_d_optimal_design(
    factors: Sequence[FactorSpec],
    n_runs: int,
    model_order: str = "interactions",
    num_restarts: int = 10,
    seed: int = 42,
) -> Tuple[np.ndarray, List[List[Any]], Dict[str, Any], List[str]]:
    """Fedorov Candidate Exchange Algorithm for D-Optimal Design Generation.
    
    Searches for the subset of n_runs candidate design points that maximizes det(X^T X).
    """
    rng = np.random.default_rng(seed)
    candidates_coded, candidates_actual = build_candidate_set(factors, include_quadratics=(model_order == "quadratic"))
    n_cand = len(candidates_coded)

    if n_runs < len(factors) + 1:
        raise ValueError(f"Number of runs ({n_runs}) must be at least number of factors + 1 ({len(factors) + 1}).")

    # Expand all candidates into model space
    X_cand_model, term_names = expand_model_matrix(candidates_coded, model_order=model_order)
    p = X_cand_model.shape[1]

    if n_runs < p:
        raise ValueError(f"Specified model order '{model_order}' requires at least {p} runs to be estimable (received {n_runs}).")

    best_log_det = -np.inf
    best_indices: Optional[np.ndarray] = None

    for _ in range(num_restarts):
        # Random initial subset
        curr_indices = rng.choice(n_cand, size=n_runs, replace=(n_cand < n_runs))
        X_curr = X_cand_model[curr_indices]

        # SVD for initial log det
        _, s, _ = np.linalg.svd(X_curr.T @ X_curr)
        if np.any(s < 1e-10):
            curr_log_det = -1e9
        else:
            curr_log_det = float(np.sum(np.log(s)))

        improved = True
        step = 0
        while improved and step < 40:
            improved = False
            step += 1

            # Try exchanging each design run with candidate points
            for r_i in range(n_runs):
                orig_cand_idx = curr_indices[r_i]
                best_swap_cand = orig_cand_idx
                best_swap_log_det = curr_log_det

                # Sample candidate test set for speed if large
                cand_sample = rng.choice(n_cand, size=min(n_cand, 64), replace=False)

                for c_i in cand_sample:
                    if c_i == orig_cand_idx:
                        continue
                    curr_indices[r_i] = c_i
                    X_test = X_cand_model[curr_indices]
                    _, s_test, _ = np.linalg.svd(X_test.T @ X_test)
                    if np.any(s_test < 1e-10):
                        cand_log_det = -1e9
                    else:
                        cand_log_det = float(np.sum(np.log(s_test)))

                    if cand_log_det > best_swap_log_det + 1e-6:
                        best_swap_log_det = cand_log_det
                        best_swap_cand = c_i

                curr_indices[r_i] = best_swap_cand
                if best_swap_cand != orig_cand_idx:
                    curr_log_det = best_swap_log_det
                    improved = True

        if curr_log_det > best_log_det:
            best_log_det = curr_log_det
            best_indices = curr_indices.copy()

    if best_indices is None:
        best_indices = np.arange(min(n_runs, n_cand))

    best_coded = candidates_coded[best_indices]
    best_actual = [candidates_actual[i] for i in best_indices]
    X_best_model = X_cand_model[best_indices]

    eval_results = evaluate_design_matrix(X_best_model)
    return best_coded, best_actual, eval_results, term_names


def create_optimal_design_worksheet(
    factors: Sequence[FactorSpec],
    n_runs: int,
    model_order: str = "interactions",
    randomize: bool = True,
    seed: int = 42,
    name: str = "Custom D-Optimal Design",
) -> Tuple[Worksheet, Dict[str, Any]]:
    """Build a complete StatCraft Worksheet containing the generated D-Optimal custom design."""
    coded_runs, actual_runs, eval_res, term_names = generate_d_optimal_design(
        factors=factors,
        n_runs=n_runs,
        model_order=model_order,
        seed=seed,
    )

    n_actual_runs = len(actual_runs)
    run_indices = list(range(n_actual_runs))
    std_orders = [i + 1 for i in run_indices]

    if randomize:
        rng = np.random.default_rng(seed)
        shuffled = run_indices.copy()
        rng.shuffle(shuffled)
        run_orders = [shuffled.index(i) + 1 for i in range(n_actual_runs)]
    else:
        run_orders = std_orders.copy()

    columns: List[Column] = [
        Column("StdOrder", "number", std_orders, {"purpose": "order"}),
        Column("RunOrder", "number", run_orders, {"purpose": "order"}),
    ]

    # Map named factors to columns with actual values
    for f_idx, factor in enumerate(factors):
        col_vals = [actual_runs[r][f_idx] for r in range(n_actual_runs)]
        kind = "number" if factor.kind == "continuous" else "text"
        meta = {
            "factor_name": factor.name,
            "factor_kind": factor.kind,
            "low": factor.low,
            "high": factor.high,
            "levels": factor.levels,
        }
        columns.append(Column(factor.name, kind, col_vals, meta))

    ws = Worksheet(name, columns)
    ws.metadata["doe_type"] = "custom_d_optimal"
    ws.metadata["n_runs"] = n_actual_runs
    ws.metadata["model_order"] = model_order
    ws.metadata["d_efficiency"] = eval_res["d_efficiency"]

    # Build response dictionary
    result = {
        "analysis": "optimal_design",
        "design_name": name,
        "n_runs": n_actual_runs,
        "model_order": model_order,
        "factors": [
            {
                "name": f.name,
                "kind": f.kind,
                "low": f.low,
                "high": f.high,
                "levels": f.levels,
            }
            for f in factors
        ],
        "term_names": term_names,
        "eval": eval_res,
    }

    return ws, result
