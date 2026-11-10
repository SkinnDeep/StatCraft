"""Resampling Studio: Bootstrapping & Randomization (Permutation) Tests."""
from __future__ import annotations

import math
from typing import Any, Dict, Sequence
import numpy as np


_STAT_FNS = {
    "mean": lambda a: float(np.mean(a)),
    "median": lambda a: float(np.median(a)),
    "stdev": lambda a: float(np.std(a, ddof=1)) if len(a) >= 2 else 0.0,
    "variance": lambda a: float(np.var(a, ddof=1)) if len(a) >= 2 else 0.0,
    "iqr": lambda a: float(np.percentile(a, 75) - np.percentile(a, 25)),
}


def _clean_arr(values: Sequence[Any], label: str = "Variable") -> np.ndarray:
    nums = []
    for v in values:
        if v is None or isinstance(v, bool):
            continue
        try:
            f = float(v)
            if math.isfinite(f):
                nums.append(f)
        except (ValueError, TypeError):
            continue
    if len(nums) < 2:
        raise ValueError(f"{label} requires at least 2 finite observations.")
    return np.asarray(nums, dtype=float)


def _resample_hist(arr: np.ndarray, bins: int = 24) -> Dict[str, List[float]]:
    counts, edges = np.histogram(arr, bins=bins)
    return {"edges": [float(e) for e in edges], "counts": [int(c) for c in counts]}


def bootstrap_1sample(
    values: Sequence[Any],
    statistic: str = "Mean",
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int | None = 42,
    variable_name: str = "Sample",
) -> Dict[str, Any]:
    """Perform 1-sample bootstrap confidence interval estimation."""
    arr = _clean_arr(values, variable_name)
    key = statistic.strip().lower()
    if key not in _STAT_FNS:
        raise ValueError(f"Unsupported statistic '{statistic}'. Choose Mean, Median, StDev, Variance, or IQR.")
    if not 100 <= int(n_resamples) <= 50000:
        raise ValueError("Number of resamples must be between 100 and 50,000.")
    if not 0.5 < float(confidence) < 1.0:
        raise ValueError("Confidence level must be between 0.50 and 1.00.")

    B = int(n_resamples)
    n = len(arr)
    obs = _STAT_FNS[key](arr)
    rng = np.random.default_rng(seed)

    # Vectorized index matrix (B x n)
    idx = rng.integers(0, n, size=(B, n))
    samples = arr[idx]
    if key == "mean":
        boot_vals = np.mean(samples, axis=1)
    elif key == "median":
        boot_vals = np.median(samples, axis=1)
    elif key == "stdev":
        boot_vals = np.std(samples, axis=1, ddof=1)
    elif key == "variance":
        boot_vals = np.var(samples, axis=1, ddof=1)
    else:
        boot_vals = np.percentile(samples, 75, axis=1) - np.percentile(samples, 25, axis=1)

    alpha = 1.0 - float(confidence)
    ci_low, ci_high = [float(x) for x in np.percentile(boot_vals, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])]
    boot_mean = float(np.mean(boot_vals))
    boot_se = float(np.std(boot_vals, ddof=1))
    bias = boot_mean - obs

    return {
        "analysis": "bootstrap_1sample",
        "variable": variable_name,
        "statistic": statistic.title() if key != "iqr" else "IQR",
        "n": int(n),
        "resamples": B,
        "confidence": float(confidence),
        "observed": obs,
        "bootstrap_mean": boot_mean,
        "bias": bias,
        "se_bootstrap": boot_se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "histogram": _resample_hist(boot_vals),
    }


