"""Covariance Matrix computation for StatCraft.

Computes sample covariance between numeric columns:
    Cov(X, Y) = sum((x_i - x_bar) * (y_i - y_bar)) / (N - 1)

Supports:
- Pairwise deletion (uses complete pairs per variable combination)
- Listwise deletion (uses rows complete across all selected variables)
- Formatted symmetric lower-triangular matrix output
"""
from __future__ import annotations

import math
from itertools import combinations, zip_longest
from .engine import normalize_numeric


def compute_covariance(samples: list[list[float | None]], names: list[str], missing: str = 'Pairwise') -> dict:
    if missing not in ('Pairwise', 'Listwise'):
        raise ValueError("Missing policy must be 'Pairwise' or 'Listwise'.")
    if not 2 <= len(samples) <= 50 or len(names) != len(samples):
        raise ValueError("Select 2 to 50 numeric variables.")

    data = [[normalize_numeric(v) for v in sample] for sample in samples]
    rows = list(zip_longest(*data, fillvalue=None))
    complete = [row for row in rows if all(v is not None for v in row)]

    num_vars = len(names)
    matrix = [[None for _ in range(num_vars)] for _ in range(num_vars)]
    n_matrix = [[0 for _ in range(num_vars)] for _ in range(num_vars)]
    warnings = []

    # Calculate diagonal (variances) and off-diagonal (covariances)
    for a in range(num_vars):
        for b in range(a, num_vars):
            if missing == 'Listwise':
                pairs = [(r[a], r[b]) for r in complete if r[a] is not None and r[b] is not None]
            else:
                pairs = [(r[a], r[b]) for r in rows if r[a] is not None and r[b] is not None]

            n = len(pairs)
            n_matrix[a][b] = n
            n_matrix[b][a] = n

            if n < 2:
                warnings.append(f"{names[a]} / {names[b]}: at least 2 complete observations required.")
                cov = None
            else:
                xs = [p[0] for p in pairs]
                ys = [p[1] for p in pairs]
                x_bar = sum(xs) / n
                y_bar = sum(ys) / n
                cov = sum((x - x_bar) * (y - y_bar) for x, y in pairs) / (n - 1)
                cov = round(cov, 6)

            matrix[a][b] = cov
            matrix[b][a] = cov

    return {
        'analysis': 'covariance',
        'variables': list(names),
        'missing': missing,
        'matrix': matrix,
        'n_matrix': n_matrix,
        'warnings': warnings,
    }
