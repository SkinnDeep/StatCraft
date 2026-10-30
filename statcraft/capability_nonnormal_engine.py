# Nonnormal Process Capability Analysis (StatCraft.6).
#
# Supports:
# - Parametric nonnormal distribution fitting:
#   * Weibull (2-parameter)
#   * Lognormal (2-parameter)
#   * Exponential (1-parameter)
#   * Gamma (2-parameter)
# - Transformations to normality:
#   * Box-Cox power transformation (optimal lambda or specified lambda)
# - Overall nonnormal capability indices using ISO 21747 / StatCraft percentile method:
#   * Pp = (USL - LSL) / (X_99.865% - X_0.135%)
#   * PPU = (USL - X_50%) / (X_99.865% - X_50%)
#   * PPL = (X_50% - LSL) / (X_50% - X_0.135%)
#   * Ppk = min(PPU, PPL)
#   * AIAG/VDA nomenclature equivalents: Cnp, Cnpu, Cnpl, Cnpk
# - Benchmark Z statistics:
#   * Z_bench = Phi^-1(1 - P_total_defect)
# - Parts Per Million (PPM) / Percentage expected defect rates vs observed sample rates.
# - Goodness-of-fit statistics (Anderson-Darling test).

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats
import numbers


SUPPORTED_DISTRIBUTIONS = ["weibull", "lognormal", "exponential", "gamma", "normal"]
SUPPORTED_TRANSFORMS = ["box_cox", "johnson"]


def fitted_anderson_darling(data, distribution):
    """Unadjusted AD against the actual fitted CDF; no calibrated p-value.

    Critical values depend on family and parameter estimation. This score alone
    is not a significance test and does not establish a native-product match.
    """
    ordered = np.sort(np.asarray(data, dtype=float))
    n = len(ordered)
    if not n:
        raise ValueError("Anderson-Darling requires observations.")
    with np.errstate(all='ignore'):
        value = -n - float(np.sum((2 * np.arange(1,n+1)-1) *
                     (distribution.logcdf(ordered) + distribution.logsf(ordered[::-1]))) / n)
    return max(0.0, value) if math.isfinite(value) else None


def _clean_values(values):
    clean=[]
    for value in values:
        if value is None:
            continue
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real) or not math.isfinite(value):
            raise ValueError("Capability observations must be finite numeric values or missing cells.")
        clean.append(float(value))
    return np.asarray(clean, dtype=float)


def fit_nonnormal_distribution(data, dist_name):
    """Fit a family and evaluate unadjusted AD using that family's fitted CDF."""
    clean = _clean_values(data)
    if len(clean) < 3:
        raise ValueError("Distribution fitting requires at least 3 valid observations.")
    if dist_name not in SUPPORTED_DISTRIBUTIONS:
        raise ValueError(f"Unsupported distribution: {dist_name}")
    if dist_name != "normal" and np.any(clean <= 0):
        raise ValueError(f"Selected distribution '{dist_name}' requires strictly positive observations.")
    if np.ptp(clean) == 0:
        raise ValueError("Distribution fitting requires variation in the observations.")
    if dist_name == "weibull":
        shape, _, scale = stats.weibull_min.fit(clean, floc=0)
        params = {"shape":float(shape), "scale":float(scale)}
        dist_obj = stats.weibull_min(shape, scale=scale)
    elif dist_name == "lognormal":
        shape, _, scale = stats.lognorm.fit(clean, floc=0)
        params = {"location_mu":float(np.log(scale)), "scale_sigma":float(shape)}
        dist_obj = stats.lognorm(shape, scale=scale)
    elif dist_name == "exponential":
        _, scale = stats.expon.fit(clean, floc=0)
        params = {"scale_mean":float(scale)}
        dist_obj = stats.expon(scale=scale)
    elif dist_name == "gamma":
        shape, _, scale = stats.gamma.fit(clean, floc=0)
        params = {"shape":float(shape), "scale":float(scale)}
        dist_obj = stats.gamma(shape, scale=scale)
    else:
        mean, stdev = stats.norm.fit(clean)
        params = {"mean":float(mean), "stdev":float(stdev)}
        dist_obj = stats.norm(loc=mean, scale=stdev)
    percentiles = list(map(float, dist_obj.ppf([.00135,.5,.99865])))
    if not all(math.isfinite(v) for v in list(params.values())+percentiles):
        raise ValueError("Fitted distribution parameters or percentiles exceed the supported numeric range.")
    return {"dist_name":dist_name, "parameters":params,
            "p_lower":percentiles[0], "p_median":percentiles[1], "p_upper":percentiles[2],
            "ad_stat":fitted_anderson_darling(clean, dist_obj),
            "ad_method":"Unadjusted fitted-CDF Anderson-Darling score",
            "p_value":None,
            "goodness_of_fit_note":"No calibrated p-value is available for this fitted-family score."}


