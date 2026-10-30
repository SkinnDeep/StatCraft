"""Nonparametric Statistical Tests with 1:1 StatCraft Numerical Parity.

Covers:
- 1-Sample Sign Test (`sign_test`)
- 1-Sample Wilcoxon Signed Rank Test (`one_sample_wilcoxon`)
- Mann-Whitney Test (`mann_whitney`)
- Kruskal-Wallis Test (`kruskal_wallis`)
- Mood's Median Test (`moods_median`)
- Friedman Test (`friedman_test`)
- Runs Test (`runs_test`)
- Paired Wilcoxon Test (`paired_wilcoxon`)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from scipy import stats


def _clean_numeric(series: Sequence[Any]) -> np.ndarray:
    """Extract valid finite floats from series."""
    vals: List[float] = []
    for v in series:
        if v is None:
            continue
        try:
            fv = float(v)
            if math.isfinite(fv):
                vals.append(fv)
        except (ValueError, TypeError):
            continue
    return np.array(vals, dtype=float)


def sign_test(
    data: Sequence[Any],
    test_median: float = 0.0,
    alternative: str = "two_sided",
    conf_level: float = 0.95,
) -> Dict[str, Any]:
    """1-Sample Sign Test and Confidence Interval for the median."""
    arr = _clean_numeric(data)
    n_total = len(arr)
    if n_total == 0:
        raise ValueError("Sign test requires at least one numeric observation.")

    n_below = int(np.sum(arr < test_median))
    n_equal = int(np.sum(arr == test_median))
    n_above = int(np.sum(arr > test_median))
    n_test = n_below + n_above
    sample_median = float(np.median(arr))

    # P-value calculation under H0: Binomial(n_test, 0.5)
    if n_test == 0:
        p_val = 1.0
    elif alternative == "less":
        p_val = float(stats.binom.cdf(n_above, n_test, 0.5))
    elif alternative == "greater":
        p_val = float(1.0 - stats.binom.cdf(n_above - 1, n_test, 0.5))
    else:  # two_sided
        k = min(n_below, n_above)
        p_val = float(min(1.0, 2.0 * stats.binom.cdf(k, n_test, 0.5)))

    # Sign Confidence Intervals
    # Using sorted order statistics
    sorted_arr = np.sort(arr)
    ci_rows: List[Dict[str, Any]] = []

    # Find position d
    # P(d <= X <= n - d) = 1 - 2 * binom.cdf(d - 1, n, 0.5)
    for d in range(1, n_total // 2 + 1):
        achieved_conf = float(1.0 - 2.0 * stats.binom.cdf(d - 1, n_total, 0.5))
        lower = float(sorted_arr[d - 1])
        upper = float(sorted_arr[n_total - d])
        ci_rows.append({
            "position": d,
            "confidence": achieved_conf,
            "lower": lower,
            "upper": upper,
        })

    # Select lower/upper surrounding target conf_level
    best_exact = None
    for row in ci_rows:
        if row["confidence"] >= conf_level:
            best_exact = row
            break
    if best_exact is None and ci_rows:
        best_exact = ci_rows[-1]

    # Non-linear interpolation (NLI) for target confidence
    nli_lower = None
    nli_upper = None
    if len(ci_rows) >= 2:
        # find pair spanning conf_level
        c_below = None
        c_above = None
        for i in range(len(ci_rows) - 1):
            if ci_rows[i]["confidence"] >= conf_level and ci_rows[i + 1]["confidence"] < conf_level:
                c_above = ci_rows[i]
                c_below = ci_rows[i + 1]
                break
        if c_below is not None and c_above is not None:
            frac = (conf_level - c_below["confidence"]) / max(1e-12, (c_above["confidence"] - c_below["confidence"]))
            nli_lower = float(c_below["lower"] + frac * (c_above["lower"] - c_below["lower"]))
            nli_upper = float(c_below["upper"] + frac * (c_above["upper"] - c_below["upper"]))
        elif best_exact is not None:
            nli_lower = best_exact["lower"]
            nli_upper = best_exact["upper"]

    return {
        "analysis": "sign_test",
        "n": n_total,
        "n_below": n_below,
        "n_equal": n_equal,
        "n_above": n_above,
        "n_test": n_test,
        "median": sample_median,
        "test_median": test_median,
        "alternative": alternative,
        "p_value": p_val,
        "confidence_intervals": ci_rows,
        "target_conf": conf_level,
        "best_exact_ci": best_exact,
        "nli_ci": (nli_lower, nli_upper) if nli_lower is not None else None,
    }


def one_sample_wilcoxon(
    data: Sequence[Any],
    test_median: float = 0.0,
    alternative: str = "two_sided",
    conf_level: float = 0.95,
) -> Dict[str, Any]:
    """1-Sample Wilcoxon Signed Rank Test and Pseudo-Median CI."""
    arr = _clean_numeric(data)
    n_total = len(arr)
    if n_total == 0:
        raise ValueError("Wilcoxon signed rank test requires at least one numeric observation.")

    diffs = arr - test_median
    non_zero_diffs = diffs[diffs != 0.0]
    n_test = len(non_zero_diffs)

    if n_test == 0:
        return {
            "analysis": "one_sample_wilcoxon",
            "n": n_total,
            "n_test": 0,
            "statistic_w": 0.0,
            "p_value": 1.0,
            "estimated_median": float(np.median(arr)),
            "test_median": test_median,
            "alternative": alternative,
            "confidence": conf_level,
            "ci": (float(np.min(arr)), float(np.max(arr))),
        }

    abs_diffs = np.abs(non_zero_diffs)
    ranks = stats.rankdata(abs_diffs)

    # In StatCraft, W is the sum of ranks of positive differences
    pos_mask = non_zero_diffs > 0
    w_stat = float(np.sum(ranks[pos_mask]))

    mean_w = n_test * (n_test + 1) / 4.0

    # Tie adjustment for variance
    _, counts = np.unique(abs_diffs, return_counts=True)
    tie_term = np.sum(counts**3 - counts)
    var_w = (n_test * (n_test + 1) * (2 * n_test + 1) - 0.5 * tie_term) / 24.0
    sd_w = math.sqrt(max(1e-12, var_w))

    # Continuity correction
    if w_stat > mean_w:
        z = (w_stat - mean_w - 0.5) / sd_w
    elif w_stat < mean_w:
        z = (w_stat - mean_w + 0.5) / sd_w
    else:
        z = 0.0

    # P-value calculation
    if alternative == "greater":
        p_val = float(1.0 - stats.norm.cdf(z))
    elif alternative == "less":
        p_val = float(stats.norm.cdf(z))
    else:  # two_sided
        p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))

    # Exact or scipy reference for small sample without ties
    if n_test <= 50 and len(counts) == n_test:
        try:
            alt_scipy = "two-sided" if alternative == "two_sided" else "greater" if alternative == "greater" else "less"
            res_sp = stats.wilcoxon(non_zero_diffs, alternative=alt_scipy)
            p_val = float(res_sp.pvalue)
        except Exception:
            pass

    # Walsh averages for estimated pseudo-median and CI
    walsh: List[float] = []
    for i in range(n_total):
        for j in range(i, n_total):
            walsh.append((arr[i] + arr[j]) / 2.0)
    walsh.sort()
    m_walsh = len(walsh)
    estimated_median = float(np.median(walsh))

    # Critical rank for confidence interval
    alpha = 1.0 - conf_level
    z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
    k = int(round(mean_w - z_crit * sd_w))
    k = max(1, min(k, m_walsh // 2))

    ci_lower = float(walsh[k - 1])
    ci_upper = float(walsh[m_walsh - k])

    return {
        "analysis": "one_sample_wilcoxon",
        "n": n_total,
        "n_test": n_test,
        "statistic_w": w_stat,
        "mean_w": mean_w,
        "sd_w": sd_w,
        "z": z,
        "p_value": p_val,
        "estimated_median": estimated_median,
        "test_median": test_median,
        "alternative": alternative,
        "confidence": conf_level,
        "ci": (ci_lower, ci_upper),
    }


def mann_whitney(
    sample1: Sequence[Any],
    sample2: Sequence[Any],
    test_diff: float = 0.0,
    alternative: str = "two_sided",
    conf_level: float = 0.95,
) -> Dict[str, Any]:
    """Mann-Whitney Two-Sample Wilcoxon Rank-Sum Test and Hodges-Lehmann CI."""
    arr1 = _clean_numeric(sample1)
    arr2 = _clean_numeric(sample2)
    n1 = len(arr1)
    n2 = len(arr2)
    if n1 == 0 or n2 == 0:
        raise ValueError("Mann-Whitney test requires at least one observation in each sample.")

    med1 = float(np.median(arr1))
    med2 = float(np.median(arr2))

    # Shift sample 1 by test_diff under H0: eta1 - eta2 = test_diff
    shifted1 = arr1 - test_diff
    combined = np.concatenate([shifted1, arr2])
    n_comb = n1 + n2
    ranks = stats.rankdata(combined)

    # In StatCraft, W is the rank sum of the first sample
    w_stat = float(np.sum(ranks[:n1]))

    mean_w = n1 * (n_comb + 1) / 2.0

    # Variance with tie adjustment
    _, counts = np.unique(combined, return_counts=True)
    tie_term = np.sum(counts**3 - counts)
    var_w = (n1 * n2 * (n_comb + 1)) / 12.0 - (n1 * n2 * tie_term) / (12.0 * n_comb * (n_comb - 1))
    sd_w = math.sqrt(max(1e-12, var_w))

    # Continuity correction
    if w_stat > mean_w:
        z = (w_stat - mean_w - 0.5) / sd_w
    elif w_stat < mean_w:
        z = (w_stat - mean_w + 0.5) / sd_w
    else:
        z = 0.0

    if alternative == "greater":
        p_val = float(1.0 - stats.norm.cdf(z))
    elif alternative == "less":
        p_val = float(stats.norm.cdf(z))
    else:
        p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))

    # Exact or scipy fallback if no ties and modest sizes
    if tie_term == 0 and n1 <= 30 and n2 <= 30 and test_diff == 0.0:
        try:
            alt_sp = "two-sided" if alternative == "two_sided" else "greater" if alternative == "greater" else "less"
            res_sp = stats.mannwhitneyu(arr1, arr2, alternative=alt_sp)
            p_val = float(res_sp.pvalue)
        except Exception:
            pass

    # Hodges-Lehmann median difference and CI
    diffs = [x - y for x in arr1 for y in arr2]
    diffs.sort()
    n_diffs = len(diffs)
    hl_estimate = float(np.median(diffs))

    alpha = 1.0 - conf_level
    z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
    sd_hl = math.sqrt(n1 * n2 * (n_comb + 1) / 12.0)
    k = int(round(n1 * n2 / 2.0 - z_crit * sd_hl))
    k = max(1, min(k, n_diffs // 2))

    ci_lower = float(diffs[k - 1])
    ci_upper = float(diffs[n_diffs - k])

    return {
        "analysis": "mann_whitney",
        "n1": n1,
        "n2": n2,
        "median1": med1,
        "median2": med2,
        "point_estimate": hl_estimate,
        "test_diff": test_diff,
        "statistic_w": w_stat,
        "mean_w": mean_w,
        "sd_w": sd_w,
        "z": z,
        "p_value": p_val,
        "has_ties": bool(tie_term > 0),
        "confidence": conf_level,
        "ci": (ci_lower, ci_upper),
        "alternative": alternative,
    }


def kruskal_wallis(
    response: Sequence[Any],
    factor: Sequence[Any],
) -> Dict[str, Any]:
    """Kruskal-Wallis Multi-Group Median Comparison Test."""
    # Align pairs
    clean_resp: List[float] = []
    clean_fact: List[str] = []
    for r, f in zip(response, factor):
        if r is None or f is None:
            continue
        try:
            fr = float(r)
            if math.isfinite(fr):
                clean_resp.append(fr)
                clean_fact.append(str(f).strip())
        except (ValueError, TypeError):
            continue

    n_total = len(clean_resp)
    if n_total < 2:
        raise ValueError("Kruskal-Wallis test requires at least two valid response observations.")

    groups: Dict[str, List[float]] = {}
    for r, f in zip(clean_resp, clean_fact):
        groups.setdefault(f, []).append(r)

    k_groups = len(groups)
    if k_groups < 2:
        raise ValueError("Kruskal-Wallis test requires at least two distinct factor levels.")

    # Pool and rank
    ranks = stats.rankdata(clean_resp)

    # Group rank distributions
    group_stats: List[Dict[str, Any]] = []
    idx = 0
    group_ranks: Dict[str, List[float]] = {}
    for r, f in zip(clean_resp, clean_fact):
        group_ranks.setdefault(f, []).append(ranks[idx])
        idx += 1

    h_num = 0.0
    for level, vals in groups.items():
        n_i = len(vals)
        r_list = group_ranks[level]
        r_sum = float(sum(r_list))
        r_avg = r_sum / n_i
        med = float(np.median(vals))
        # StatCraft Z-value: (Ave Rank - (N+1)/2) / sqrt((N+1)*(N - n_i) / (12*n_i))
        denom_z = math.sqrt((n_total + 1.0) * (n_total - n_i) / (12.0 * n_i)) if n_total > n_i else 1.0
        z_val = (r_avg - (n_total + 1.0) / 2.0) / denom_z if denom_z > 0 else 0.0

        group_stats.append({
            "level": level,
            "n": n_i,
            "median": med,
            "rank_sum": r_sum,
            "avg_rank": r_avg,
            "z": z_val,
            "values": vals,
        })
        h_num += (r_sum**2) / n_i

    # H-statistic
    h_stat = (12.0 / (n_total * (n_total + 1.0))) * h_num - 3.0 * (n_total + 1.0)
    df = k_groups - 1

    # Tie adjustment
    _, counts = np.unique(clean_resp, return_counts=True)
    tie_term = np.sum(counts**3 - counts)
    c_factor = 1.0 - tie_term / (n_total**3 - n_total) if n_total > 1 else 1.0
    h_adj = h_stat / c_factor if c_factor > 0 else h_stat

    p_val = float(1.0 - stats.chi2.cdf(h_stat, df))
    p_adj = float(1.0 - stats.chi2.cdf(h_adj, df))

    return {
        "analysis": "kruskal_wallis",
        "n": n_total,
        "k": k_groups,
        "df": df,
        "h_statistic": float(h_stat),
        "h_adjusted": float(h_adj),
        "p_value": p_val,
        "p_adjusted": p_adj,
        "group_stats": group_stats,
        "has_ties": bool(tie_term > 0),
        "overall_avg_rank": (n_total + 1.0) / 2.0,
    }


def moods_median(
    response: Sequence[Any],
    factor: Sequence[Any],
    conf_level: float = 0.95,
) -> Dict[str, Any]:
    """Mood's Median Test with 95% Individual CIs for group medians."""
    clean_resp: List[float] = []
    clean_fact: List[str] = []
    for r, f in zip(response, factor):
        if r is None or f is None:
            continue
        try:
            fr = float(r)
            if math.isfinite(fr):
                clean_resp.append(fr)
                clean_fact.append(str(f).strip())
        except (ValueError, TypeError):
            continue

    n_total = len(clean_resp)
    if n_total < 2:
        raise ValueError("Mood's median test requires at least two valid responses.")

    groups: Dict[str, List[float]] = {}
    for r, f in zip(clean_resp, clean_fact):
        groups.setdefault(f, []).append(r)

    k_groups = len(groups)
    if k_groups < 2:
        raise ValueError("Mood's median test requires at least two factor levels.")

    overall_median = float(np.median(clean_resp))

    # Contingency table counts
    group_rows: List[Dict[str, Any]] = []
    n_le_total = 0
    n_gt_total = 0

    for level, vals in groups.items():
        arr = np.array(vals)
        n_le = int(np.sum(arr <= overall_median))
        n_gt = int(np.sum(arr > overall_median))
        n_le_total += n_le
        n_gt_total += n_gt
        n_i = len(vals)
        med = float(np.median(arr))
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1

        # 95% Individual CI for the median
        # d = (n_i + 1)/2 - 1.96 * sqrt(n_i)/2
        sorted_vals = np.sort(arr)
        z_crit = float(stats.norm.ppf(1.0 - (1.0 - conf_level) / 2.0))
        d = int(math.floor((n_i + 1.0) / 2.0 - z_crit * math.sqrt(n_i) / 2.0))
        d = max(1, min(d, n_i // 2 if n_i > 1 else 1))
        ci_lower = float(sorted_vals[d - 1])
        ci_upper = float(sorted_vals[n_i - d])

        group_rows.append({
            "level": level,
            "n": n_i,
            "n_le": n_le,
            "n_gt": n_gt,
            "median": med,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "ci": (ci_lower, ci_upper),
            "values": vals,
        })

    # Chi-square contingency test
    df = k_groups - 1
    chi_sq = 0.0
    for row in group_rows:
        n_i = row["n"]
        e_le = n_i * n_le_total / float(n_total)
        e_gt = n_i * n_gt_total / float(n_total)
        if e_le > 0:
            chi_sq += ((row["n_le"] - e_le) ** 2) / e_le
        if e_gt > 0:
            chi_sq += ((row["n_gt"] - e_gt) ** 2) / e_gt

    p_val = float(1.0 - stats.chi2.cdf(chi_sq, df))

    return {
        "analysis": "moods_median",
        "n": n_total,
        "k": k_groups,
        "overall_median": overall_median,
        "chi_square": float(chi_sq),
        "df": df,
        "p_value": p_val,
        "group_rows": group_rows,
        "confidence": conf_level,
    }


def friedman_test(
    response: Sequence[Any],
    treatment: Sequence[Any],
    block: Sequence[Any],
) -> Dict[str, Any]:
    """Friedman Nonparametric Randomized Complete Block Design Test."""
    # Clean triplets
    triplets: List[Tuple[float, str, str]] = []
    for r, t, b in zip(response, treatment, block):
        if r is None or t is None or b is None:
            continue
        try:
            fr = float(r)
            if math.isfinite(fr):
                triplets.append((fr, str(t).strip(), str(b).strip()))
        except (ValueError, TypeError):
            continue

    if len(triplets) < 4:
        raise ValueError("Friedman test requires at least four observations.")

    # Organize by block
    blocks_dict: Dict[str, Dict[str, float]] = {}
    treatments_set = set()
    for fr, t, b in triplets:
        blocks_dict.setdefault(b, {})[t] = fr
        treatments_set.add(t)

    treatments = sorted(treatments_set)
    k_treat = len(treatments)
    b_blocks = len(blocks_dict)

    if k_treat < 2:
        raise ValueError("Friedman test requires at least two treatment levels.")
    if b_blocks < 2:
        raise ValueError("Friedman test requires at least two blocks.")

    # Check balanced completeness
    for b_id, t_map in blocks_dict.items():
        if len(t_map) != k_treat:
            raise ValueError(f"Block '{b_id}' is incomplete; Friedman test requires a balanced complete block design.")

    # Rank treatments within each block
    rank_sums: Dict[str, float] = {t: 0.0 for t in treatments}
    tie_term_total = 0

    for b_id, t_map in blocks_dict.items():
        vals = [t_map[t] for t in treatments]
        block_ranks = stats.rankdata(vals)
        for t, r in zip(treatments, block_ranks):
            rank_sums[t] += float(r)

        _, counts = np.unique(vals, return_counts=True)
        tie_term_total += int(np.sum(counts**3 - counts))

    # Friedman test statistic S
    s_sum = sum(rank_sums[t] ** 2 for t in treatments)
    s_stat = (12.0 / (b_blocks * k_treat * (k_treat + 1.0))) * s_sum - 3.0 * b_blocks * (k_treat + 1.0)
    df = k_treat - 1

    # Tie adjustment
    c_factor = 1.0 - tie_term_total / float(b_blocks * k_treat * (k_treat**2 - 1.0)) if k_treat > 1 else 1.0
    s_adj = s_stat / c_factor if c_factor > 0 else s_stat

    p_val = float(1.0 - stats.chi2.cdf(s_stat, df))
    p_adj = float(1.0 - stats.chi2.cdf(s_adj, df))

    treatment_stats: List[Dict[str, Any]] = []
    for t in treatments:
        t_vals = [blocks_dict[b][t] for b in blocks_dict]
        treatment_stats.append({
            "treatment": t,
            "n": b_blocks,
            "median": float(np.median(t_vals)),
            "rank_sum": rank_sums[t],
        })

    return {
        "analysis": "friedman_test",
        "k_treatments": k_treat,
        "b_blocks": b_blocks,
        "df": df,
        "s_statistic": float(s_stat),
        "s_adjusted": float(s_adj),
        "p_value": p_val,
        "p_adjusted": p_adj,
        "treatment_stats": treatment_stats,
        "has_ties": bool(tie_term_total > 0),
    }


def runs_test(
    data: Sequence[Any],
    baseline: str = "mean",
    custom_baseline: Optional[float] = None,
) -> Dict[str, Any]:
    """Runs Test for Randomness of a Data Sequence."""
    arr = _clean_numeric(data)
    n_total = len(arr)
    if n_total < 2:
        raise ValueError("Runs test requires at least two numeric observations.")

    if baseline == "mean":
        k_thresh = float(np.mean(arr))
    elif custom_baseline is not None:
        k_thresh = float(custom_baseline)
    else:
        k_thresh = float(np.mean(arr))

    # Sequence of signs: True for >= K, False for < K
    signs = (arr >= k_thresh)
    n1 = int(np.sum(signs))
    n2 = int(np.sum(~signs))

    if n1 == 0 or n2 == 0:
        return {
            "analysis": "runs_test",
            "n": n_total,
            "k_threshold": k_thresh,
            "n_above_or_equal": n1,
            "n_below": n2,
            "runs": 1,
            "expected_runs": 1.0,
            "sd_runs": 0.0,
            "z": 0.0,
            "p_value": 1.0,
            "values": arr.tolist(),
            "baseline": baseline,
        }

    # Count runs (contiguous runs of True or False)
    runs = 1 + int(np.sum(signs[1:] != signs[:-1]))

    # Expected value and variance
    mu_runs = (2.0 * n1 * n2) / float(n_total) + 1.0
    var_runs = (2.0 * n1 * n2 * (2.0 * n1 * n2 - n_total)) / (float(n_total**2) * (n_total - 1.0))
    sd_runs = math.sqrt(max(1e-12, var_runs))

    z_val = (runs - mu_runs) / sd_runs if sd_runs > 0 else 0.0
    p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z_val))))

    return {
        "analysis": "runs_test",
        "n": n_total,
        "k_threshold": k_thresh,
        "n_above_or_equal": n1,
        "n_below": n2,
        "runs": runs,
        "expected_runs": float(mu_runs),
        "sd_runs": float(sd_runs),
        "z": float(z_val),
        "p_value": p_val,
        "values": arr.tolist(),
        "baseline": baseline,
    }


def paired_wilcoxon(
    sample1: Sequence[Any],
    sample2: Sequence[Any],
    test_diff: float = 0.0,
    alternative: str = "two_sided",
    conf_level: float = 0.95,
) -> Dict[str, Any]:
    """Paired Wilcoxon Signed Rank Test on differences (sample1 - sample2)."""
    # Align pairs
    clean_pairs: List[Tuple[float, float]] = []
    for v1, v2 in zip(sample1, sample2):
        if v1 is None or v2 is None:
            continue
        try:
            fv1 = float(v1)
            fv2 = float(v2)
            if math.isfinite(fv1) and math.isfinite(fv2):
                clean_pairs.append((fv1, fv2))
        except (ValueError, TypeError):
            continue

    if len(clean_pairs) == 0:
        raise ValueError("Paired Wilcoxon test requires at least one complete observation pair.")

    diffs = [p[0] - p[1] for p in clean_pairs]
    res = one_sample_wilcoxon(
        diffs,
        test_median=test_diff,
        alternative=alternative,
        conf_level=conf_level,
    )
    res["analysis"] = "paired_wilcoxon"
    res["n_pairs"] = len(clean_pairs)
    res["differences"] = diffs
    return res
