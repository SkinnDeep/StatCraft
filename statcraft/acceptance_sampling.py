"""Acceptance Sampling by Attributes Computational Engine.

Minitab Standard Acceptance Sampling by Attributes:
- Designs or compares single-sampling plans for attribute inspection (go/no-go defectives or defect count).
- Derives optimal sample size (n) and acceptance number (c) given:
    - AQL (Acceptable Quality Level) and Producer's Risk (alpha)
    - RQL / LTPD (Rejectable Quality Level / Lot Tolerance Percent Defective) and Consumer's Risk (beta)
    - Optional Lot Size (N) for finite population correction (Hypergeometric) or infinite (Binomial/Poisson)
- Computes Operating Characteristic (OC), Average Outgoing Quality (AOQ), and Average Total Inspection (ATI) curves.
- Computes Average Outgoing Quality Limit (AOQL) and actual realized risks.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union


DEFAULT_SETTINGS = {
    "aql": 0.01,              # Acceptable Quality Level (e.g. 1% = 0.01)
    "rql": 0.05,              # Rejectable Quality Level / LTPD (e.g. 5% = 0.05)
    "alpha": 0.05,            # Producer's Risk
    "beta": 0.10,             # Consumer's Risk
    "lot_size": None,         # Optional finite lot size N
    "measurement_type": "defective",  # 'defective' (go/no-go) or 'defect' (count)
    "algorithm": "binomial",  # 'binomial', 'hypergeometric', or 'poisson'
    "user_n": None,           # For user-specified plan comparison
    "user_c": None,
    "title": "",
}


def _binom_cdf(k: int, n: int, p: float) -> float:
    """Cumulative probability P(X <= k) for Binomial(n, p)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0

    # Lazy import scipy.stats for numerical stability with large n
    from scipy.stats import binom
    return float(binom.cdf(k, n, p))


def _hypergeom_cdf(k: int, M: int, n: int, N: int) -> float:
    """Cumulative probability P(X <= k) for Hypergeometric: Lot size N, defectives M, sample size n."""
    if k < 0:
        return 0.0
    from scipy.stats import hypergeom
    return float(hypergeom.cdf(k, N, M, n))


def _poisson_cdf(k: int, mu: float) -> float:
    """Cumulative probability P(X <= k) for Poisson(mu)."""
    if k < 0:
        return 0.0
    if mu <= 0.0:
        return 1.0
    from scipy.stats import poisson
    return float(poisson.cdf(k, mu))


def solve_attribute_sampling_plan(
    aql: float,
    rql: float,
    alpha: float = 0.05,
    beta: float = 0.10,
    lot_size: Optional[int] = None,
    measurement_type: str = "defective",
) -> Tuple[int, int]:
    """Find the minimal sample size n and integer acceptance number c.
    
    Conditions:
      P(Accept | p = AQL) >= 1 - alpha  (Producer's risk condition)
      P(Accept | p = RQL) <= beta       (Consumer's risk condition)
    """
    if aql <= 0 or aql >= 1.0:
        raise ValueError("AQL must be strictly between 0 and 1.")
    if rql <= aql or rql >= 1.0:
        raise ValueError("RQL must be strictly greater than AQL and less than 1.")
    if alpha <= 0 or alpha >= 1.0:
        raise ValueError("Alpha (Producer's risk) must be strictly between 0 and 1.")
    if beta <= 0 or beta >= 1.0:
        raise ValueError("Beta (Consumer's risk) must be strictly between 0 and 1.")

    use_hyper = (lot_size is not None and lot_size > 0)
    max_n = lot_size if use_hyper and lot_size else 10000

    # Search starting from c = 0 upwards
    best_n = None
    best_c = None

    for c in range(0, 50):
        # Find minimum n where P(Accept | RQL) <= beta
        # Since P(Accept) is non-increasing in n, we can use binary search or step
        low = c + 1
        high = max_n

        # Check if even high satisfies beta condition
        p_high = (_hypergeom_cdf(c, int(round(rql * lot_size)), high, lot_size)
                  if use_hyper else
                  _binom_cdf(c, high, rql))
        if p_high > beta:
            continue

        sol_n = high
        while low <= high:
            mid = (low + high) // 2
            if use_hyper:
                p_rql = _hypergeom_cdf(c, int(round(rql * lot_size)), mid, lot_size)
            else:
                p_rql = _binom_cdf(c, mid, rql)

            if p_rql <= beta:
                sol_n = mid
                high = mid - 1
            else:
                low = mid + 1

        # Now check if this sol_n satisfies producer's risk condition at AQL
        if use_hyper:
            p_aql = _hypergeom_cdf(c, int(round(aql * lot_size)), sol_n, lot_size)
        else:
            p_aql = _binom_cdf(c, sol_n, aql)

        if p_aql >= 1.0 - alpha:
            best_n = sol_n
            best_c = c
            break

    if best_n is None:
        # Fallback to nearest reasonable integer plan
        best_n = min(50, max_n)
        best_c = 1

    return best_n, best_c


