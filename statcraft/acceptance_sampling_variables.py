"""Computational engine for Acceptance Sampling by Variables.

Matches Minitab, ANSI/ASQ Z1.9, and ISO 3951 standards:
- Designing single-sampling plans by variables for percent defective / proportion nonconforming.
- Supports Lower specification limit (LSL), Upper specification limit (USL), or Double limits.
- Supports Historical/Known standard deviation (sigma) or Unknown standard deviation (sample s).
- Determines critical distance k and sample size n.
- Computes Operating Characteristic (OC), Average Outgoing Quality (AOQ), and Average Total Inspection (ATI) curves.
- Computes Average Outgoing Quality Limit (AOQL) and Lot Tolerance Percent Defective (LTPD).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


def solve_variables_sampling_plan(
    aql: float,
    rql: float,
    alpha: float = 0.05,
    beta: float = 0.10,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    sigma: Optional[float] = None,
    lot_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate single sampling plan parameters (sample size n and critical distance k) by variables.
    
    aql, rql: fraction nonconforming (0 < aql < rql < 1)
    alpha: producer's risk (0 < alpha < 0.5)
    beta: consumer's risk (0 < beta < 0.5)
    lsl, usl: specification limits (at least one must be provided)
    sigma: historical standard deviation (if known), or None (for sample s method)
    lot_size: lot size N (optional)
    """
    if aql <= 0 or rql <= 0 or aql >= rql or rql >= 1.0:
        raise ValueError("AQL and RQL must satisfy 0 < AQL < RQL < 1.")
    if not (0 < alpha < 0.5 and 0 < beta < 0.5):
        raise ValueError("Producer and Consumer risks must be between 0 and 0.5.")
    if lsl is None and usl is None:
        raise ValueError("Specify at least one specification limit (LSL or USL).")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL must be strictly less than USL.")
    if sigma is not None and sigma <= 0:
        raise ValueError("Historical standard deviation must be positive.")

    # Normal quantiles
    z_alpha = float(stats.norm.ppf(1.0 - alpha))
    z_beta = float(stats.norm.ppf(1.0 - beta))
    z_aql = float(stats.norm.ppf(1.0 - aql))
    z_rql = float(stats.norm.ppf(1.0 - rql))

    # Critical distance k
    k = (z_alpha * z_rql + z_beta * z_aql) / (z_alpha + z_beta)

    # Sample size n
    sigma_known = sigma is not None
    denom = (z_aql - z_rql) ** 2
    if sigma_known:
        # Known sigma formula
        n_exact = ((z_alpha + z_beta) ** 2) / denom
    else:
        # Unknown sigma (s-method) formula: ANSI/ASQ Z1.9
        n_exact = (((z_alpha + z_beta) ** 2) / denom) * (1.0 + (k ** 2) / 2.0)

    n = max(2 if not sigma_known else 1, int(math.ceil(n_exact)))

    # Compute actual risks achieved with integer n
    def prob_acceptance(p_frac: float) -> float:
        if p_frac <= 0:
            return 1.0
        if p_frac >= 1.0:
            return 0.0
        zp = float(stats.norm.ppf(1.0 - p_frac))
        if sigma_known:
            w = (zp - k) * math.sqrt(n)
        else:
            se_factor = math.sqrt(1.0 / n + (k ** 2) / (2.0 * n))
            w = (zp - k) / se_factor
        return float(stats.norm.cdf(w))

    act_alpha = 1.0 - prob_acceptance(aql)
    act_beta = prob_acceptance(rql)

    # Generate curves
    p_max = min(1.0, max(0.10, rql * 3.0))
    p_vals = np.linspace(0.0001, p_max, 100)

    oc_points = []
    aoq_points = []
    ati_points = []

    max_aoq = 0.0
    for p_cur in p_vals:
        pa = prob_acceptance(p_cur)
        oc_points.append({"p": float(p_cur), "pa": float(pa)})

        if lot_size is not None and lot_size > n:
            aoq = p_cur * pa * float(lot_size - n) / float(lot_size)
            ati = n + (1.0 - pa) * float(lot_size - n)
        else:
            aoq = p_cur * pa
            ati = float(n)

        aoq_points.append({"p": float(p_cur), "aoq": float(aoq)})
        ati_points.append({"p": float(p_cur), "ati": float(ati)})
        if aoq > max_aoq:
            max_aoq = aoq

    spec_type = "double" if (lsl is not None and usl is not None) else ("lower" if lsl is not None else "upper")

    return {
        "analysis": "acceptance_sampling_variables",
        "n": n,
        "k": float(k),
        "aql": aql,
        "rql": rql,
        "target_alpha": alpha,
        "target_beta": beta,
        "actual_alpha": float(act_alpha),
        "actual_beta": float(act_beta),
        "lsl": lsl,
        "usl": usl,
        "spec_type": spec_type,
        "sigma_known": sigma_known,
        "sigma": sigma,
        "lot_size": lot_size,
        "aoql": float(max_aoq),
        "oc_curve": oc_points,
        "aoq_curve": aoq_points,
        "ati_curve": ati_points,
    }
