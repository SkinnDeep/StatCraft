"""Original unweighted summaries with a narrowly checked quartile convention.

Default unweighted DESCRIBE quartiles were checked against five controlled UI
reference cases: clamped (n+1)*p ranks and linear interpolation. Mean/SD/SE were
checked at their displayed precision in those cases. This does not establish
weighted/default-setting variants, bitwise rounding or whole-product parity.
"""
from __future__ import annotations

import math
from collections.abc import Iterable

from .engine import normalize_numeric


def _clamped_rank_quantile(ordered: list[float], probability: float) -> float:
    """Internal nonempty finite-data quantile for the observed summary route."""
    count = len(ordered)
    rank = min(float(count), max(1.0, (count + 1) * probability))
    lower_rank = math.floor(rank)
    fraction = rank - lower_rank
    lower = ordered[lower_rank - 1]
    if fraction == 0.0:
        return lower
    upper = ordered[lower_rank]
    # Weighted endpoints avoid overflow in upper-lower for opposite extremes.
    # This is original stable arithmetic, not a claim of native bitwise rounding.
    return math.fsum(((1.0 - fraction) * lower, fraction * upper))


def describe(values: Iterable[float | None]) -> dict:
    """Summarize finite observations using sample variance (denominator n-1).

    Missing entries are excluded and counted. One observation has undefined
    sample variance, standard deviation and standard error, represented by None.
    Q1/Q3 use ranks (n+1)*0.25 and (n+1)*0.75, clamped to [1,n], with linear
    interpolation. This is the controlled default unweighted DESCRIBE convention,
    not a universal percentile API. Confidence intervals are not supplied here.
    """
    clean = []
    missing = 0
    for value in values:
        normalized = normalize_numeric(value)
        if normalized is None:
            missing += 1
        else:
            clean.append(normalized)
    if not clean:
        raise ValueError("At least one nonmissing numeric observation is required.")
    count = len(clean)
    ordered = sorted(clean)
    mean = math.fsum(x / count for x in clean)
    warnings = []
    try:
        total = math.fsum(clean)
    except OverflowError:
        total = None
        warnings.append("The sum exceeds the supported numeric range.")
    stdev = variance = standard_error = None
    if count > 1:
        deviations = [x - mean for x in clean]
        scale = max(abs(x) for x in deviations)
        if not math.isfinite(scale):
            warnings.append("Spread exceeds the supported numeric range.")
        elif scale == 0:
            stdev = variance = standard_error = 0.0
        else:
            factor = math.sqrt(math.fsum((x / scale) ** 2 for x in deviations) / (count - 1))
            candidate = scale * factor
            if math.isfinite(candidate):
                stdev = candidate
                standard_error = candidate / math.sqrt(count)
                square = candidate * candidate
                if math.isfinite(square):
                    variance = square
                else:
                    warnings.append("Variance exceeds the supported numeric range.")
            else:
                warnings.append("Standard deviation exceeds the supported numeric range.")
    return {
        "count": count,
        "missing": missing,
        "mean": mean,
        "q1": _clamped_rank_quantile(ordered, 0.25),
        "median": _clamped_rank_quantile(ordered, 0.5),
        "q3": _clamped_rank_quantile(ordered, 0.75),
        "minimum": min(clean),
        "maximum": max(clean),
        "sum": total,
        "sample_variance": variance,
        "sample_stdev": stdev,
        "standard_error": standard_error,
        "warnings": warnings,
    }


def extra_descriptive_stats(values: Iterable[float | None]) -> dict:
    """Compute optional descriptive measures beyond the core describe() contract."""
    from collections import Counter
    from scipy import stats as _scipy_stats

    total_rows = 0
    clean = []
    for value in values:
        total_rows += 1
        norm = normalize_numeric(value)
        if norm is not None:
            clean.append(norm)
    if not clean:
        return {}
    n = len(clean)
    ordered = sorted(clean)
    lo, hi = ordered[0], ordered[-1]
    q1 = _clamped_rank_quantile(ordered, 0.25)
    q3 = _clamped_rank_quantile(ordered, 0.75)
    mean = math.fsum(x / n for x in clean)
    stdev = None
    if n > 1:
        dev = [x - mean for x in clean]
        scale = max(abs(x) for x in dev)
        stdev = 0.0 if scale == 0 else scale * math.sqrt(math.fsum((x / scale) ** 2 for x in dev) / (n - 1))
    coef_var = (100.0 * stdev / abs(mean)) if (stdev is not None and mean != 0) else None
    trimmed = float(_scipy_stats.trim_mean(clean, 0.05)) if n >= 1 else None
    skew = float(_scipy_stats.skew(clean, bias=False)) if n >= 3 and stdev and stdev > 0 else None
    kurt = float(_scipy_stats.kurtosis(clean, bias=False)) if n >= 4 and stdev and stdev > 0 else None
    counts = Counter(clean)
    top_val, top_cnt = counts.most_common(1)[0]
    return {
        "n_total": total_rows,
        "range": hi - lo,
        "iqr": q3 - q1,
        "coef_var": coef_var,
        "trimmed_mean": trimmed,
        "skewness": skew,
        "kurtosis": kurt,
        "mode": top_val if top_cnt > 1 else None,
    }