def compute_acceptance_sampling_attributes(
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute complete Acceptance Sampling by Attributes statistics and curve coordinates."""
    opts = dict(DEFAULT_SETTINGS)
    if settings:
        opts.update(settings)

    aql = float(opts.get("aql", 0.01))
    rql = float(opts.get("rql", 0.05))
    alpha = float(opts.get("alpha", 0.05))
    beta = float(opts.get("beta", 0.10))
    lot_size = int(opts["lot_size"]) if opts.get("lot_size") else None
    meas_type = str(opts.get("measurement_type", "defective")).lower()

    user_n = opts.get("user_n")
    user_c = opts.get("user_c")

    if user_n is not None and user_c is not None:
        n = int(user_n)
        c = int(user_c)
        is_user_plan = True
    else:
        n, c = solve_attribute_sampling_plan(
            aql=aql,
            rql=rql,
            alpha=alpha,
            beta=beta,
            lot_size=lot_size,
            measurement_type=meas_type,
        )
        is_user_plan = False

    use_hyper = (lot_size is not None and lot_size > 0 and n < lot_size)

    # Actual realized risks
    if use_hyper:
        m_aql = int(round(aql * lot_size))
        m_rql = int(round(rql * lot_size))
        actual_p_accept_aql = _hypergeom_cdf(c, m_aql, n, lot_size)
        actual_p_accept_rql = _hypergeom_cdf(c, m_rql, n, lot_size)
    else:
        actual_p_accept_aql = _binom_cdf(c, n, aql)
        actual_p_accept_rql = _binom_cdf(c, n, rql)

    actual_alpha = 1.0 - actual_p_accept_aql
    actual_beta = actual_p_accept_rql

    # Generate high-resolution curve points (OC, AOQ, ATI)
    # p from 0 to min(1.0, 3.5 * rql)
    p_max = min(1.0, max(0.10, 3.5 * rql))
    num_pts = 100
    curve_p = [i * (p_max / (num_pts - 1)) for i in range(num_pts)]

    curve_oc = []
    curve_aoq = []
    curve_ati = []

    for p_val in curve_p:
        if use_hyper:
            m_val = int(round(p_val * lot_size))
            p_acc = _hypergeom_cdf(c, m_val, n, lot_size)
            # AOQ with rectification: defects found in rejected lots replaced
            aoq_val = (p_val * p_acc * (lot_size - n)) / lot_size
            ati_val = n + (1.0 - p_acc) * (lot_size - n)
        else:
            p_acc = _binom_cdf(c, n, p_val)
            if lot_size:
                aoq_val = (p_val * p_acc * (lot_size - n)) / lot_size
                ati_val = n + (1.0 - p_acc) * (lot_size - n)
            else:
                aoq_val = p_val * p_acc
                ati_val = None

        curve_oc.append(p_acc)
        curve_aoq.append(aoq_val)
        if ati_val is not None:
            curve_ati.append(ati_val)

    # Calculate AOQL (Average Outgoing Quality Limit = maximum of AOQ curve)
    aoql = max(curve_aoq)
    aoql_idx = curve_aoq.index(aoql)
    p_at_aoql = curve_p[aoql_idx]

    curves = {
        "p_values": curve_p,
        "oc_values": curve_oc,
        "aoq_values": curve_aoq,
        "ati_values": curve_ati if curve_ati else None,
        "p_max": p_max,
        "aoql": aoql,
        "p_at_aoql": p_at_aoql,
    }

    return {
        "analysis": "acceptance_sampling_attributes",
        "sample_size": n,
        "acceptance_number": c,
        "aql": aql,
        "rql": rql,
        "target_alpha": alpha,
        "target_beta": beta,
        "actual_alpha": actual_alpha,
        "actual_beta": actual_beta,
        "actual_p_accept_aql": actual_p_accept_aql,
        "actual_p_accept_rql": actual_p_accept_rql,
        "lot_size": lot_size,
        "measurement_type": meas_type,
        "is_user_plan": is_user_plan,
        "aoql": aoql,
        "p_at_aoql": p_at_aoql,
        "curves": curves,
        "settings": opts,
    }
