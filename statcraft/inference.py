"""Original, supported classical inference for StatCraft; no vendor parity claim.

All tests are two-sided. Missing numeric values follow StatCraft normalization.
Pairs are removed together; independent samples/groups omit missing separately.
SciPy supplies distribution tails/critical values, not application dependencies.
Official API sources consulted:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from scipy import stats
from .engine import normalize_numeric


def _finite(value, name):
    result = normalize_numeric(value)
    if result is None:
        raise ValueError(f"{name} must be finite and nonmissing.")
    return result


def _confidence(value):
    result = _finite(value, "Confidence level")
    if not 0 < result < 1:
        raise ValueError("Confidence level must lie strictly between 0 and 1.")
    return result


def _clean(values, name, minimum=2):
    clean, missing = [], 0
    for value in values:
        result = normalize_numeric(value)
        if result is None:
            missing += 1
        else:
            clean.append(result)
    if len(clean) < minimum:
        raise ValueError(f"{name} requires at least {minimum} nonmissing observations.")
    return clean, missing


def _pairs(x, y, minimum):
    x, y = list(x), list(y)
    if len(x) != len(y):
        raise ValueError("Paired columns must have the same row count.")
    left, right, indices = [], [], []
    for index, (a, b) in enumerate(zip(x, y)):
        a, b = normalize_numeric(a), normalize_numeric(b)
        if a is not None and b is not None:
            left.append(a)
            right.append(b)
            indices.append(index)
    if len(left) < minimum:
        raise ValueError(f"At least {minimum} complete paired rows are required.")
    return left, right, len(x) - len(left), indices


def _summary(values):
    count = len(values)
    mean = math.fsum(value / count for value in values)
    if not math.isfinite(mean):
        raise ValueError("Mean exceeds the supported numeric range.")
    deviations = [value - mean for value in values]
    if not all(math.isfinite(value) for value in deviations):
        raise ValueError("Data spread exceeds the supported numeric range.")
    scale = max(abs(value) for value in deviations)
    stdev = None
    if count > 1:
        stdev = 0.0 if scale == 0 else scale * math.sqrt(
            math.fsum((value / scale) ** 2 for value in deviations) / (count - 1))
        if not math.isfinite(stdev):
            raise ValueError("Standard deviation exceeds the supported numeric range.")
    return count, mean, stdev, deviations


def _square_sum(values):
    scale = max((abs(value) for value in values), default=0.0)
    if scale == 0:
        return 0.0
    # Multiplication yields inf rather than raising an unhelpful raw power error.
    norm = scale * math.sqrt(math.fsum((value / scale) ** 2 for value in values))
    result = norm * norm
    if not math.isfinite(result):
        raise ValueError("Sum of squares exceeds the supported numeric range.")
    return result


def _pvalue(t, df):
    return min(1.0, max(0.0, float(2.0 * stats.t.sf(abs(t), df))))


def _interval(estimate, standard_error, df, confidence):
    critical = float(stats.t.isf((1.0 - confidence) / 2.0, df))
    margin = critical * standard_error
    try:
        low, high = math.fsum((estimate, -margin)), math.fsum((estimate, margin))
    except (OverflowError, ValueError) as exc:
        raise ValueError("Confidence interval exceeds the supported numeric range.") from exc
    if not all(math.isfinite(value) for value in (low, high)):
        raise ValueError("Confidence interval exceeds the supported numeric range.")
    return low, high


def _t_result(method, estimate, standard_error, df, mu, confidence):
    if not math.isfinite(standard_error) or standard_error <= 0:
        raise ValueError("A t test requires positive estimable sampling variation; constant data are unsupported.")
    difference = estimate - mu
    if not math.isfinite(difference):
        raise ValueError("Difference from the null value exceeds the supported numeric range.")
    t = difference / standard_error
    if not math.isfinite(t):
        raise ValueError("Test statistic exceeds the supported numeric range.")
    low, high = _interval(estimate, standard_error, df, confidence)
    return {"method": method, "standard_error": standard_error, "null_value": mu,
            "t": t, "df": df, "p_value": _pvalue(t, df), "confidence": confidence,
            "ci_low": low, "ci_high": high, "alternative": "two-sided", "warnings": []}


def one_sample_t(values: Iterable[float | None], mu=0, confidence=.95) -> dict:
    """Test a population mean; CI covers the mean, not mean-minus-mu."""
    confidence, mu = _confidence(confidence), _finite(mu, "Null mean")
    clean, missing = _clean(values, "One-sample t test")
    count, mean, stdev, _ = _summary(clean)
    result = _t_result("One-sample t test", mean, stdev / math.sqrt(count),
                       count - 1, mu, confidence)
    result.update(count=count, missing=missing, mean=mean, sample_stdev=stdev,
                  assumptions="Independent observations; a normally distributed population for exact small-sample inference.")
    return result


def paired_t(x, y, mu=0, confidence=.95) -> dict:
    """Test mean x-y; omit a complete row when either partner is missing."""
    confidence, mu = _confidence(confidence), _finite(mu, "Null mean difference")
    left, right, missing, indices = _pairs(x, y, 2)
    differences = [a - b for a, b in zip(left, right)]
    if not all(math.isfinite(value) for value in differences):
        raise ValueError("Paired differences exceed the supported numeric range.")
    count, mean, stdev, _ = _summary(differences)
    result = _t_result("Paired t test (x - y)", mean, stdev / math.sqrt(count),
                       count - 1, mu, confidence)
    result.update(count=count, missing=missing, mean_difference=mean,
                  sample_stdev=stdev, row_indices=indices,
                  assumptions="Independent pairs; normally distributed within-pair differences for exact small-sample inference.")
    return result


def two_sample_t(x, y, mu=0, confidence=.95) -> dict:
    """Welch unequal-variance test of mean(x)-mean(y), with independent deletion."""
    confidence, mu = _confidence(confidence), _finite(mu, "Null mean difference")
    left, missing_x = _clean(x, "First sample")
    right, missing_y = _clean(y, "Second sample")
    nx, mx, sx, _ = _summary(left)
    ny, my, sy, _ = _summary(right)
    ax, ay = sx / math.sqrt(nx), sy / math.sqrt(ny)
    se = math.hypot(ax, ay)
    if not math.isfinite(se):
        raise ValueError("Sampling uncertainty exceeds the supported numeric range.")
    if se == 0:
        raise ValueError("Welch's test requires variation in at least one sample.")
    # Normalized form avoids squaring enormous/subnormal variances directly.
    denominator = (ax / se) ** 4 / (nx - 1) + (ay / se) ** 4 / (ny - 1)
    df = 1.0 / denominator
    difference = mx - my
    if not math.isfinite(difference):
        raise ValueError("Between-sample mean difference exceeds the supported numeric range.")
    result = _t_result("Welch two-sample t test (x - y)", difference, se, df, mu, confidence)
    result.update(count_x=nx, count_y=ny, missing_x=missing_x, missing_y=missing_y,
                  mean_x=mx, mean_y=my, stdev_x=sx, stdev_y=sy,
                  mean_difference=difference,
                  assumptions="Independent samples and observations; approximately normal populations for small samples. Equal population variances are not assumed.")
    return result


def one_way_anova(groups) -> dict:
    """Classical equal-variance one-way ANOVA; independently omit group missing."""
    groups = list(groups)
    if len(groups) < 2:
        raise ValueError("One-way ANOVA requires at least two groups.")
    prepared, summaries = [], []
    for index, group in enumerate(groups):
        clean, missing = _clean(group, f"Group {index + 1}", minimum=1)
        count, mean, stdev, deviations = _summary(clean)
        prepared.append((count, mean, deviations))
        summaries.append({"group": index + 1, "count": count, "missing": missing,
                          "mean": mean, "sample_stdev": stdev})
    count = sum(item[0] for item in prepared)
    df_between, df_within = len(groups) - 1, count - len(groups)
    if df_within <= 0:
        raise ValueError("ANOVA requires residual degrees of freedom; all groups cannot be singletons.")
    grand_mean = math.fsum(n / count * mean for n, mean, _ in prepared)
    between_terms = [math.sqrt(n) * (mean - grand_mean) for n, mean, _ in prepared]
    within_terms = [value for _, _, deviations in prepared for value in deviations]
    if not all(math.isfinite(value) for value in between_terms):
        raise ValueError("Between-group spread exceeds the supported numeric range.")
    ss_between, ss_within = _square_sum(between_terms), _square_sum(within_terms)
    if ss_within <= 0:
        raise ValueError("ANOVA inference is undefined without within-group variation.")
    ms_between, ms_within = ss_between / df_between, ss_within / df_within
    if ms_within <= 0:
        raise ValueError("Within-group mean square is below the supported numeric range.")
    f = ms_between / ms_within
    ss_total = ss_between + ss_within
    if not all(math.isfinite(value) for value in (f, ss_total)):
        raise ValueError("ANOVA arithmetic exceeds the supported numeric range.")
    return {"method": "Classical one-way ANOVA", "count": count,
            "missing": sum(row["missing"] for row in summaries),
            "grand_mean": grand_mean, "group_statistics": summaries,
            "ss_between": ss_between, "ss_within": ss_within,
            "ss_total": ss_total,
            "df_between": df_between, "df_within": df_within,
            "ms_between": ms_between, "ms_within": ms_within, "f": f,
            "p_value": float(stats.f.sf(f, df_between, df_within)),
            "assumptions": "Independent observations; normally distributed populations; equal within-group population variances.",
            "warnings": []}


def linear_regression(x, y, confidence=.95) -> dict:
    """Simple OLS y=intercept+slope*x, with complete paired-row deletion.

    At least three pairs and variation in x and y are required. Exact fits return
    coefficients/R2 but no inferential t/p/CI: residual variance cannot support
    ordinary significance testing. No multiple predictors/weights are supported.
    """
    confidence = _confidence(confidence)
    left, right, missing, indices = _pairs(x, y, 3)
    count, mean_x, _, dx = _summary(left)
    _, mean_y, _, dy = _summary(right)
    scale_x, scale_y = max(abs(value) for value in dx), max(abs(value) for value in dy)
    if scale_x == 0:
        raise ValueError("Regression requires variation in the predictor; constant x is rank deficient.")
    if scale_y == 0:
        raise ValueError("Regression inference and R-squared are undefined for a constant response.")
    ux, uy = [value / scale_x for value in dx], [value / scale_y for value in dy]
    sxx = math.fsum(value * value for value in ux)
    syy = math.fsum(value * value for value in uy)
    sxy = math.fsum(a * b for a, b in zip(ux, uy))
    slope = (scale_y / scale_x) * (sxy / sxx)
    intercept = mean_y - slope * mean_x
    try:
        fitted = [math.fsum((mean_y, slope * value)) for value in dx]
    except (ValueError, OverflowError) as exc:
        raise ValueError("Regression arithmetic exceeds the supported numeric range.") from exc
    residuals = [a - b for a, b in zip(right, fitted)]
    if not all(math.isfinite(value) for value in (slope, intercept, *fitted, *residuals)):
        raise ValueError("Regression arithmetic exceeds the supported numeric range.")
    df = count - 2
    residual_scale = max(abs(value) for value in residuals)
    residual_stdev = (0.0 if residual_scale == 0 else residual_scale * math.sqrt(
        math.fsum((value / residual_scale) ** 2 for value in residuals) / df))
    if not math.isfinite(residual_stdev):
        raise ValueError("Residual spread exceeds the supported numeric range.")
    residual_unit = math.fsum((value / scale_y) ** 2 for value in residuals)
    r_squared = min(1.0, max(0.0, 1.0 - residual_unit / syy))
    slope_se = residual_stdev / scale_x / math.sqrt(sxx)
    intercept_se = residual_stdev * math.hypot(1 / math.sqrt(count),
                                              (mean_x / scale_x) / math.sqrt(sxx))
    if not math.isfinite(intercept_se):
        raise ValueError("Intercept uncertainty exceeds the supported numeric range.")
    result = {"method": "Simple linear regression (OLS, intercept included)",
              "count": count, "missing": missing, "row_indices": indices,
              "intercept": intercept, "slope": slope,
              "intercept_se": intercept_se, "slope_se": slope_se,
              "r_squared": r_squared, "residual_stdev": residual_stdev, "df": df,
              "confidence": confidence, "fitted": fitted, "residuals": residuals,
              "assumptions": "A linear mean relationship; independent, normally distributed residuals with constant variance for coefficient t tests and confidence intervals.",
              "warnings": []}
    if residual_scale == 0:
        result.update(status="exact_fit", intercept_t=None, slope_t=None,
                      intercept_p_value=None, slope_p_value=None,
                      intercept_ci_low=None, intercept_ci_high=None,
                      slope_ci_low=None, slope_ci_high=None)
        result["warnings"].append("Exact fit: zero residual variation; coefficient significance tests and confidence intervals are not reported.")
    else:
        if slope_se <= 0 or intercept_se <= 0:
            raise ValueError("Coefficient uncertainty is below the supported numeric range.")
        intercept_t, slope_t = intercept / intercept_se, slope / slope_se
        if not all(math.isfinite(value) for value in (intercept_t, slope_t)):
            raise ValueError("Coefficient test statistic exceeds the supported numeric range.")
        ilow, ihigh = _interval(intercept, intercept_se, df, confidence)
        slow, shigh = _interval(slope, slope_se, df, confidence)
        result.update(status="estimated", intercept_t=intercept_t, slope_t=slope_t,
                      intercept_p_value=_pvalue(intercept_t, df), slope_p_value=_pvalue(slope_t, df),
                      intercept_ci_low=ilow, intercept_ci_high=ihigh,
                      slope_ci_low=slow, slope_ci_high=shigh)
    return result
