"""Definitive Screening Designs (DSD) generator based on conference matrices.

References:
- Jones, B., & Nachtsheim, C. J. (2011). "A Class of Three-Level Designs for Physical
  Experiments in Which Main Effects Are Orthogonal to Two-Factor Interactions and None
  of the Two-Factor Interactions Are Completely Confounded with Each Other."
  Journal of Quality Technology, 43(1), 1-15.
- Xiao, L., Lin, D. K., & Bai, F. (2012). "Constructing Definitive Screening Designs
  Using Circulant Matrices." Statistica Sinica, 22(4), 1373-1388.
- Jones, B., & Nachtsheim, C. J. (2013). "Definitive screening designs with added
  two-level categorical factors." Journal of Quality Technology, 45(2), 121-129.
"""
from __future__ import annotations

import copy
import math
import random
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

from .model import Column, Worksheet


def _paley_skew(p: int) -> np.ndarray:
    """Construct a skew-symmetric conference matrix of order p + 1 for prime p = 3 mod 4."""
    chi = {0: 0}
    for k in range(1, p):
        chi[k] = 1 if pow(k, (p - 1) // 2, p) == 1 else -1
    Q = np.zeros((p, p), dtype=int)
    for i in range(p):
        for j in range(p):
            Q[i, j] = chi[(j - i) % p]
    m = p + 1
    S = np.zeros((m, m), dtype=int)
    S[0, 1:] = 1
    S[1:, 0] = -1
    S[1:, 1:] = Q
    return S


def _paley_symmetric(p: int) -> np.ndarray:
    """Construct a symmetric conference matrix of order p + 1 for prime p = 1 mod 4."""
    chi = {0: 0}
    for k in range(1, p):
        chi[k] = 1 if pow(k, (p - 1) // 2, p) == 1 else -1
    Q = np.zeros((p, p), dtype=int)
    for i in range(p):
        for j in range(p):
            Q[i, j] = chi[(i - j) % p]
    m = p + 1
    C = np.zeros((m, m), dtype=int)
    C[0, 1:] = 1
    C[1:, 0] = 1
    C[1:, 1:] = Q
    return C


def _two_circulant_10() -> np.ndarray:
    """Construct an orthogonal conference matrix of order 10 using two circulants."""
    a = [0, -1, 1, 1, -1]
    b = [-1, 1, 1, 1, 1]
    A = np.array([np.roll(a, i) for i in range(5)], dtype=int)
    B = np.array([np.roll(b, i) for i in range(5)], dtype=int)
    return np.block([[A, B], [-B.T, A.T]])


# Standard orthogonal conference matrix catalog for even orders
_CONFERENCE_CATALOG: Dict[int, np.ndarray] = {
    4: _paley_skew(3),
    6: _paley_symmetric(5),
    8: _paley_skew(7),
    10: _two_circulant_10(),
    12: _paley_skew(11),
    14: _paley_symmetric(13),
    18: _paley_symmetric(17),
    20: _paley_skew(19),
    24: _paley_skew(23),
}


def get_conference_matrix(order: int) -> np.ndarray:
    """Return an orthogonal conference matrix of the given order (or next available even order)."""
    if order in _CONFERENCE_CATALOG:
        return _CONFERENCE_CATALOG[order].copy()
    avail = sorted([m for m in _CONFERENCE_CATALOG if m >= order])
    if not avail:
        raise ValueError(f"DSD supports up to 24 factors (requested {order}).")
    return _CONFERENCE_CATALOG[avail[0]].copy()


def generate_dsd_coded_matrix(
    k: int,
    categorical_flags: Optional[Sequence[bool]] = None,
    extra_centers: int = 0,
) -> np.ndarray:
    """Generate a standard (2m + 1 + extra_centers) x k coded DSD matrix.
    
    For continuous factors, levels are -1, 0, +1.
    For 2-level categorical factors, center points 0 are replaced by +1 in the
    top fold and -1 in the bottom fold.
    """
    if not 3 <= k <= 24:
        raise ValueError(f"Number of factors must be between 3 and 24 (got {k}).")
    if extra_centers < 0:
        raise ValueError("Extra center points must be non-negative.")

    if categorical_flags is None:
        categorical_flags = [False] * k
    else:
        categorical_flags = list(categorical_flags)[:k]
        if len(categorical_flags) < k:
            categorical_flags.extend([False] * (k - len(categorical_flags)))

    # Find conference matrix of order m >= k
    avail = sorted([m for m in _CONFERENCE_CATALOG if m >= k])
    if not avail:
        raise ValueError(f"Unsupported factor count {k}.")
    m = avail[0]
    C = _CONFERENCE_CATALOG[m]

    # Foldover structure: [C; -C; zeros]
    top = C[:, :k].copy()
    bottom = -C[:, :k].copy()
    center = np.zeros((1 + extra_centers, k), dtype=int)

    # Adjust 2-level categorical factors
    for col_idx, is_cat in enumerate(categorical_flags):
        if is_cat:
            # Replace 0 in top half with +1, and 0 in bottom half with -1
            top[top[:, col_idx] == 0, col_idx] = 1
            bottom[bottom[:, col_idx] == 0, col_idx] = -1
            # In center runs, alternate +1 and -1 if multiple, or set to 1
            for c_idx in range(1 + extra_centers):
                center[c_idx, col_idx] = 1 if (c_idx % 2 == 0) else -1

    return np.vstack([top, bottom, center])


def create_definitive_screening_design(
    factors: Sequence[Dict[str, Any]],
    replicates: int = 1,
    extra_centers: int = 0,
    randomize: bool = True,
    seed: int = 1,
    name: str = "Definitive Screening Design",
) -> Worksheet:
    """Create a high-fidelity Definitive Screening Design Worksheet.

    Parameters:
    - factors: list of dicts with:
        'name': str
        'type': 'continuous' | 'categorical' (default 'continuous')
        'low': numeric low level (for continuous) or string/numeric level 1
        'high': numeric high level (for continuous) or string/numeric level 2
        'mid': optional numeric midpoint (defaults to (low + high) / 2)
    - replicates: number of full design replicates (1 to 5)
    - extra_centers: additional center runs per replicate (0 to 10)
    - randomize: whether to randomize run order
    - seed: randomization seed
    - name: worksheet name
    """
    if not (1 <= replicates <= 5):
        raise ValueError("Replicates must be between 1 and 5.")
    if not (0 <= extra_centers <= 10):
        raise ValueError("Extra center points must be between 0 and 10.")
    if not isinstance(factors, (list, tuple)) or not (3 <= len(factors) <= 24):
        raise ValueError("Specify between 3 and 24 factors for Definitive Screening Design.")

    reserved_names = {"stdorder", "runorder", "pttype", "blocks"}
    validated_factors = []
    cat_flags = []

    for idx, f in enumerate(factors):
        if not isinstance(f, dict):
            raise ValueError(f"Factor {idx + 1} must be a dictionary.")
        fname = str(f.get("name", f"X{idx + 1}")).strip()
        if not fname or fname.casefold() in reserved_names:
            raise ValueError(f"Factor name '{fname}' is invalid or reserved.")
        reserved_names.add(fname.casefold())

        ftype = f.get("type", "continuous").lower()
        if ftype not in ("continuous", "categorical"):
            ftype = "continuous"

        is_cat = (ftype == "categorical")
        cat_flags.append(is_cat)

        if not is_cat:
            try:
                low = float(f.get("low", -1.0))
                high = float(f.get("high", 1.0))
            except (ValueError, TypeError) as err:
                raise ValueError(f"Factor '{fname}' low and high settings must be numeric.") from err
            if low >= high:
                raise ValueError(f"Factor '{fname}' low setting ({low}) must be below high ({high}).")
            mid = float(f.get("mid", (low + high) / 2.0))
            validated_factors.append({
                "name": fname,
                "type": "continuous",
                "kind": "number",
                "low": low,
                "high": high,
                "mid": mid,
                "column_index": 4 + idx,
            })
        else:
            low_val = f.get("low", -1)
            high_val = f.get("high", 1)
            is_num_cat = isinstance(low_val, (int, float)) and isinstance(high_val, (int, float))
            validated_factors.append({
                "name": fname,
                "type": "categorical",
                "kind": "number" if is_num_cat else "text",
                "low": low_val,
                "high": high_val,
                "mid": None,
                "column_index": 4 + idx,
            })

    k = len(validated_factors)
    base_matrix = generate_dsd_coded_matrix(k, cat_flags, extra_centers)
    n_base = base_matrix.shape[0]

    # Replicates and blocks
    total_runs = n_base * replicates
    std_orders = list(range(1, total_runs + 1))
    blocks = []
    coded_all = []
    pt_types = []

    for rep in range(replicates):
        block_id = rep + 1
        for r_idx in range(n_base):
            row = base_matrix[r_idx]
            blocks.append(block_id)
            coded_all.append(row)
            # PtType: 0 = center run, 1 = design run (corners/axial)
            if np.all(row == 0):
                pt_types.append(0)
            elif any(cat_flags[c] and row[c] != 0 for c in range(k)):
                pt_types.append(1)
            else:
                pt_types.append(1)

    # Run order
    if randomize:
        rng = random.Random(seed)
        run_indices = list(range(total_runs))
        rng.shuffle(run_indices)
        run_orders = [0] * total_runs
        for pos, orig in enumerate(run_indices, 1):
            run_orders[orig] = pos
    else:
        run_orders = list(range(1, total_runs + 1))

    # Real factor column values
    factor_columns_data = [[] for _ in range(k)]
    for row in coded_all:
        for c_idx, val in enumerate(row):
            vf = validated_factors[c_idx]
            if vf["type"] == "continuous":
                if val == -1:
                    real_val = vf["low"]
                elif val == 1:
                    real_val = vf["high"]
                else:
                    real_val = vf["mid"]
                factor_columns_data[c_idx].append(float(real_val))
            else:
                # Categorical
                if val <= -1:
                    real_val = vf["low"]
                else:
                    real_val = vf["high"]
                factor_columns_data[c_idx].append(real_val)

    # Build worksheet columns
    cols = [
        Column("StdOrder", "number", [float(x) for x in std_orders]),
        Column("RunOrder", "number", [float(x) for x in run_orders]),
        Column("PtType", "number", [float(x) for x in pt_types]),
        Column("Blocks", "number", [float(x) for x in blocks]),
    ]

    for c_idx, vf in enumerate(validated_factors):
        cols.append(Column(vf["name"], vf["kind"], factor_columns_data[c_idx]))

    ws = Worksheet(name=name, columns=cols)

    # DOE Metadata
    ws.metadata["doe"] = {
        "schema": "statcraft-dsd-v1",
        "design": "definitive_screening",
        "factors": validated_factors,
        "runs": total_runs,
        "base_runs": n_base,
        "replicates": replicates,
        "extra_centers": extra_centers,
        "randomize": randomize,
        "seed": seed,
        "planner_configuration": {
            "kind": "definitive_screening",
            "factors": copy.deepcopy(validated_factors),
            "replicates": replicates,
            "centers": 1 + extra_centers,
            "randomize": randomize,
            "seed": seed,
            "blocks": replicates,
            "options": {"extra_centers": extra_centers},
            "name": name,
        },
    }

    return ws
