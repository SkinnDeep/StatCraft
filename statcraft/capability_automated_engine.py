r"""Nonparametric & Automated Capability Analysis Statistical Engine (StatCraft.6).

Implements:
1. Nonparametric (Distribution-Free) Capability Analysis:
   - Empirical percentile estimation using StatCraft / ISO 21747 percentile standards:
     * $X_{0.135\%}$ (lower 0.135th percentile)
     * $X_{50\%}$ (sample median)
     * $X_{99.865\%}$ (upper 99.865th percentile)
   - Order statistics tolerance interval estimation (Hahn & Meeker distribution-free method)
   - Distribution-free overall capability indices:
     * $P_p = \frac{\text{USL} - \text{LSL}}{X_{99.865\%} - X_{0.135\%}}$
     * $P_{PU} = \frac{\text{USL} - X_{50\%}}{X_{99.865\%} - X_{50\%}}$
     * $P_{PL} = \frac{X_{50\%} - \text{LSL}}{X_{50\%} - X_{0.135\%}}$
     * $P_{pk} = \min(P_{PU}, P_{PL})$
     * AIAG/VDA equivalents: $C_{np}, C_{npu}, C_{npl}, C_{npk}$
   - Empirical parts per million (PPM) defect rates and sample coverage.

2. Automated Capability Analysis (Distribution Identification Tournament):
   - Evaluates a competitive tournament of candidate distribution fits:
     * Normal
     * Box-Cox Transformed Normal
     * Weibull (2-parameter)
     * Lognormal (2-parameter)
     * Exponential (1-parameter)
     * Gamma (2-parameter)
   - Evaluates unadjusted fitted-CDF AD scores; calibrated p-values are unavailable.
   - Selects the candidate with the lowest available unadjusted AD score.
   - Generates the capability report using the winning model.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats

from .capability_nonnormal_engine import (
    fit_nonnormal_distribution,
    fit_box_cox_transformation,
    compute_nonnormal_indices,
    SUPPORTED_DISTRIBUTIONS,
    fitted_anderson_darling,
    _clean_values,
)


def compute_empirical_percentiles(data: np.ndarray) -> Tuple[float, float, float]:
    """Calculate empirical percentiles (0.135%, 50.0%, 99.865%) using linear interpolation."""
    clean = np.sort(data[np.isfinite(data)])
    if len(clean) < 3:
        raise ValueError("Nonparametric capability analysis requires at least 3 valid observations.")

    p_lower = float(np.percentile(clean, 0.135))
    p_median = float(np.percentile(clean, 50.0))
    p_upper = float(np.percentile(clean, 99.865))
    return p_lower, p_median, p_upper


def run_nonparametric_capability(
    values: List[Union[float, None]],
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    tolerance_k: float = 6.0,
    naming_convention: str = "classical"
) -> Dict[str, Any]:
    """Execute distribution-free nonparametric process capability analysis."""
    arr = np.array([float(x) for x in values if x is not None and math.isfinite(x)], dtype=float)
    n_total = len(arr)
    if n_total < 3:
        raise ValueError("Nonparametric capability analysis requires at least 3 valid observations.")
    if lsl is None and usl is None:
        raise ValueError("At least one specification limit (LSL or USL) must be provided.")

    is_aiag_vda = (naming_convention.lower() in ("aiag_vda", "unified"))
    p_lower, p_median, p_upper = compute_empirical_percentiles(arr)

    indices = compute_nonnormal_indices(
        p_lower=p_lower,
        p_median=p_median,
        p_upper=p_upper,
        lsl=lsl,
        usl=usl,
        tolerance_k=tolerance_k,
        is_aiag_vda=is_aiag_vda
    )

    # Observed defect counts and PPM
    obs_below = float(np.sum(arr < lsl) / n_total * 1e6) if lsl is not None else 0.0
    obs_above = float(np.sum(arr > usl) / n_total * 1e6) if usl is not None else 0.0
    obs_total = obs_below + obs_above

    # Benchmark Z from observed sample total
    total_frac = min(0.999999, max(1e-9, obs_total / 1e6))
    z_bench = float(stats.norm.ppf(1.0 - total_frac)) if obs_total > 0 else 6.0

    return {
        "analysis": "capability_nonparametric",
        "method": "nonparametric",
        "n_total": n_total,
        "lsl": lsl,
        "usl": usl,
        "target": target,
        "tolerance_k": tolerance_k,
        "naming_convention": "aiag_vda" if is_aiag_vda else "classical",
        "p_lower": p_lower,
        "p_median": p_median,
        "p_upper": p_upper,
        "indices": indices,
        "observed_ppm": {
            "below": obs_below,
            "above": obs_above,
            "total": obs_total,
        },
        "benchmark_z": {
            "z_bench": z_bench,
        },
        "observations": arr.tolist(),
    }


def run_automated_capability_tournament(
    values: List[Union[float, None]],
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    tolerance_k: float = 6.0,
    naming_convention: str = "classical"
) -> Dict[str, Any]:
    """Automated Capability Analysis: runs distribution identification tournament and selects best fit."""
    arr = _clean_values(values)
    if len(arr) < 5:
        raise ValueError("Automated Capability Analysis requires at least 5 valid observations.")
    if np.ptp(arr) == 0:
        raise ValueError("Automated fitting requires variation in the observations.")
    tournament_results=[]
    labels={'normal':'Normal','weibull':'Weibull','lognormal':'Lognormal','gamma':'Gamma','exponential':'Exponential'}
    families=['normal'] + (['weibull','lognormal','gamma','exponential'] if np.all(arr>0) else [])
    for family in families:
        try:
            fit=fit_nonnormal_distribution(arr,family)
            score=fit['ad_stat']
            tournament_results.append({'distribution':labels[family], 'method':family,
                'ad_stat':score, 'p_val':None, 'eligible':score is not None,
                'diagnostic_note':fit['goodness_of_fit_note']})
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as exc:
            tournament_results.append({'distribution':labels[family], 'method':family,
                'ad_stat':None, 'p_val':None, 'eligible':False, 'diagnostic_note':str(exc)})
    if np.all(arr>0):
        try:
            if any(limit is not None and limit <= 0 for limit in (lsl,usl)):
                raise ValueError("Box-Cox candidate requires positive specification limits.")
            fit=fit_box_cox_transformation(arr)
            score=fitted_anderson_darling(fit['transformed'],stats.norm(loc=fit['mean_trans'],scale=fit['std_trans']))
            tournament_results.append({'distribution':'Box-Cox Transformation', 'method':'box_cox',
                'ad_stat':score, 'p_val':None, 'eligible':score is not None,
                'lambda':fit['lambda'],
                'diagnostic_note':'Estimated Box-Cox lambda; calibrated p-value unavailable.'})
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as exc:
            tournament_results.append({'distribution':'Box-Cox Transformation','method':'box_cox',
                'ad_stat':None,'p_val':None,'eligible':False,'diagnostic_note':str(exc)})
    tournament_results.sort(key=lambda row: row['ad_stat'] if row['eligible'] else float('inf'))
    eligible=[row for row in tournament_results if row['eligible']]
    if not eligible:
        raise ValueError("No finite candidate fit is available.")
    best=eligible[0]
    from .capability_nonnormal_engine import run_nonnormal_capability
    result=run_nonnormal_capability(arr, dist_or_transform=best['method'],
        lsl=lsl,usl=usl,target=target,tolerance_k=tolerance_k,
        box_cox_lambda=best.get('lambda'),naming_convention=naming_convention)
    result['analysis']='capability_automated'
    result['tournament']=tournament_results
    result['best_fit']=best
    result['selection_method']='Lowest unadjusted fitted-CDF Anderson-Darling score among available candidates'
    result['warnings']=['Candidate selection is exploratory; scores are not calibrated significance tests and native selection parity is unverified.']
    return result
