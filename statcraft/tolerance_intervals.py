"""Computational engine for Tolerance Intervals (Normal Distribution).

Matches StatCraft statistical formulas:
- Exact one-sided tolerance factor via noncentral Student's t distribution.
- Two-sided tolerance factor via Howe's method with high-accuracy chi-square and normal quantiles.
- Nonparametric tolerance interval with exact binomial coverage probability for raw data.
- Supports both raw column samples and summarized data (sample size, mean, standard deviation).
"""
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


DEFAULT_SETTINGS = {
    'conf_level': 95.0,        # Confidence level (1 - alpha), e.g. 95.0%
    'min_percent': 95.0,       # Minimum percentage of population in interval (coverage p), e.g. 95.0%
    'interval_type': 'two_sided', # 'two_sided', 'lower', or 'upper'
    'show_graphs': True,       # Generate visual tolerance interval plot
    'title': '',               # Optional custom graph title
}


def compute_k_factor(n: int, conf_level: float = 95.0, min_percent: float = 95.0, interval_type: str = 'two_sided') -> float:
    """Compute parametric normal tolerance factor k."""
    if n < 2:
        raise ValueError("Sample size must be at least 2 to compute tolerance intervals.")

    alpha = 1.0 - (conf_level / 100.0)
    p = min_percent / 100.0
    df = n - 1

    if interval_type in ('lower', 'upper'):
        # One-sided tolerance factor k1:
        # k1 = t_{n-1, 1-alpha}(delta) / sqrt(n), delta = sqrt(n) * z_p
        z_p = stats.norm.ppf(p)
        delta = math.sqrt(n) * z_p
        k = float(stats.nct.ppf(1.0 - alpha, df=df, nc=delta) / math.sqrt(n))
        return k
    else:
        # Two-sided tolerance factor k2 via Howe's method (standard in StatCraft / ISO 16269-6)
        z = stats.norm.ppf((1.0 + p) / 2.0)
        chi2_alpha = stats.chi2.ppf(alpha, df=df)
        u = math.sqrt(1.0 + 1.0 / n)
        w = math.sqrt(df / chi2_alpha)
        correction = math.sqrt(1.0 + (df - 2.0 - chi2_alpha) / (2.0 * (n + 1.0)**2))
        k2 = u * z * w * correction
        return float(k2)


def compute_tolerance_interval(
    raw_data: Optional[List[float]] = None,
    n: Optional[int] = None,
    mean: Optional[float] = None,
    std: Optional[float] = None,
    settings: Optional[Dict[str, Any]] = None,
    variable_name: str = "Sample",
) -> Dict[str, Any]:
    """Calculate normal and nonparametric tolerance intervals.

    Parameters
    ----------
    raw_data : list of float, optional
        Raw observations.
    n : int, optional
        Sample size (used if raw_data not provided).
    mean : float, optional
        Sample mean (used if raw_data not provided).
    std : float, optional
        Sample standard deviation (used if raw_data not provided).
    settings : dict, optional
        Analysis options.
    variable_name : str, optional
        Label for reporting.

    Returns
    -------
    dict
        Analysis results and interval boundaries.
    """
    opts = dict(DEFAULT_SETTINGS)
    if settings:
        opts.update(settings)

    conf_level = float(opts.get('conf_level', 95.0))
    if not (0.0 < conf_level < 100.0):
        raise ValueError("Confidence level must be strictly between 0 and 100.")

    min_percent = float(opts.get('min_percent', 95.0))
    if not (0.0 < min_percent < 100.0):
        raise ValueError("Minimum percentage of population must be strictly between 0 and 100.")

    interval_type = str(opts.get('interval_type', 'two_sided')).lower()
    if interval_type not in ('two_sided', 'lower', 'upper'):
        raise ValueError(f"Unknown interval type: '{interval_type}'. Must be 'two_sided', 'lower', or 'upper'.")

    clean_raw: Optional[List[float]] = None
    if raw_data is not None:
        clean_raw = [float(v) for v in raw_data if v is not None and math.isfinite(float(v))]
        n_calc = len(clean_raw)
        if n_calc < 2:
            raise ValueError("At least 2 valid numeric observations are required.")
        mean_calc = float(np.mean(clean_raw))
        std_calc = float(np.std(clean_raw, ddof=1))
    else:
        if n is None or n < 2:
            raise ValueError("Sample size must be an integer >= 2.")
        if mean is None or not math.isfinite(float(mean)):
            raise ValueError("Sample mean must be a finite number.")
        if std is None or float(std) <= 0.0 or not math.isfinite(float(std)):
            raise ValueError("Sample standard deviation must be a positive finite number.")
        n_calc = int(n)
        mean_calc = float(mean)
        std_calc = float(std)

    if std_calc <= 0.0:
        raise ValueError("Sample standard deviation must be positive.")

    # 1. Parametric Normal Tolerance Interval
    k = compute_k_factor(n_calc, conf_level=conf_level, min_percent=min_percent, interval_type=interval_type)

    if interval_type == 'two_sided':
        norm_lower = mean_calc - k * std_calc
        norm_upper = mean_calc + k * std_calc
    elif interval_type == 'lower':
        norm_lower = mean_calc - k * std_calc
        norm_upper = float('inf')
    else:  # 'upper'
        norm_lower = float('-inf')
        norm_upper = mean_calc + k * std_calc

    # 2. Nonparametric Tolerance Interval (if raw observations are available)
    np_result: Optional[Dict[str, Any]] = None
    if clean_raw is not None:
        p_cov = min_percent / 100.0
        sorted_vals = sorted(clean_raw)
        if interval_type == 'two_sided':
            # Lowest and highest order statistics
            np_lower = sorted_vals[0]
            np_upper = sorted_vals[-1]
            # Achieved confidence = 1 - p^n - n * p^(n-1) * (1 - p)
            achieved_conf = (1.0 - (p_cov ** n_calc) - n_calc * (p_cov ** (n_calc - 1)) * (1.0 - p_cov)) * 100.0
            achieved_conf = max(0.0, min(100.0, achieved_conf))
        elif interval_type == 'lower':
            np_lower = sorted_vals[0]
            np_upper = float('inf')
            achieved_conf = max(0.0, min(100.0, (1.0 - (p_cov ** n_calc)) * 100.0))
        else:  # 'upper'
            np_lower = float('-inf')
            np_upper = sorted_vals[-1]
            achieved_conf = max(0.0, min(100.0, (1.0 - (p_cov ** n_calc)) * 100.0))

        np_result = {
            'lower': np_lower,
            'upper': np_upper,
            'achieved_confidence': achieved_conf,
        }

    return {
        'variable_name': variable_name,
        'is_summarized': clean_raw is None,
        'n': n_calc,
        'mean': mean_calc,
        'std': std_calc,
        'conf_level': conf_level,
        'min_percent': min_percent,
        'interval_type': interval_type,
        'k': k,
        'normal_lower': norm_lower,
        'normal_upper': norm_upper,
        'nonparametric': np_result,
        'raw_observations': clean_raw,
        'title': opts.get('title', ''),
        'show_graphs': opts.get('show_graphs', True),
    }
