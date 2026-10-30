"""Equivalence testing statistical engine for StatCraft.

Provides 1:1 statistical parity with StatCraft for:
- 1-Sample Equivalence Test
- 2-Sample Equivalence Test
- Paired Equivalence Test
- 2x2 Crossover Design Equivalence Test

Implements Schuirmann's Two One-Sided Tests (TOST) procedure and (1 - 2*alpha)
confidence intervals for difference and ratio hypotheses.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


def _clean_numeric_vector(vals: List[Any]) -> np.ndarray:
    """Filter list to finite float numpy array."""
    cleaned = []
    for v in vals:
        if v is None or v == "" or isinstance(v, bool):
            continue
        try:
            f = float(v)
            if math.isfinite(f):
                cleaned.append(f)
        except (ValueError, TypeError):
            continue
    return np.array(cleaned, dtype=np.float64)


# ==============================================================================
# 1. 1-SAMPLE EQUIVALENCE TEST
# ==============================================================================

def one_sample_equivalence(
    data: List[Any],
    target: float = 0.0,
    lower_margin: float = -1.0,
    upper_margin: float = 1.0,
    alpha: float = 0.05,
    hypothesis_type: str = "difference",  # 'difference' or 'ratio'
) -> Dict[str, Any]:
    """Perform 1-sample equivalence test against target value matching StatCraft.
    
    Tests whether the mean (or mean - target) is between lower_margin and upper_margin.
    If hypothesis_type is 'ratio', data and target are evaluated on the ratio scale (via log transformation).
    """
    x = _clean_numeric_vector(data)
    n = len(x)
    if n < 2:
        raise ValueError("1-Sample Equivalence test requires at least 2 complete observations.")

    if lower_margin >= upper_margin:
        raise ValueError("Lower equivalence margin must be strictly less than upper margin.")

    is_ratio = hypothesis_type.lower() == "ratio"
    if is_ratio:
        if np.any(x <= 0) or target <= 0 or lower_margin <= 0 or upper_margin <= 0:
            raise ValueError("Ratio equivalence requires strictly positive values and margins.")
        log_x = np.log(x)
        log_target = math.log(target)
        log_lower = math.log(lower_margin)
        log_upper = math.log(upper_margin)
        
        # Working on log-transformed data: log(mean) - log(target)
        mean_log = float(np.mean(log_x))
        sd_log = float(np.std(log_x, ddof=1))
        se_log = sd_log / math.sqrt(n)
        df = n - 1

        diff_log = mean_log - log_target
        # TOST t-statistics
        t1 = (diff_log - log_lower) / se_log if se_log > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))  # H01: diff <= log_lower vs H11: diff > log_lower

        t2 = (diff_log - log_upper) / se_log if se_log > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))  # H02: diff >= log_upper vs H12: diff < log_upper

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        # 100*(1 - 2*alpha)% CI on log scale, then exponentiate
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower_log = diff_log - t_crit * se_log
        ci_upper_log = diff_log + t_crit * se_log

        ci_lower = math.exp(ci_lower_log)
        ci_upper = math.exp(ci_upper_log)
        point_estimate = math.exp(diff_log)
        mean_val = float(np.mean(x))
        sd_val = float(np.std(x, ddof=1))
        se_val = sd_val / math.sqrt(n)

    else:
        # Difference scale: mean - target
        mean_val = float(np.mean(x))
        sd_val = float(np.std(x, ddof=1))
        se_val = sd_val / math.sqrt(n)
        df = n - 1
        diff = mean_val - target

        t1 = (diff - lower_margin) / se_val if se_val > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))  # H01: mean - target <= lower vs H1: > lower

        t2 = (diff - upper_margin) / se_val if se_val > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))  # H02: mean - target >= upper vs H1: < upper

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = diff - t_crit * se_val
        ci_upper = diff + t_crit * se_val
        point_estimate = diff

    conf_level = (1.0 - 2.0 * alpha) * 100.0

    return {
        "analysis": "one_sample_equivalence",
        "hypothesis_type": hypothesis_type.lower(),
        "n": n,
        "mean": mean_val,
        "stdev": sd_val,
        "se_mean": se_val,
        "target": target,
        "lower_margin": lower_margin,
        "upper_margin": upper_margin,
        "alpha": alpha,
        "conf_level": conf_level,
        "point_estimate": point_estimate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "df": df,
        "t1": t1,
        "p1": p1,
        "t2": t2,
        "p2": p2,
        "p_value": p_value,
        "is_equivalent": is_equivalent,
        "values": x.tolist(),
    }


# ==============================================================================
# 2. 2-SAMPLE EQUIVALENCE TEST
# ==============================================================================

def two_sample_equivalence(
    sample1: List[Any],
    sample2: List[Any],
    name1: str = "Test",
    name2: str = "Reference",
    lower_margin: float = -1.0,
    upper_margin: float = 1.0,
    alpha: float = 0.05,
    equal_variances: bool = False,
    hypothesis_type: str = "difference",
) -> Dict[str, Any]:
    """Perform 2-sample equivalence test matching StatCraft."""
    x1 = _clean_numeric_vector(sample1)
    x2 = _clean_numeric_vector(sample2)
    n1, n2 = len(x1), len(x2)
    if n1 < 2 or n2 < 2:
        raise ValueError("2-Sample Equivalence test requires at least 2 observations in each sample.")
    if lower_margin >= upper_margin:
        raise ValueError("Lower equivalence margin must be strictly less than upper margin.")

    is_ratio = hypothesis_type.lower() == "ratio"

    if is_ratio:
        if np.any(x1 <= 0) or np.any(x2 <= 0) or lower_margin <= 0 or upper_margin <= 0:
            raise ValueError("Ratio equivalence requires strictly positive values and margins.")
        log_x1 = np.log(x1)
        log_x2 = np.log(x2)
        mean1_log = float(np.mean(log_x1))
        mean2_log = float(np.mean(log_x2))
        v1_log = float(np.var(log_x1, ddof=1))
        v2_log = float(np.var(log_x2, ddof=1))
        diff_log = mean1_log - mean2_log

        if equal_variances:
            sp2 = ((n1 - 1) * v1_log + (n2 - 1) * v2_log) / (n1 + n2 - 2)
            se_diff = math.sqrt(sp2 * (1.0 / n1 + 1.0 / n2))
            df = n1 + n2 - 2
        else:
            se_diff = math.sqrt(v1_log / n1 + v2_log / n2)
            # Welch-Satterthwaite df
            num = (v1_log / n1 + v2_log / n2) ** 2
            den = ((v1_log / n1) ** 2) / (n1 - 1) + ((v2_log / n2) ** 2) / (n2 - 1)
            df = num / den if den > 0 else (n1 + n2 - 2)

        log_lower = math.log(lower_margin)
        log_upper = math.log(upper_margin)

        t1 = (diff_log - log_lower) / se_diff if se_diff > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))

        t2 = (diff_log - log_upper) / se_diff if se_diff > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = math.exp(diff_log - t_crit * se_diff)
        ci_upper = math.exp(diff_log + t_crit * se_diff)
        point_estimate = math.exp(diff_log)

        mean1 = float(np.mean(x1))
        mean2 = float(np.mean(x2))
        sd1 = float(np.std(x1, ddof=1))
        sd2 = float(np.std(x2, ddof=1))

    else:
        mean1 = float(np.mean(x1))
        mean2 = float(np.mean(x2))
        sd1 = float(np.std(x1, ddof=1))
        sd2 = float(np.std(x2, ddof=1))
        v1 = sd1 ** 2
        v2 = sd2 ** 2
        diff = mean1 - mean2

        if equal_variances:
            sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
            se_diff = math.sqrt(sp2 * (1.0 / n1 + 1.0 / n2))
            df = n1 + n2 - 2
        else:
            se_diff = math.sqrt(v1 / n1 + v2 / n2)
            num = (v1 / n1 + v2 / n2) ** 2
            den = ((v1 / n1) ** 2) / (n1 - 1) + ((v2 / n2) ** 2) / (n2 - 1)
            df = num / den if den > 0 else (n1 + n2 - 2)

        t1 = (diff - lower_margin) / se_diff if se_diff > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))

        t2 = (diff - upper_margin) / se_diff if se_diff > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = diff - t_crit * se_diff
        ci_upper = diff + t_crit * se_diff
        point_estimate = diff

    conf_level = (1.0 - 2.0 * alpha) * 100.0

    return {
        "analysis": "two_sample_equivalence",
        "hypothesis_type": hypothesis_type.lower(),
        "name1": name1,
        "name2": name2,
        "n1": n1,
        "n2": n2,
        "mean1": mean1,
        "mean2": mean2,
        "stdev1": sd1,
        "stdev2": sd2,
        "se_mean1": sd1 / math.sqrt(n1),
        "se_mean2": sd2 / math.sqrt(n2),
        "equal_variances": equal_variances,
        "lower_margin": lower_margin,
        "upper_margin": upper_margin,
        "alpha": alpha,
        "conf_level": conf_level,
        "point_estimate": point_estimate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "df": df,
        "se_diff": se_diff,
        "t1": t1,
        "p1": p1,
        "t2": t2,
        "p2": p2,
        "p_value": p_value,
        "is_equivalent": is_equivalent,
        "values1": x1.tolist(),
        "values2": x2.tolist(),
    }


# ==============================================================================
# 3. PAIRED EQUIVALENCE TEST
# ==============================================================================

def paired_equivalence(
    sample1: List[Any],
    sample2: List[Any],
    name1: str = "Test",
    name2: str = "Reference",
    lower_margin: float = -1.0,
    upper_margin: float = 1.0,
    alpha: float = 0.05,
    hypothesis_type: str = "difference",
) -> Dict[str, Any]:
    """Perform paired equivalence test matching StatCraft."""
    n_pairs = min(len(sample1), len(sample2))
    cleaned_s1 = []
    cleaned_s2 = []
    for i in range(n_pairs):
        v1, v2 = sample1[i], sample2[i]
        if v1 is None or v2 is None or v1 == "" or v2 == "" or isinstance(v1, bool) or isinstance(v2, bool):
            continue
        try:
            f1, f2 = float(v1), float(v2)
            if math.isfinite(f1) and math.isfinite(f2):
                cleaned_s1.append(f1)
                cleaned_s2.append(f2)
        except (ValueError, TypeError):
            continue

    n = len(cleaned_s1)
    if n < 2:
        raise ValueError("Paired Equivalence test requires at least 2 complete pairs.")
    if lower_margin >= upper_margin:
        raise ValueError("Lower equivalence margin must be strictly less than upper margin.")

    s1 = np.array(cleaned_s1)
    s2 = np.array(cleaned_s2)
    is_ratio = hypothesis_type.lower() == "ratio"

    if is_ratio:
        if np.any(s1 <= 0) or np.any(s2 <= 0) or lower_margin <= 0 or upper_margin <= 0:
            raise ValueError("Ratio equivalence requires strictly positive values and margins.")
        log_diff = np.log(s1) - np.log(s2)
        mean_log_d = float(np.mean(log_diff))
        sd_log_d = float(np.std(log_diff, ddof=1))
        se_log_d = sd_log_d / math.sqrt(n)
        df = n - 1

        log_lower = math.log(lower_margin)
        log_upper = math.log(upper_margin)

        t1 = (mean_log_d - log_lower) / se_log_d if se_log_d > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))

        t2 = (mean_log_d - log_upper) / se_log_d if se_log_d > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = math.exp(mean_log_d - t_crit * se_log_d)
        ci_upper = math.exp(mean_log_d + t_crit * se_log_d)
        point_estimate = math.exp(mean_log_d)

    else:
        diffs = s1 - s2
        mean_d = float(np.mean(diffs))
        sd_d = float(np.std(diffs, ddof=1))
        se_d = sd_d / math.sqrt(n)
        df = n - 1

        t1 = (mean_d - lower_margin) / se_d if se_d > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))

        t2 = (mean_d - upper_margin) / se_d if se_d > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = mean_d - t_crit * se_d
        ci_upper = mean_d + t_crit * se_d
        point_estimate = mean_d

    conf_level = (1.0 - 2.0 * alpha) * 100.0

    return {
        "analysis": "paired_equivalence",
        "hypothesis_type": hypothesis_type.lower(),
        "name1": name1,
        "name2": name2,
        "n": n,
        "mean1": float(np.mean(s1)),
        "mean2": float(np.mean(s2)),
        "stdev1": float(np.std(s1, ddof=1)),
        "stdev2": float(np.std(s2, ddof=1)),
        "mean_diff": float(np.mean(s1 - s2)),
        "stdev_diff": float(np.std(s1 - s2, ddof=1)),
        "se_diff": float(np.std(s1 - s2, ddof=1)) / math.sqrt(n),
        "lower_margin": lower_margin,
        "upper_margin": upper_margin,
        "alpha": alpha,
        "conf_level": conf_level,
        "point_estimate": point_estimate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "df": df,
        "t1": t1,
        "p1": p1,
        "t2": t2,
        "p2": p2,
        "p_value": p_value,
        "is_equivalent": is_equivalent,
        "values1": s1.tolist(),
        "values2": s2.tolist(),
    }


# ==============================================================================
# 4. 2x2 CROSSOVER DESIGN EQUIVALENCE TEST
# ==============================================================================

def crossover_equivalence(
    response: List[Any],
    sequence: List[Any],
    period: List[Any],
    subject: List[Any],
    treatment: List[Any],
    test_treatment: Optional[str] = None,
    ref_treatment: Optional[str] = None,
    lower_margin: float = -1.0,
    upper_margin: float = 1.0,
    alpha: float = 0.05,
    hypothesis_type: str = "difference",
) -> Dict[str, Any]:
    """Perform equivalence test for 2x2 crossover design matching StatCraft."""
    n_rows = len(response)
    if not (len(sequence) == len(period) == len(subject) == len(treatment) == n_rows):
        raise ValueError("All column inputs for Crossover Design must have identical lengths.")

    # Filter complete observations
    clean_y, clean_seq, clean_per, clean_sub, clean_trt = [], [], [], [], []
    for i in range(n_rows):
        y_val = response[i]
        s_val = sequence[i]
        p_val = period[i]
        sub_val = subject[i]
        t_val = treatment[i]
        if any(v is None or v == "" or isinstance(v, bool) for v in (y_val, s_val, p_val, sub_val, t_val)):
            continue
        try:
            fy = float(y_val)
            if math.isfinite(fy):
                clean_y.append(fy)
                clean_seq.append(str(s_val).strip())
                clean_per.append(str(p_val).strip())
                clean_sub.append(str(sub_val).strip())
                clean_trt.append(str(t_val).strip())
        except (ValueError, TypeError):
            continue

    n = len(clean_y)
    if n < 4:
        raise ValueError("Crossover equivalence requires at least 4 complete observations.")

    unique_trts = sorted(list(set(clean_trt)))
    if len(unique_trts) != 2:
        raise ValueError("2x2 Crossover design requires exactly 2 treatments.")

    if test_treatment is None or test_treatment not in unique_trts:
        test_trt = unique_trts[0]
        ref_trt = unique_trts[1]
    else:
        test_trt = test_treatment
        ref_trt = ref_treatment if ref_treatment in unique_trts and ref_treatment != test_trt else ([t for t in unique_trts if t != test_trt][0])

    is_ratio = hypothesis_type.lower() == "ratio"
    y_work = np.log(np.array(clean_y)) if is_ratio else np.array(clean_y)

    # Standard 2x2 Crossover ANOVA:
    # Model: Y_ijk = mu + S_i + Subject(S)_k(i) + Period_j + Treatment_t + e_ijk
    # Subject differences: within-subject response difference d_k = Y(Test) - Y(Ref)
    subjects = sorted(list(set(clean_sub)))
    sub_diffs = []
    sub_seqs = []
    
    for sub in subjects:
        sub_indices = [idx for idx, s in enumerate(clean_sub) if s == sub]
        if len(sub_indices) == 2:
            idx1, idx2 = sub_indices[0], sub_indices[1]
            t1, t2 = clean_trt[idx1], clean_trt[idx2]
            if {t1, t2} == {test_trt, ref_trt}:
                y_test = y_work[idx1] if t1 == test_trt else y_work[idx2]
                y_ref = y_work[idx2] if t1 == test_trt else y_work[idx1]
                sub_diffs.append(y_test - y_ref)
                sub_seqs.append(clean_seq[idx1])

    n_subs = len(sub_diffs)
    if n_subs < 3:
        raise ValueError("Crossover design requires at least 3 subjects with both periods observed.")

    # Two-sample comparison of differences between sequences (accounts for period effect)
    unique_seqs = sorted(list(set(sub_seqs)))
    if len(unique_seqs) == 2:
        diffs1 = [d for d, s in zip(sub_diffs, sub_seqs) if s == unique_seqs[0]]
        diffs2 = [d for d, s in zip(sub_diffs, sub_seqs) if s == unique_seqs[1]]
        n_s1, n_s2 = len(diffs1), len(diffs2)
        mean_d1 = np.mean(diffs1) if n_s1 > 0 else 0.0
        mean_d2 = np.mean(diffs2) if n_s2 > 0 else 0.0
        v_d1 = np.var(diffs1, ddof=1) if n_s1 > 1 else 0.0
        v_d2 = np.var(diffs2, ddof=1) if n_s2 > 1 else 0.0
        
        df = max(1, n_s1 + n_s2 - 2)
        sp2 = ((n_s1 - 1) * v_d1 + (n_s2 - 1) * v_d2) / df if df > 0 else 1.0
        # Treatment difference estimate = 0.5 * (mean_d1 - mean_d2) or adjusted mean
        trt_diff = 0.5 * (mean_d1 + mean_d2)
        se_trt = math.sqrt(sp2 * 0.25 * (1.0 / n_s1 + 1.0 / n_s2)) if n_s1 > 0 and n_s2 > 0 else 1.0
    else:
        # Single sequence fallback
        df = max(1, n_subs - 1)
        trt_diff = float(np.mean(sub_diffs))
        se_trt = float(np.std(sub_diffs, ddof=1)) / math.sqrt(n_subs)

    if is_ratio:
        log_lower = math.log(lower_margin)
        log_upper = math.log(upper_margin)

        t1 = (trt_diff - log_lower) / se_trt if se_trt > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))

        t2 = (trt_diff - log_upper) / se_trt if se_trt > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = math.exp(trt_diff - t_crit * se_trt)
        ci_upper = math.exp(trt_diff + t_crit * se_trt)
        point_estimate = math.exp(trt_diff)
    else:
        t1 = (trt_diff - lower_margin) / se_trt if se_trt > 0 else 0.0
        p1 = 1.0 - float(stats.t.cdf(t1, df))

        t2 = (trt_diff - upper_margin) / se_trt if se_trt > 0 else 0.0
        p2 = float(stats.t.cdf(t2, df))

        p_value = max(p1, p2)
        is_equivalent = p_value < alpha

        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = trt_diff - t_crit * se_trt
        ci_upper = trt_diff + t_crit * se_trt
        point_estimate = trt_diff

    conf_level = (1.0 - 2.0 * alpha) * 100.0

    return {
        "analysis": "crossover_equivalence",
        "hypothesis_type": hypothesis_type.lower(),
        "test_treatment": test_trt,
        "ref_treatment": ref_trt,
        "n_obs": n,
        "n_subjects": n_subs,
        "lower_margin": lower_margin,
        "upper_margin": upper_margin,
        "alpha": alpha,
        "conf_level": conf_level,
        "point_estimate": point_estimate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "df": df,
        "se_trt": se_trt,
        "t1": t1,
        "p1": p1,
        "t2": t2,
        "p2": p2,
        "p_value": p_value,
        "is_equivalent": is_equivalent,
    }