def fit_box_cox_transformation(
    data: np.ndarray,
    user_lambda: Optional[float] = None
) -> Dict[str, Any]:
    """Fit optimal Box-Cox lambda or apply user-specified lambda."""
    clean = _clean_values(data)
    if np.any(clean <= 0):
        raise ValueError("Box-Cox transformation requires all observations to be strictly positive (> 0).")

    if len(clean) < 3 or np.ptp(clean) == 0:
        raise ValueError("Box-Cox transformation requires at least 3 observations with variation.")
    if user_lambda is not None:
        if isinstance(user_lambda, bool) or not isinstance(user_lambda, numbers.Real) or not math.isfinite(user_lambda):
            raise ValueError("Box-Cox lambda must be finite.")
        lam = float(user_lambda)
        if abs(lam) < 1e-6:
            transformed = np.log(clean)
        else:
            transformed = (clean**lam - 1.0) / lam
    else:
        transformed, lam = stats.boxcox(clean)
        lam = float(lam)

    if not np.all(np.isfinite(transformed)) or np.std(transformed, ddof=1) <= 0:
        raise ValueError("Transformed observations must be finite and have variation.")

    # Transform function
    def transform_val(x: float) -> float:
        if x <= 0:
            return float('nan')
        return math.log(x) if abs(lam) < 1e-6 else (x**lam - 1.0) / lam

    return {
        "lambda": lam,
        "transformed": transformed.tolist(),
        "mean_trans": float(np.mean(transformed)),
        "std_trans": float(np.std(transformed, ddof=1)),
    }


def compute_nonnormal_indices(
    p_lower: float,
    p_median: float,
    p_upper: float,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    tolerance_k: float = 6.0,
    is_aiag_vda: bool = False
) -> Dict[str, Optional[float]]:
    """Calculates nonnormal capability indices (Pp, PPL, PPU, Ppk / Cnp, Cnpl, Cnpu, Cnpk)."""
    spread = p_upper - p_lower
    half_upper = p_upper - p_median
    half_lower = p_median - p_lower

    pp: Optional[float] = None
    ppl: Optional[float] = None
    ppu: Optional[float] = None
    ppk: Optional[float] = None

    if lsl is not None and usl is not None:
        if spread > 0:
            pp = float((usl - lsl) / spread)
    if usl is not None and half_upper > 0:
        ppu = float((usl - p_median) / half_upper)
    if lsl is not None and half_lower > 0:
        ppl = float((p_median - lsl) / half_lower)

    if ppu is not None and ppl is not None:
        ppk = min(ppu, ppl)
    elif ppu is not None:
        ppk = ppu
    elif ppl is not None:
        ppk = ppl

    res = {
        "pp": pp,
        "ppl": ppl,
        "ppu": ppu,
        "ppk": ppk,
    }

    if is_aiag_vda:
        res.update({
            "cnp": pp,
            "cnpl": ppl,
            "cnpu": ppu,
            "cnpk": ppk,
        })

    return res


