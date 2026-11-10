"""Extended Minitab Power and Sample Size Calculators.

Covers:
- 1 Variance (Chi-Square)
- 2 Variances (F-test)
- 1-Sample Poisson Rate
- 2-Sample Poisson Rates
- Equivalence Tests (TOST: 1-Sample, 2-Sample, Paired)
- Sample Size for Estimation (Mean, Proportion, Poisson Rate)
- Sample Size for Tolerance Intervals (Normal)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np
from scipy import stats


def _binary_search_n(calc_power_fn, target_power: float, low: int = 2, high: int = 100000) -> tuple[int, float]:
    while low < high:
        mid = (low + high) // 2
        if calc_power_fn(mid) >= target_power:
            high = mid
        else:
            low = mid + 1
    return low, float(calc_power_fn(low))


def one_variance_power(
    ratio: float = 1.5,
    sample_size: Optional[int] = None,
    target_power: Optional[float] = 0.80,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """1-Variance Chi-square test power/sample size (ratio = sigma_1 / sigma_0)."""
    if ratio <= 0 or abs(ratio - 1.0) < 1e-12:
        raise ValueError("Ratio (StDev1 / StDev0) must be positive and not equal to 1.0.")
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be strictly between 0 and 1.")

    alt = alternative.strip().lower()
    r2 = float(ratio) ** 2

    def power_fn(n: int) -> float:
        df = max(1, n - 1)
        if alt in ("greater", "upper"):
            c_up = stats.chi2.ppf(1.0 - alpha, df)
            return float(1.0 - stats.chi2.cdf(c_up / r2, df))
        if alt in ("less", "lower"):
            c_lo = stats.chi2.ppf(alpha, df)
            return float(stats.chi2.cdf(c_lo / r2, df))
        c_lo = stats.chi2.ppf(alpha / 2.0, df)
        c_up = stats.chi2.ppf(1.0 - alpha / 2.0, df)
        return float(stats.chi2.cdf(c_lo / r2, df) + (1.0 - stats.chi2.cdf(c_up / r2, df)))

    if sample_size is not None and sample_size >= 2:
        n_res = int(sample_size)
        act_p = power_fn(n_res)
        tp = None
    else:
        tp = float(target_power or 0.80)
        if not alpha < tp < 1.0:
            raise ValueError("Target power must lie between alpha and 1.0.")
        n_res, act_p = _binary_search_n(power_fn, tp, 2, 50000)

    return {
        "analysis": "one_variance_power",
        "ratio": float(ratio),
        "sample_size": n_res,
        "target_power": tp,
        "actual_power": act_p,
        "alpha": float(alpha),
        "alternative": alt,
    }


def two_variances_power(
    ratio: float = 1.5,
    sample_size: Optional[int] = None,
    target_power: Optional[float] = 0.80,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """2-Variances F-test power/sample size (ratio = sigma_1 / sigma_2, equal n)."""
    if ratio <= 0 or abs(ratio - 1.0) < 1e-12:
        raise ValueError("Ratio (StDev1 / StDev2) must be positive and not equal to 1.0.")
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be strictly between 0 and 1.")

    alt = alternative.strip().lower()
    r2 = float(ratio) ** 2

    def power_fn(n: int) -> float:
        df = max(1, n - 1)
        if alt in ("greater", "upper"):
            f_up = stats.f.ppf(1.0 - alpha, df, df)
            return float(1.0 - stats.f.cdf(f_up / r2, df, df))
        if alt in ("less", "lower"):
            f_lo = stats.f.ppf(alpha, df, df)
            return float(stats.f.cdf(f_lo / r2, df, df))
        f_lo = stats.f.ppf(alpha / 2.0, df, df)
        f_up = stats.f.ppf(1.0 - alpha / 2.0, df, df)
        return float(stats.f.cdf(f_lo / r2, df, df) + (1.0 - stats.f.cdf(f_up / r2, df, df)))

    if sample_size is not None and sample_size >= 2:
        n_res = int(sample_size)
        act_p = power_fn(n_res)
        tp = None
    else:
        tp = float(target_power or 0.80)
        n_res, act_p = _binary_search_n(power_fn, tp, 2, 50000)

    return {
        "analysis": "two_variances_power",
        "ratio": float(ratio),
        "sample_size_per_group": n_res,
        "target_power": tp,
        "actual_power": act_p,
        "alpha": float(alpha),
        "alternative": alt,
    }


def one_poisson_rate_power(
    baseline_rate: float = 2.0,
    comparison_rate: float = 3.0,
    sample_size: Optional[int] = None,
    target_power: Optional[float] = 0.80,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """1-Sample Poisson Rate power/sample size using score/normal approximation."""
    if baseline_rate <= 0 or comparison_rate <= 0 or abs(comparison_rate - baseline_rate) < 1e-12:
        raise ValueError("Baseline and comparison rates must be positive and distinct.")
    alt = alternative.strip().lower()
    z_crit = stats.norm.ppf(1.0 - alpha / 2.0 if alt == "two_sided" else 1.0 - alpha)

    def power_fn(n: int) -> float:
        se0 = math.sqrt(baseline_rate / n)
        se1 = math.sqrt(comparison_rate / n)
        diff = abs(comparison_rate - baseline_rate)
        z = (diff - z_crit * se0) / se1
        return float(stats.norm.cdf(z))

    if sample_size is not None and sample_size >= 1:
        n_res = int(sample_size)
        act_p = power_fn(n_res)
        tp = None
    else:
        tp = float(target_power or 0.80)
        n_res, act_p = _binary_search_n(power_fn, tp, 1, 100000)

    return {
        "analysis": "one_poisson_rate_power",
        "baseline_rate": float(baseline_rate),
        "comparison_rate": float(comparison_rate),
        "sample_size": n_res,
        "target_power": tp,
        "actual_power": act_p,
        "alpha": float(alpha),
        "alternative": alt,
    }


def two_poisson_rates_power(
    rate1: float = 3.0,
    rate2: float = 2.0,
    sample_size: Optional[int] = None,
    target_power: Optional[float] = 0.80,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """2-Sample Poisson Rates power/sample size (equal sample sizes)."""
    if rate1 <= 0 or rate2 <= 0 or abs(rate1 - rate2) < 1e-12:
        raise ValueError("Rates must be positive and distinct.")
    alt = alternative.strip().lower()
    z_crit = stats.norm.ppf(1.0 - alpha / 2.0 if alt == "two_sided" else 1.0 - alpha)

    def power_fn(n: int) -> float:
        r_pool = 0.5 * (rate1 + rate2)
        se0 = math.sqrt(2.0 * r_pool / n)
        se1 = math.sqrt((rate1 + rate2) / n)
        z = (abs(rate1 - rate2) - z_crit * se0) / se1
        return float(stats.norm.cdf(z))

    if sample_size is not None and sample_size >= 1:
        n_res = int(sample_size)
        act_p = power_fn(n_res)
        tp = None
    else:
        tp = float(target_power or 0.80)
        n_res, act_p = _binary_search_n(power_fn, tp, 1, 100000)

    return {
        "analysis": "two_poisson_rates_power",
        "rate1": float(rate1),
        "rate2": float(rate2),
        "sample_size_per_group": n_res,
        "target_power": tp,
        "actual_power": act_p,
        "alpha": float(alpha),
        "alternative": alt,
    }


def equivalence_tost_power(
    design: str = "2-Sample",
    lower_limit: float = -1.0,
    upper_limit: float = 1.0,
    difference: float = 0.0,
    stdev: float = 1.0,
    sample_size: Optional[int] = None,
    target_power: Optional[float] = 0.80,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Power and sample size for Equivalence Tests (TOST 1-Sample, 2-Sample, Paired)."""
    if lower_limit >= upper_limit:
        raise ValueError("Lower equivalence limit must be strictly less than upper limit.")
    if not (lower_limit < difference < upper_limit):
        raise ValueError("Assumed true difference must fall strictly inside equivalence limits.")
    if stdev <= 0:
        raise ValueError("Standard deviation must be positive.")

    d_low = design.strip().lower()
    is_two = "2" in d_low

    def power_fn(n: int) -> float:
        df = 2 * n - 2 if is_two else max(1, n - 1)
        se = stdev * math.sqrt(2.0 / n) if is_two else stdev / math.sqrt(n)
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ncp_low = (difference - lower_limit) / se
        ncp_high = (upper_limit - difference) / se
        # Two one-sided t rejection region probability under noncentral t / normal approx with exact df
        p1 = float(1.0 - stats.t.cdf(t_crit - ncp_low, df))
        p2 = float(stats.t.cdf(-t_crit + ncp_high, df))
        return float(max(0.0, min(1.0, p1 + p2 - 1.0)))

    if sample_size is not None and sample_size >= 2:
        n_res = int(sample_size)
        act_p = power_fn(n_res)
        tp = None
    else:
        tp = float(target_power or 0.80)
        n_res, act_p = _binary_search_n(power_fn, tp, 3, 50000)

    return {
        "analysis": "equivalence_tost_power",
        "design": design,
        "lower_limit": float(lower_limit),
        "upper_limit": float(upper_limit),
        "difference": float(difference),
        "stdev": float(stdev),
        "sample_size": n_res,
        "target_power": tp,
        "actual_power": act_p,
        "alpha": float(alpha),
    }


