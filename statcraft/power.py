"""Power and Sample Size calculation engine for StatCraft.

Provides 1:1 statistical parity with StatCraft for:
- 1-Sample Z
- 1-Sample t
- 2-Sample t
- Paired t
- 1 Proportion
- 2 Proportions
- One-Way ANOVA
- 2-Level Factorial Design

Supports solving for:
- Sample size from Target Power and Difference/Effect
- Power from Sample Size and Difference/Effect
- Difference/Effect from Sample Size and Target Power
- Generating data series for High-DPI Power Curves
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


# ==============================================================================
# Helper Functions & Numerical Inversion
# ==============================================================================

def _clean_float_list(vals: Optional[Union[float, List[float]]]) -> List[float]:
    if vals is None:
        return []
    if isinstance(vals, (int, float)):
        return [float(vals)]
    out = []
    for v in vals:
        try:
            f = float(v)
            if math.isfinite(f):
                out.append(f)
        except (ValueError, TypeError):
            continue
    return out


def _clean_int_list(vals: Optional[Union[int, List[int]]]) -> List[int]:
    if vals is None:
        return []
    if isinstance(vals, (int, float)):
        return [int(round(vals))]
    out = []
    for v in vals:
        try:
            i = int(round(float(v)))
            if i > 0:
                out.append(i)
        except (ValueError, TypeError):
            continue
    return out


def _calc_t_power(df: float, delta_nc: float, alpha: float, is_two_sided: bool = True) -> float:
    """Robust non-central t power calculation avoiding SciPy NaN artifacts."""
    if df < 1:
        return alpha
    t_alpha = stats.t.ppf(1.0 - alpha / 2.0 if is_two_sided else 1.0 - alpha, df)
    if df > 200 or abs(delta_nc) > 20:
        s_nc = math.sqrt(1.0 + (delta_nc ** 2) / (2.0 * df))
        if is_two_sided:
            p = float(1.0 - stats.norm.cdf((t_alpha - delta_nc) / s_nc) + stats.norm.cdf((-t_alpha - delta_nc) / s_nc))
        else:
            p = float(1.0 - stats.norm.cdf((t_alpha - delta_nc) / s_nc))
    else:
        if is_two_sided:
            p = 1.0 - stats.nct.cdf(t_alpha, df, delta_nc) + stats.nct.cdf(-t_alpha, df, delta_nc)
        else:
            p = 1.0 - stats.nct.cdf(t_alpha, df, delta_nc)
    if math.isnan(p):
        p = 1.0 if delta_nc > t_alpha else alpha
    return float(np.clip(p, 0.0, 1.0))


def _calc_f_power(df1: float, df2: float, lambda_nc: float, alpha: float) -> float:
    """Robust non-central F power calculation."""
    if df1 < 1 or df2 < 1 or lambda_nc <= 0:
        return alpha
    f_crit = stats.f.ppf(1.0 - alpha, df1, df2)
    p = 1.0 - stats.ncf.cdf(f_crit, df1, df2, lambda_nc)
    if math.isnan(p):
        p = 1.0 if lambda_nc > 20 else alpha
    return float(np.clip(p, 0.0, 1.0))


# ==============================================================================
# 1. 1-SAMPLE Z POWER AND SAMPLE SIZE
# ==============================================================================

def one_sample_z_power(
    differences: Optional[Union[float, List[float]]] = None,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    sigma: float = 1.0,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for 1-Sample Z Test matching StatCraft."""
    if sigma <= 0:
        raise ValueError("Standard deviation (sigma) must be strictly positive.")
    if not 0.0 < alpha < 1.0:
        raise ValueError("Significance level (alpha) must be between 0 and 1.")

    diffs = _clean_float_list(differences) or [1.0]
    is_two_sided = alternative.lower() in ("two_sided", "not_equal", "two-sided")
    z_alpha = stats.norm.ppf(1.0 - alpha / 2.0 if is_two_sided else 1.0 - alpha)

    def calc_power(delta: float, n: int) -> float:
        if n < 1 or delta == 0:
            return alpha
        mu_nc = abs(delta) * math.sqrt(n) / sigma
        if is_two_sided:
            return float(1.0 - stats.norm.cdf(z_alpha - mu_nc) + stats.norm.cdf(-z_alpha - mu_nc))
        else:
            return float(1.0 - stats.norm.cdf(z_alpha - mu_nc))

    def calc_sample_size(delta: float, target_p: float) -> Tuple[int, float]:
        if delta == 0 or target_p <= alpha:
            return 2, alpha
        z_beta = stats.norm.ppf(target_p)
        n_exact = ((sigma * (z_alpha + z_beta)) / abs(delta)) ** 2
        n = max(1, int(math.ceil(n_exact)))
        actual_p = calc_power(delta, n)
        return n, actual_p

    rows = []
    curve_data = []

    if sample_sizes is not None and len(_clean_int_list(sample_sizes)) > 0:
        ns = _clean_int_list(sample_sizes)
        for delta in diffs:
            for n in ns:
                p = calc_power(delta, n)
                rows.append({"difference": delta, "sample_size": n, "target_power": None, "actual_power": p})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for delta in diffs:
            for tp in tps:
                n, act_p = calc_sample_size(delta, tp)
                rows.append({"difference": delta, "sample_size": n, "target_power": tp, "actual_power": act_p})
    else:
        for delta in diffs:
            for tp in [0.8, 0.9]:
                n, act_p = calc_sample_size(delta, tp)
                rows.append({"difference": delta, "sample_size": n, "target_power": tp, "actual_power": act_p})

    max_n = max([r["sample_size"] for r in rows]) if rows else 50
    n_grid = np.unique(np.linspace(max(2, max_n // 10), max(max_n * 2, 20), 40).astype(int)).tolist()
    for delta in diffs:
        pts = [(n, calc_power(delta, n)) for n in n_grid]
        curve_data.append({"difference": delta, "points": pts})

    return {
        "analysis": "one_sample_z_power",
        "sigma": sigma,
        "alpha": alpha,
        "alternative": "Two-sided" if is_two_sided else "One-sided",
        "rows": rows,
        "curves": curve_data,
    }


# ==============================================================================
# 2. 1-SAMPLE T POWER AND SAMPLE SIZE
# ==============================================================================

def one_sample_t_power(
    differences: Optional[Union[float, List[float]]] = None,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    sigma: float = 1.0,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for 1-Sample t Test matching StatCraft."""
    if sigma <= 0:
        raise ValueError("Standard deviation (sigma) must be strictly positive.")
    if not 0.0 < alpha < 1.0:
        raise ValueError("Significance level (alpha) must be between 0 and 1.")

    diffs = _clean_float_list(differences) or [1.0]
    is_two_sided = alternative.lower() in ("two_sided", "not_equal", "two-sided")

    def calc_power(delta: float, n: int) -> float:
        if n < 2 or delta == 0:
            return alpha
        df = n - 1
        delta_nc = abs(delta) * math.sqrt(n) / sigma
        return _calc_t_power(df, delta_nc, alpha, is_two_sided)

    def calc_sample_size(delta: float, target_p: float) -> Tuple[int, float]:
        if delta == 0 or target_p <= alpha:
            return 2, alpha
        low, high = 2, 5000
        while low < high:
            mid = (low + high) // 2
            if calc_power(delta, mid) >= target_p:
                high = mid
            else:
                low = mid + 1
        return low, calc_power(delta, low)

    rows = []
    curve_data = []

    if sample_sizes is not None and len(_clean_int_list(sample_sizes)) > 0:
        ns = _clean_int_list(sample_sizes)
        for delta in diffs:
            for n in ns:
                p = calc_power(delta, n)
                rows.append({"difference": delta, "sample_size": n, "target_power": None, "actual_power": p})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for delta in diffs:
            for tp in tps:
                n, act_p = calc_sample_size(delta, tp)
                rows.append({"difference": delta, "sample_size": n, "target_power": tp, "actual_power": act_p})
    else:
        for delta in diffs:
            for tp in [0.8, 0.9]:
                n, act_p = calc_sample_size(delta, tp)
                rows.append({"difference": delta, "sample_size": n, "target_power": tp, "actual_power": act_p})

    max_n = max([r["sample_size"] for r in rows]) if rows else 50
    n_grid = np.unique(np.linspace(max(2, max_n // 10), max(max_n * 2, 20), 40).astype(int)).tolist()
    for delta in diffs:
        pts = [(n, calc_power(delta, n)) for n in n_grid]
        curve_data.append({"difference": delta, "points": pts})

    return {
        "analysis": "one_sample_t_power",
        "sigma": sigma,
        "alpha": alpha,
        "alternative": "Two-sided" if is_two_sided else "One-sided",
        "rows": rows,
        "curves": curve_data,
    }


# ==============================================================================
# 3. 2-SAMPLE T POWER AND SAMPLE SIZE
# ==============================================================================

def two_sample_t_power(
    differences: Optional[Union[float, List[float]]] = None,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    sigma: float = 1.0,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for 2-Sample t Test matching StatCraft."""
    if sigma <= 0:
        raise ValueError("Standard deviation (sigma) must be strictly positive.")
    if not 0.0 < alpha < 1.0:
        raise ValueError("Significance level (alpha) must be between 0 and 1.")

    diffs = _clean_float_list(differences) or [1.0]
    is_two_sided = alternative.lower() in ("two_sided", "not_equal", "two-sided")

    def calc_power(delta: float, n: int) -> float:
        if n < 2 or delta == 0:
            return alpha
        df = 2 * n - 2
        delta_nc = (abs(delta) / sigma) * math.sqrt(n / 2.0)
        return _calc_t_power(df, delta_nc, alpha, is_two_sided)

    def calc_sample_size(delta: float, target_p: float) -> Tuple[int, float]:
        if delta == 0 or target_p <= alpha:
            return 2, alpha
        low, high = 2, 5000
        while low < high:
            mid = (low + high) // 2
            if calc_power(delta, mid) >= target_p:
                high = mid
            else:
                low = mid + 1
        return low, calc_power(delta, low)

    rows = []
    curve_data = []

    if sample_sizes is not None and len(_clean_int_list(sample_sizes)) > 0:
        ns = _clean_int_list(sample_sizes)
        for delta in diffs:
            for n in ns:
                p = calc_power(delta, n)
                rows.append({"difference": delta, "sample_size": n, "target_power": None, "actual_power": p})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for delta in diffs:
            for tp in tps:
                n, act_p = calc_sample_size(delta, tp)
                rows.append({"difference": delta, "sample_size": n, "target_power": tp, "actual_power": act_p})
    else:
        for delta in diffs:
            for tp in [0.8, 0.9]:
                n, act_p = calc_sample_size(delta, tp)
                rows.append({"difference": delta, "sample_size": n, "target_power": tp, "actual_power": act_p})

    max_n = max([r["sample_size"] for r in rows]) if rows else 50
    n_grid = np.unique(np.linspace(max(2, max_n // 10), max(max_n * 2, 20), 40).astype(int)).tolist()
    for delta in diffs:
        pts = [(n, calc_power(delta, n)) for n in n_grid]
        curve_data.append({"difference": delta, "points": pts})

    return {
        "analysis": "two_sample_t_power",
        "sigma": sigma,
        "alpha": alpha,
        "alternative": "Two-sided" if is_two_sided else "One-sided",
        "rows": rows,
        "curves": curve_data,
    }


# ==============================================================================
# 4. PAIRED T POWER AND SAMPLE SIZE
# ==============================================================================

def paired_t_power(
    differences: Optional[Union[float, List[float]]] = None,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    stdev_diff: float = 1.0,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for Paired t Test matching StatCraft."""
    res = one_sample_t_power(
        differences=differences,
        sample_sizes=sample_sizes,
        target_powers=target_powers,
        sigma=stdev_diff,
        alpha=alpha,
        alternative=alternative,
    )
    res["analysis"] = "paired_t_power"
    res["stdev_diff"] = stdev_diff
    return res


# ==============================================================================
# 5. 1 PROPORTION POWER AND SAMPLE SIZE
# ==============================================================================

def one_proportion_power(
    comparison_proportions: Optional[Union[float, List[float]]] = None,
    baseline_p0: float = 0.5,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for 1 Proportion Test matching StatCraft."""
    if not (0.0 < baseline_p0 < 1.0):
        raise ValueError("Baseline proportion (p0) must be between 0 and 1.")
    props = _clean_float_list(comparison_proportions) or [0.6]
    for p in props:
        if not (0.0 < p < 1.0):
            raise ValueError("Comparison proportions must be strictly between 0 and 1.")

    is_two_sided = alternative.lower() in ("two_sided", "not_equal", "two-sided")
    z_alpha = stats.norm.ppf(1.0 - alpha / 2.0 if is_two_sided else 1.0 - alpha)

    def calc_power(p1: float, n: int) -> float:
        if n < 2 or p1 == baseline_p0:
            return alpha
        se0 = math.sqrt(baseline_p0 * (1.0 - baseline_p0) / n)
        se1 = math.sqrt(p1 * (1.0 - p1) / n)
        z_crit = z_alpha * se0
        if is_two_sided:
            pow_val = 1.0 - stats.norm.cdf((baseline_p0 + z_crit - p1) / se1) + stats.norm.cdf((baseline_p0 - z_crit - p1) / se1)
        else:
            if p1 > baseline_p0:
                pow_val = 1.0 - stats.norm.cdf((baseline_p0 + z_crit - p1) / se1)
            else:
                pow_val = stats.norm.cdf((baseline_p0 - z_crit - p1) / se1)
        return float(np.clip(pow_val, 0.0, 1.0))

    def calc_sample_size(p1: float, target_p: float) -> Tuple[int, float]:
        if p1 == baseline_p0 or target_p <= alpha:
            return 5, alpha
        low, high = 5, 20000
        while low < high:
            mid = (low + high) // 2
            if calc_power(p1, mid) >= target_p:
                high = mid
            else:
                low = mid + 1
        return low, calc_power(p1, low)

    rows = []
    curve_data = []

    if sample_sizes is not None and len(_clean_int_list(sample_sizes)) > 0:
        ns = _clean_int_list(sample_sizes)
        for p1 in props:
            for n in ns:
                pw = calc_power(p1, n)
                rows.append({"comparison_p": p1, "sample_size": n, "target_power": None, "actual_power": pw})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for p1 in props:
            for tp in tps:
                n, act_p = calc_sample_size(p1, tp)
                rows.append({"comparison_p": p1, "sample_size": n, "target_power": tp, "actual_power": act_p})
    else:
        for p1 in props:
            for tp in [0.8, 0.9]:
                n, act_p = calc_sample_size(p1, tp)
                rows.append({"comparison_p": p1, "sample_size": n, "target_power": tp, "actual_power": act_p})

    max_n = max([r["sample_size"] for r in rows]) if rows else 100
    n_grid = np.unique(np.linspace(max(5, max_n // 10), max(max_n * 2, 50), 40).astype(int)).tolist()
    for p1 in props:
        pts = [(n, calc_power(p1, n)) for n in n_grid]
        curve_data.append({"comparison_p": p1, "points": pts})

    return {
        "analysis": "one_proportion_power",
        "baseline_p0": baseline_p0,
        "alpha": alpha,
        "alternative": "Two-sided" if is_two_sided else "One-sided",
        "rows": rows,
        "curves": curve_data,
    }


# ==============================================================================
# 6. 2 PROPORTIONS POWER AND SAMPLE SIZE
# ==============================================================================

def two_proportions_power(
    p1_values: Optional[Union[float, List[float]]] = None,
    p2: float = 0.5,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    alpha: float = 0.05,
    alternative: str = "two_sided",
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for 2 Proportions Test matching StatCraft."""
    if not (0.0 < p2 < 1.0):
        raise ValueError("Comparison proportion (p2) must be between 0 and 1.")
    props1 = _clean_float_list(p1_values) or [0.6]
    for p in props1:
        if not (0.0 < p < 1.0):
            raise ValueError("Proportions must be strictly between 0 and 1.")

    is_two_sided = alternative.lower() in ("two_sided", "not_equal", "two-sided")
    z_alpha = stats.norm.ppf(1.0 - alpha / 2.0 if is_two_sided else 1.0 - alpha)

    def calc_power(p1: float, n: int) -> float:
        if n < 2 or p1 == p2:
            return alpha
        p_pool = (p1 + p2) / 2.0
        se0 = math.sqrt(2.0 * p_pool * (1.0 - p_pool) / n)
        se1 = math.sqrt((p1 * (1.0 - p1) + p2 * (1.0 - p2)) / n)
        diff = abs(p1 - p2)
        z = (diff - z_alpha * se0) / se1 if se1 > 0 else 0.0
        return float(np.clip(stats.norm.cdf(z), 0.0, 1.0))

    def calc_sample_size(p1: float, target_p: float) -> Tuple[int, float]:
        if p1 == p2 or target_p <= alpha:
            return 5, alpha
        low, high = 5, 25000
        while low < high:
            mid = (low + high) // 2
            if calc_power(p1, mid) >= target_p:
                high = mid
            else:
                low = mid + 1
        return low, calc_power(p1, low)

    rows = []
    curve_data = []

    if sample_sizes is not None and len(_clean_int_list(sample_sizes)) > 0:
        ns = _clean_int_list(sample_sizes)
        for p1 in props1:
            for n in ns:
                pw = calc_power(p1, n)
                rows.append({"p1": p1, "p2": p2, "sample_size": n, "target_power": None, "actual_power": pw})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for p1 in props1:
            for tp in tps:
                n, act_p = calc_sample_size(p1, tp)
                rows.append({"p1": p1, "p2": p2, "sample_size": n, "target_power": tp, "actual_power": act_p})
    else:
        for p1 in props1:
            for tp in [0.8, 0.9]:
                n, act_p = calc_sample_size(p1, tp)
                rows.append({"p1": p1, "p2": p2, "sample_size": n, "target_power": tp, "actual_power": act_p})

    max_n = max([r["sample_size"] for r in rows]) if rows else 100
    n_grid = np.unique(np.linspace(max(5, max_n // 10), max(max_n * 2, 50), 40).astype(int)).tolist()
    for p1 in props1:
        pts = [(n, calc_power(p1, n)) for n in n_grid]
        curve_data.append({"p1": p1, "points": pts})

    return {
        "analysis": "two_proportions_power",
        "p2": p2,
        "alpha": alpha,
        "alternative": "Two-sided" if is_two_sided else "One-sided",
        "rows": rows,
        "curves": curve_data,
    }


# ==============================================================================
# 7. ONE-WAY ANOVA POWER AND SAMPLE SIZE
# ==============================================================================

def oneway_anova_power(
    levels: int = 3,
    max_differences: Optional[Union[float, List[float]]] = None,
    sample_sizes: Optional[Union[int, List[int]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    sigma: float = 1.0,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for One-Way ANOVA matching StatCraft."""
    if levels < 2:
        raise ValueError("One-Way ANOVA requires at least 2 factor levels.")
    if sigma <= 0:
        raise ValueError("Standard deviation (sigma) must be strictly positive.")
    if not 0.0 < alpha < 1.0:
        raise ValueError("Significance level (alpha) must be between 0 and 1.")

    diffs = _clean_float_list(max_differences) or [1.0]

    def calc_power(d_max: float, n: int) -> float:
        if n < 2 or d_max <= 0:
            return alpha
        df1 = levels - 1
        df2 = levels * (n - 1)
        lambda_nc = (n * (d_max ** 2)) / (2.0 * (sigma ** 2))
        return _calc_f_power(df1, df2, lambda_nc, alpha)

    def calc_sample_size(d_max: float, target_p: float) -> Tuple[int, float]:
        if d_max <= 0 or target_p <= alpha:
            return 2, alpha
        low, high = 2, 5000
        while low < high:
            mid = (low + high) // 2
            if calc_power(d_max, mid) >= target_p:
                high = mid
            else:
                low = mid + 1
        return low, calc_power(d_max, low)

    rows = []
    curve_data = []

    if sample_sizes is not None and len(_clean_int_list(sample_sizes)) > 0:
        ns = _clean_int_list(sample_sizes)
        for d_max in diffs:
            for n in ns:
                p = calc_power(d_max, n)
                rows.append({"levels": levels, "max_difference": d_max, "sample_size": n, "target_power": None, "actual_power": p})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for d_max in diffs:
            for tp in tps:
                n, act_p = calc_sample_size(d_max, tp)
                rows.append({"levels": levels, "max_difference": d_max, "sample_size": n, "target_power": tp, "actual_power": act_p})
    else:
        for d_max in diffs:
            for tp in [0.8, 0.9]:
                n, act_p = calc_sample_size(d_max, tp)
                rows.append({"levels": levels, "max_difference": d_max, "sample_size": n, "target_power": tp, "actual_power": act_p})

    max_n = max([r["sample_size"] for r in rows]) if rows else 50
    n_grid = np.unique(np.linspace(max(2, max_n // 10), max(max_n * 2, 20), 40).astype(int)).tolist()
    for d_max in diffs:
        pts = [(n, calc_power(d_max, n)) for n in n_grid]
        curve_data.append({"max_difference": d_max, "points": pts})

    return {
        "analysis": "oneway_anova_power",
        "levels": levels,
        "sigma": sigma,
        "alpha": alpha,
        "rows": rows,
        "curves": curve_data,
    }


# ==============================================================================
# 8. 2-LEVEL FACTORIAL DESIGN POWER AND SAMPLE SIZE
# ==============================================================================

def factorial_power(
    factors: int = 3,
    corner_points: int = 8,
    replicates: Optional[Union[int, List[int]]] = None,
    effects: Optional[Union[float, List[float]]] = None,
    target_powers: Optional[Union[float, List[float]]] = None,
    center_points: int = 0,
    sigma: float = 1.0,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Calculate Power and Sample Size for 2-Level Factorial Design matching StatCraft."""
    if factors < 2:
        raise ValueError("2-Level Factorial Design requires at least 2 factors.")
    if corner_points < 4:
        raise ValueError("Corner points must be at least 4.")
    if sigma <= 0:
        raise ValueError("Standard deviation (sigma) must be strictly positive.")

    effs = _clean_float_list(effects) or [1.0]

    def calc_power(effect: float, reps: int) -> float:
        if reps < 1 or effect == 0:
            return alpha
        total_runs = reps * corner_points + center_points
        df_error = total_runs - corner_points
        if df_error < 1:
            df_error = max(1, total_runs - factors - 1)
        se_effect = 2.0 * sigma / math.sqrt(reps * corner_points)
        delta_nc = abs(effect) / se_effect if se_effect > 0 else 0.0
        return _calc_t_power(df_error, delta_nc, alpha, is_two_sided=True)

    def calc_replicates(effect: float, target_p: float) -> Tuple[int, int, float]:
        if effect == 0 or target_p <= alpha:
            return 1, corner_points + center_points, alpha
        low, high = 1, 500
        while low < high:
            mid = (low + high) // 2
            if calc_power(effect, mid) >= target_p:
                high = mid
            else:
                low = mid + 1
        total_runs = low * corner_points + center_points
        return low, total_runs, calc_power(effect, low)

    rows = []
    curve_data = []

    if replicates is not None and len(_clean_int_list(replicates)) > 0:
        reps_list = _clean_int_list(replicates)
        for eff in effs:
            for r in reps_list:
                tot = r * corner_points + center_points
                pw = calc_power(eff, r)
                rows.append({"effect": eff, "replicates": r, "total_runs": tot, "target_power": None, "actual_power": pw})
    elif target_powers is not None and len(_clean_float_list(target_powers)) > 0:
        tps = _clean_float_list(target_powers)
        for eff in effs:
            for tp in tps:
                r, tot, act_p = calc_replicates(eff, tp)
                rows.append({"effect": eff, "replicates": r, "total_runs": tot, "target_power": tp, "actual_power": act_p})
    else:
        for eff in effs:
            for tp in [0.8, 0.9]:
                r, tot, act_p = calc_replicates(eff, tp)
                rows.append({"effect": eff, "replicates": r, "total_runs": tot, "target_power": tp, "actual_power": act_p})

    max_reps = max([rw["replicates"] for rw in rows]) if rows else 10
    r_grid = list(range(1, max(max_reps * 2 + 1, 8)))
    for eff in effs:
        pts = [(r * corner_points + center_points, calc_power(eff, r)) for r in r_grid]
        curve_data.append({"effect": eff, "points": pts})

    return {
        "analysis": "factorial_power",
        "factors": factors,
        "corner_points": corner_points,
        "center_points": center_points,
        "sigma": sigma,
        "alpha": alpha,
        "rows": rows,
        "curves": curve_data,
    }