def bootstrap_2sample(
    values1: Sequence[Any],
    values2: Sequence[Any],
    statistic: str = "Mean Difference",
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int | None = 42,
    name1: str = "Sample 1",
    name2: str = "Sample 2",
) -> Dict[str, Any]:
    """Perform 2-sample bootstrap for difference in means/medians or ratio of StDevs."""
    a1 = _clean_arr(values1, name1)
    a2 = _clean_arr(values2, name2)
    B = int(n_resamples)
    if not 100 <= B <= 50000:
        raise ValueError("Number of resamples must be between 100 and 50,000.")
    if not 0.5 < float(confidence) < 1.0:
        raise ValueError("Confidence level must be between 0.50 and 1.00.")

    mode = statistic.strip().lower()
    rng = np.random.default_rng(seed)
    s1 = a1[rng.integers(0, len(a1), size=(B, len(a1)))]
    s2 = a2[rng.integers(0, len(a2), size=(B, len(a2)))]

    if "median" in mode:
        obs = float(np.median(a1) - np.median(a2))
        boot_vals = np.median(s1, axis=1) - np.median(s2, axis=1)
        stat_label = "Median Difference (1 - 2)"
    elif "ratio" in mode or "stdev" in mode:
        sd2 = float(np.std(a2, ddof=1))
        if sd2 <= 0:
            raise ValueError("Sample 2 standard deviation must be positive for ratio.")
        obs = float(np.std(a1, ddof=1) / sd2)
        sd2_b = np.std(s2, axis=1, ddof=1)
        boot_vals = np.where(sd2_b > 0, np.std(s1, axis=1, ddof=1) / np.maximum(sd2_b, 1e-15), np.nan)
        boot_vals = boot_vals[~np.isnan(boot_vals)]
        stat_label = "StDev Ratio (1 / 2)"
    else:
        obs = float(np.mean(a1) - np.mean(a2))
        boot_vals = np.mean(s1, axis=1) - np.mean(s2, axis=1)
        stat_label = "Mean Difference (1 - 2)"

    alpha = 1.0 - float(confidence)
    ci_low, ci_high = [float(x) for x in np.percentile(boot_vals, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])]
    boot_mean = float(np.mean(boot_vals))
    boot_se = float(np.std(boot_vals, ddof=1))

    return {
        "analysis": "bootstrap_2sample",
        "sample1": name1,
        "sample2": name2,
        "statistic": stat_label,
        "n1": int(len(a1)),
        "n2": int(len(a2)),
        "resamples": B,
        "confidence": float(confidence),
        "observed": obs,
        "bootstrap_mean": boot_mean,
        "bias": boot_mean - obs,
        "se_bootstrap": boot_se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "histogram": _resample_hist(boot_vals),
    }


def randomization_1sample(
    values: Sequence[Any],
    hypothesized_mean: float = 0.0,
    alternative: str = "two_sided",
    n_resamples: int = 2000,
    seed: int | None = 42,
    variable_name: str = "Sample",
) -> Dict[str, Any]:
    """One-sample sign-flip permutation test against hypothesized center."""
    arr = _clean_arr(values, variable_name)
    B = int(n_resamples)
    if not 100 <= B <= 50000:
        raise ValueError("Number of permutations must be between 100 and 50,000.")

    diff = arr - float(hypothesized_mean)
    obs = float(np.mean(diff))
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(B, len(diff)))
    perm_means = np.mean(signs * diff, axis=1)

    alt = alternative.strip().lower()
    if alt in ("greater", "upper"):
        extreme = int(np.sum(perm_means >= obs - 1e-12))
    elif alt in ("less", "lower"):
        extreme = int(np.sum(perm_means <= obs + 1e-12))
    else:
        extreme = int(np.sum(np.abs(perm_means) >= abs(obs) - 1e-12))
        alt = "two_sided"

    p_value = (extreme + 1.0) / (B + 1.0)
    return {
        "analysis": "randomization_1sample",
        "variable": variable_name,
        "n": int(len(arr)),
        "sample_mean": float(np.mean(arr)),
        "hypothesized_mean": float(hypothesized_mean),
        "observed_diff": obs,
        "resamples": B,
        "alternative": alt,
        "extreme_count": extreme,
        "p_value": float(p_value),
        "histogram": _resample_hist(perm_means),
    }