def sample_size_estimation(
    parameter: str = "Mean (Normal)",
    planning_value: float = 1.0,
    margin_of_error: float = 0.2,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Calculate Sample Size for Estimation given margin of error and confidence level."""
    if margin_of_error <= 0:
        raise ValueError("Margin of error must be strictly positive.")
    if not 0.5 < confidence < 1.0:
        raise ValueError("Confidence level must be between 0.50 and 1.00.")

    z = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))
    p_low = parameter.strip().lower()
    if "proportion" in p_low:
        p = float(planning_value)
        if not 0.0 < p < 1.0:
            raise ValueError("Planning proportion must be strictly between 0 and 1.")
        n = int(math.ceil((z ** 2) * p * (1.0 - p) / (margin_of_error ** 2)))
    elif "poisson" in p_low:
        lam = float(planning_value)
        if lam <= 0:
            raise ValueError("Planning Poisson rate must be positive.")
        n = int(math.ceil((z ** 2) * lam / (margin_of_error ** 2)))
    else:
        sigma = float(planning_value)
        if sigma <= 0:
            raise ValueError("Planning standard deviation must be positive.")
        n = int(math.ceil((z * sigma / margin_of_error) ** 2))

    return {
        "analysis": "sample_size_estimation",
        "parameter": parameter,
        "planning_value": float(planning_value),
        "margin_of_error": float(margin_of_error),
        "confidence": float(confidence),
        "sample_size": max(2, n),
    }


def sample_size_tolerance_interval(
    coverage: float = 0.95,
    confidence: float = 0.95,
    margin_ratio: float = 1.25,
) -> Dict[str, Any]:
    """Sample Size for Normal Tolerance Intervals controlling two-sided k/k_inf precision."""
    if not (0.5 <= coverage < 1.0 and 0.5 <= confidence < 1.0):
        raise ValueError("Coverage and confidence must be between 0.50 and 1.00.")
    if margin_ratio <= 1.0:
        raise ValueError("Tolerance factor ratio (k / z_p) must exceed 1.0 (e.g., 1.15 or 1.25).")

    z_p = float(stats.norm.ppf((1.0 + coverage) / 2.0))
    # Approximate Howe-Guenther normal tolerance k(n, p, 1-alpha)
    def tol_k(n: int) -> float:
        df = n - 1
        chi_crit = float(stats.chi2.ppf(1.0 - confidence, df))
        return z_p * math.sqrt((1.0 + 1.0 / n) * df / max(chi_crit, 1e-12))

    n_req = 4
    while n_req < 50000 and tol_k(n_req) / z_p > margin_ratio:
        n_req += 1

    return {
        "analysis": "sample_size_tolerance_interval",
        "coverage": float(coverage),
        "confidence": float(confidence),
        "margin_ratio": float(margin_ratio),
        "asymptotic_z": z_p,
        "achieved_k": float(tol_k(n_req)),
        "sample_size": int(n_req),
    }


def format_power_extended_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    lines = [f"Power and Sample Size: {kind.replace('_', ' ').title()}", "─" * 56]
    for k, v in result.items():
        if k == "analysis":
            continue
        lbl = k.replace("_", " ").title()
        if isinstance(v, float):
            lines.append(f"  {lbl:<24}: {v:.6g}")
        else:
            lines.append(f"  {lbl:<24}: {v}")
    return "\n".join(lines)
