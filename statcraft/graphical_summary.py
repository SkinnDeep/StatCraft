"""Graphical Summary of Descriptive Statistics.

Computes four-in-one summary metrics:
- Anderson-Darling normality test (A-squared and p-value)
- Descriptive statistics (Mean, StDev, Variance, Skewness, Kurtosis, N, Min, Q1, Median, Q3, Max)
- 95% Confidence Intervals for Mean, Median, and StDev
"""
from __future__ import annotations

import math
import statistics
from scipy import stats
from .engine import normalize_numeric
from .normality import normality


def _finite(val):
    return float(val) if val is not None and math.isfinite(val) else None


def graphical_summary(values: list, confidence: float = 0.95) -> dict:
    clean = [float(v) for v in (normalize_numeric(x) for x in values) if v is not None]
    n = len(clean)
    if n < 4:
        raise ValueError("Graphical Summary requires at least 4 nonmissing observations.")

    alpha = 1.0 - confidence
    clean_sorted = sorted(clean)

    # 1. Basic descriptive stats
    mean_val = statistics.fmean(clean)
    stdev_val = statistics.stdev(clean) if n > 1 else 0.0
    var_val = stdev_val ** 2

    # Skewness (Fisher-Pearson standardized third moment)
    if n > 2 and stdev_val > 0:
        m3 = sum((x - mean_val) ** 3 for x in clean) / n
        s3 = (stdev_val ** 3)
        skew_val = (math.sqrt(n * (n - 1)) / (n - 2)) * (m3 / s3)
    else:
        skew_val = 0.0

    # Kurtosis (excess kurtosis)
    if n > 3 and stdev_val > 0:
        m4 = sum((x - mean_val) ** 4 for x in clean) / n
        s4 = (stdev_val ** 4)
        term1 = (n - 1) / ((n - 2) * (n - 3))
        kurt_val = term1 * ((n + 1) * (m4 / s4) - 3 * (n - 1))
    else:
        kurt_val = 0.0

    # Five-number summary
    min_val = clean_sorted[0]
    max_val = clean_sorted[-1]
    
    # Quartiles (StatCraft default convention)
    def _quantile(p):
        pos = (n + 1) * p
        k = int(pos)
        d = pos - k
        if k < 1:
            return clean_sorted[0]
        if k >= n:
            return clean_sorted[-1]
        return clean_sorted[k - 1] + d * (clean_sorted[k] - clean_sorted[k - 1])

    q1_val = _quantile(0.25)
    median_val = statistics.median(clean)
    q3_val = _quantile(0.75)
    iqr_val = q3_val - q1_val

    # Outliers for boxplot
    lower_fence = q1_val - 1.5 * iqr_val
    upper_fence = q3_val + 1.5 * iqr_val
    outliers = [x for x in clean if x < lower_fence or x > upper_fence]
    non_outliers = [x for x in clean if lower_fence <= x <= upper_fence]
    whisker_low = min(non_outliers) if non_outliers else min_val
    whisker_high = max(non_outliers) if non_outliers else max_val

    # 2. Anderson-Darling Normality Test
    try:
        norm_res = normality(clean)
        ad_stat = norm_res.get('statistic', 0.0)
        ad_p = norm_res.get('p', 0.0)
    except Exception:
        ad_stat = None
        ad_p = None

    # 3. 95% CI for Mean (Student-t)
    if n > 1 and stdev_val > 0:
        se_mean = stdev_val / math.sqrt(n)
        t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=n - 1)
        ci_mean_low = mean_val - t_crit * se_mean
        ci_mean_high = mean_val + t_crit * se_mean
    else:
        ci_mean_low = mean_val
        ci_mean_high = mean_val

    # 4. 95% CI for StDev (Chi-Square)
    if n > 1 and stdev_val > 0:
        chi2_low = stats.chi2.ppf(alpha / 2.0, df=n - 1)
        chi2_high = stats.chi2.ppf(1.0 - alpha / 2.0, df=n - 1)
        ci_stdev_low = math.sqrt((n - 1) * var_val / chi2_high) if chi2_high > 0 else 0.0
        ci_stdev_high = math.sqrt((n - 1) * var_val / chi2_low) if chi2_low > 0 else 0.0
    else:
        ci_stdev_low = stdev_val
        ci_stdev_high = stdev_val

    # 5. 95% CI for Median (Nonparametric sign test / order statistics)
    # Using normal approximation to binomial for order statistics
    k_med = int(round((n - stats.norm.ppf(1.0 - alpha / 2.0) * math.sqrt(n)) / 2.0))
    k_med = max(0, min(n - 1, k_med))
    ci_med_low = clean_sorted[k_med]
    ci_med_high = clean_sorted[n - 1 - k_med]

    # Histogram binning (Sturges / Scott)
    nbins = max(6, min(25, int(math.ceil(math.log2(n) + 1))))
    span = max_val - min_val
    if span <= 0:
        span = 1.0
    bin_width = span / nbins
    bins = [min_val + i * bin_width for i in range(nbins + 1)]
    counts = [0] * nbins
    for x in clean:
        b = int((x - min_val) / bin_width)
        b = min(nbins - 1, max(0, b))
        counts[b] += 1

    return {
        'n': n,
        'mean': mean_val,
        'stdev': stdev_val,
        'variance': var_val,
        'skewness': skew_val,
        'kurtosis': kurt_val,
        'min': min_val,
        'q1': q1_val,
        'median': median_val,
        'q3': q3_val,
        'max': max_val,
        'iqr': iqr_val,
        'ad_stat': ad_stat,
        'ad_p': ad_p,
        'confidence': confidence,
        'ci_mean': (ci_mean_low, ci_mean_high),
        'ci_median': (ci_med_low, ci_med_high),
        'ci_stdev': (ci_stdev_low, ci_stdev_high),
        'boxplot': {
            'min': min_val,
            'whisker_low': whisker_low,
            'q1': q1_val,
            'median': median_val,
            'q3': q3_val,
            'whisker_high': whisker_high,
            'max': max_val,
            'outliers': outliers,
        },
        'histogram': {
            'bins': bins,
            'counts': counts,
            'bin_width': bin_width,
        },
        'values_sorted': clean_sorted,
    }