def randomization_2sample(
    values1: Sequence[Any],
    values2: Sequence[Any],
    alternative: str = "two_sided",
    n_resamples: int = 2000,
    seed: int | None = 42,
    name1: str = "Sample 1",
    name2: str = "Sample 2",
) -> Dict[str, Any]:
    """Two-sample label-permutation test for difference in means."""
    a1 = _clean_arr(values1, name1)
    a2 = _clean_arr(values2, name2)
    B = int(n_resamples)
    if not 100 <= B <= 50000:
        raise ValueError("Number of permutations must be between 100 and 50,000.")

    obs = float(np.mean(a1) - np.mean(a2))
    pooled = np.concatenate([a1, a2])
    n1 = len(a1)
    n_tot = len(pooled)
    total_sum = float(np.sum(pooled))
    rng = np.random.default_rng(seed)

    perm_diffs = np.empty(B, dtype=float)
    n2 = len(a2)
    for b in range(B):
        chosen = rng.choice(n_tot, size=n1, replace=False)
        sum1 = float(np.sum(pooled[chosen]))
        perm_diffs[b] = (sum1 / n1) - ((total_sum - sum1) / n2)

    alt = alternative.strip().lower()
    if alt in ("greater", "upper"):
        extreme = int(np.sum(perm_diffs >= obs - 1e-12))
    elif alt in ("less", "lower"):
        extreme = int(np.sum(perm_diffs <= obs + 1e-12))
    else:
        extreme = int(np.sum(np.abs(perm_diffs) >= abs(obs) - 1e-12))
        alt = "two_sided"

    p_value = (extreme + 1.0) / (B + 1.0)
    return {
        "analysis": "randomization_2sample",
        "sample1": name1,
        "sample2": name2,
        "n1": n1,
        "n2": n2,
        "mean1": float(np.mean(a1)),
        "mean2": float(np.mean(a2)),
        "observed_diff": obs,
        "resamples": B,
        "alternative": alt,
        "extreme_count": extreme,
        "p_value": float(p_value),
        "histogram": _resample_hist(perm_diffs),
    }


def format_resampling_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    lines = []
    if kind == "bootstrap_1sample":
        pct = round(result["confidence"] * 100, 2)
        lines.extend([
            f"Bootstrapping for 1-Sample Function: {result['variable']} ({result['statistic']})",
            f"  N = {result['n']}   |   Resamples = {result['resamples']}",
            f"  Observed {result['statistic']}:   {result['observed']:.6g}",
            f"  Bootstrap Mean:      {result['bootstrap_mean']:.6g}",
            f"  Bias:                {result['bias']:.6g}",
            f"  Bootstrap SE:        {result['se_bootstrap']:.6g}",
            f"  {pct}% Percentile CI:  ({result['ci_low']:.6g}, {result['ci_high']:.6g})",
        ])
    elif kind == "bootstrap_2sample":
        pct = round(result["confidence"] * 100, 2)
        lines.extend([
            f"Bootstrapping for 2 Samples: {result['sample1']} vs {result['sample2']}",
            f"  Statistic: {result['statistic']}   |   N1 = {result['n1']}, N2 = {result['n2']}",
            f"  Resamples = {result['resamples']}",
            f"  Observed Estimate:   {result['observed']:.6g}",
            f"  Bootstrap Mean:      {result['bootstrap_mean']:.6g}",
            f"  Bias:                {result['bias']:.6g}",
            f"  Bootstrap SE:        {result['se_bootstrap']:.6g}",
            f"  {pct}% Percentile CI:  ({result['ci_low']:.6g}, {result['ci_high']:.6g})",
        ])
    elif kind == "randomization_1sample":
        lines.extend([
            f"Randomization Test (1-Sample Sign-Flip): {result['variable']}",
            f"  Null hypothesis: H0: Mean = {result['hypothesized_mean']:.6g}   |   Alt: {result['alternative']}",
            f"  N = {result['n']}   |   Sample Mean = {result['sample_mean']:.6g}   |   Permutations = {result['resamples']}",
            f"  Extreme count: {result['extreme_count']}   |   P-Value = {result['p_value']:.4f}",
        ])
    elif kind == "randomization_2sample":
        lines.extend([
            f"Randomization Test (2-Sample Means): {result['sample1']} vs {result['sample2']}",
            f"  N1 = {result['n1']} (Mean = {result['mean1']:.6g})   |   N2 = {result['n2']} (Mean = {result['mean2']:.6g})",
            f"  Observed Difference (1 - 2): {result['observed_diff']:.6g}   |   Alt: {result['alternative']}",
            f"  Permutations = {result['resamples']}   |   Extreme count = {result['extreme_count']}   |   P-Value = {result['p_value']:.4f}",
        ])
    return "\n".join(lines)