def run_nonnormal_capability(
    values: List[Union[float, None]],
    dist_or_transform: str = "weibull",
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    tolerance_k: float = 6.0,
    box_cox_lambda: Optional[float] = None,
    naming_convention: str = "classical",
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    """Original fitted-family percentile capability estimates; native parity unverified."""
    arr = _clean_values(values)
    n_total = len(arr)
    if n_total < 3:
        raise ValueError("Nonnormal Capability Analysis requires at least 3 valid observations.")
    for key, value in [('LSL',lsl),('USL',usl),('Target',target)]:
        if value is not None and (isinstance(value,bool) or not isinstance(value,numbers.Real) or not math.isfinite(value)):
            raise ValueError(f"{key} must be finite.")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL must be less than USL.")
    if isinstance(tolerance_k,bool) or not isinstance(tolerance_k,numbers.Real) or not math.isfinite(tolerance_k) or tolerance_k <= 0:
        raise ValueError("Tolerance multiplier must be positive and finite.")
    if isinstance(confidence_level,bool) or not isinstance(confidence_level,numbers.Real) or not math.isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise ValueError("Confidence level must be strictly between 0 and 1.")
    if lsl is None and usl is None:
        raise ValueError("At least one specification limit (LSL or USL) must be provided.")

    is_aiag_vda = (naming_convention.lower() in ("aiag_vda", "unified"))
    fit_info: Dict[str, Any] = {}
    p_lower: float = 0.0
    p_median: float = 0.0
    p_upper: float = 0.0

    exp_below: float = 0.0
    exp_above: float = 0.0

    if dist_or_transform in SUPPORTED_DISTRIBUTIONS:
        fit_res = fit_nonnormal_distribution(arr, dist_or_transform)
        fit_info = fit_res
        p_lower = fit_res["p_lower"]
        p_median = fit_res["p_median"]
        p_upper = fit_res["p_upper"]

        params = fit_res["parameters"]
        if dist_or_transform == "weibull":
            dist_obj = stats.weibull_min(params["shape"], scale=params["scale"])
        elif dist_or_transform == "lognormal":
            dist_obj = stats.lognorm(params["scale_sigma"], scale=math.exp(params["location_mu"]))
        elif dist_or_transform == "exponential":
            dist_obj = stats.expon(scale=params["scale_mean"])
        elif dist_or_transform == "gamma":
            dist_obj = stats.gamma(params["shape"], scale=params["scale"])
        elif dist_or_transform == "normal":
            dist_obj = stats.norm(loc=params["mean"], scale=params["stdev"])

        if lsl is not None:
            exp_below = float(dist_obj.cdf(lsl)) * 1e6
        if usl is not None:
            exp_above = float(dist_obj.sf(usl)) * 1e6

    elif dist_or_transform == "box_cox":
        if any(limit is not None and limit <= 0 for limit in (lsl,usl)):
            raise ValueError("Box-Cox capability requires positive specification limits.")
        bc = fit_box_cox_transformation(arr, user_lambda=box_cox_lambda)
        fit_info = bc
        fit_info['ad_stat'] = fitted_anderson_darling(bc['transformed'],stats.norm(loc=bc['mean_trans'],scale=bc['std_trans']))
        fit_info['ad_method'] = 'Unadjusted fitted-normal AD score in transformed space'
        fit_info['p_value'] = None
        fit_info['goodness_of_fit_note'] = 'Box-Cox lambda was estimated; no calibrated p-value is available.'
        mu = bc["mean_trans"]
        sigma = bc["std_trans"]
        lam = bc["lambda"]

        def _t(x):
            if x is None:
                return None
            if x <= 0:
                return float("-inf")
            return math.log(x) if abs(lam) < 1e-6 else (x**lam - 1.0) / lam

        lsl_t = _t(lsl)
        usl_t = _t(usl)

        # Standard normal percentiles mapped back
        p_lower = mu - 3.0 * sigma
        p_median = mu
        p_upper = mu + 3.0 * sigma

        # Expected PPM from standard normal in transformed space
        if lsl_t is not None:
            exp_below = float(stats.norm.cdf(lsl_t, loc=mu, scale=sigma)) * 1e6
        if usl_t is not None:
            exp_above = float(stats.norm.sf(usl_t, loc=mu, scale=sigma)) * 1e6

        indices = compute_nonnormal_indices(
            p_lower=p_lower,
            p_median=p_median,
            p_upper=p_upper,
            lsl=lsl_t,
            usl=usl_t,
            tolerance_k=tolerance_k,
            is_aiag_vda=is_aiag_vda
        )
    else:
        raise ValueError(f"Unknown distribution or transformation: {dist_or_transform}")

    if dist_or_transform != "box_cox":
        indices = compute_nonnormal_indices(
            p_lower=p_lower,
            p_median=p_median,
            p_upper=p_upper,
            lsl=lsl,
            usl=usl,
            tolerance_k=tolerance_k,
            is_aiag_vda=is_aiag_vda
        )

    exp_total = exp_below + exp_above

    # Observed performance in sample
    obs_below = float(np.sum(arr < lsl) / n_total * 1e6) if lsl is not None else 0.0
    obs_above = float(np.sum(arr > usl) / n_total * 1e6) if usl is not None else 0.0
    obs_total = obs_below + obs_above

    # Inverse survival avoids loss of tiny upper tails in 1-p subtraction.
    # Unbounded endpoints are explicit missing numeric values for strict JSON.
    def benchmark_z(probability):
        probability=min(1.0,max(0.0,float(probability)))
        return float(stats.norm.isf(probability)) if 0<probability<1 else None
    z_bench = benchmark_z(exp_total / 1e6)
    z_lsl = benchmark_z(exp_below / 1e6) if lsl is not None else None
    z_usl = benchmark_z(exp_above / 1e6) if usl is not None else None

    return {
        "analysis": "capability_nonnormal",
        "method": dist_or_transform,
        "n_total": n_total,
        "lsl": lsl,
        "usl": usl,
        "target": target,
        "tolerance_k": tolerance_k,
        "naming_convention": "aiag_vda" if is_aiag_vda else "classical",
        "fit_info": fit_info,
        "p_lower": p_lower,
        "p_median": p_median,
        "p_upper": p_upper,
        "indices": indices,
        "expected_ppm": {
            "below": exp_below,
            "above": exp_above,
            "total": exp_total,
        },
        "observed_ppm": {
            "below": obs_below,
            "above": obs_above,
            "total": obs_total,
        },
        "benchmark_z": {
            "z_bench": z_bench,
            "z_lsl": z_lsl,
            "z_usl": z_usl,
        },
        "observations": arr.tolist(),
    }
