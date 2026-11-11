"""Process Capability Analysis (Normal Distribution) Engine for StatCraft.

Supports:
- Individual observations (subgroup size = 1) or Rational Subgroups (size > 1 or group column)
- Subgroups across rows of columns
- Lower Spec (LSL), Upper Spec (USL), and Target
- Historical Mean and Historical Standard Deviation
- Within-subgroup standard deviation estimators:
    * Subgroup size > 1: Pooled Standard Deviation, Rbar (average range), Sbar (average stdev)
    * Subgroup size = 1: AMR (Average Moving Range), MMR (Median Moving Range), SRMSSD (Square root of MSSD)
- Overall standard deviation with optional unbiasing (c4)
- Process capability indices: Cp, CPL, CPU, Cpk, CCpk, Cpm, Pp, PPL, PPU, Ppk
- Benchmark Z statistics (Z.LSL, Z.USL, Z.Bench)
- Observed, Expected Within, and Expected Overall PPM / Percent defect rates
- Confidence intervals (two-sided or one-sided) for capability indices
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.stats import norm, chi2


# Official published d2 table for n=2..50
D2_TABLE = {
    2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078,
    11: 3.173, 12: 3.258, 13: 3.336, 14: 3.407, 15: 3.472, 16: 3.532, 17: 3.588, 18: 3.640,
    19: 3.689, 20: 3.735, 21: 3.778, 22: 3.819, 23: 3.858, 24: 3.895, 25: 3.931,
    26: 3.964, 27: 3.997, 28: 4.027, 29: 4.057, 30: 4.086, 31: 4.113, 32: 4.139,
    33: 4.165, 34: 4.189, 35: 4.213, 36: 4.236, 37: 4.259, 38: 4.280, 39: 4.301,
    40: 4.322, 41: 4.341, 42: 4.361, 43: 4.379, 44: 4.398, 45: 4.415, 46: 4.433,
    47: 4.450, 48: 4.466, 49: 4.482, 50: 4.498
}

# d4 table for median moving range (span 2..10)
D4_TABLE = {
    2: 0.954, 3: 1.588, 4: 1.978, 5: 2.257, 6: 2.472, 7: 2.645, 8: 2.791, 9: 2.915, 10: 3.024
}


def c4(n: int) -> float:
    """Unbiasing constant c4 for sample size n."""
    if n <= 1:
        return 1.0
    return math.exp(0.5 * math.log(2.0 / (n - 1)) + math.lgamma(n / 2.0) - math.lgamma((n - 1) / 2.0))


def d2(n: int) -> float:
    """Expected value of relative range W = R / sigma for sample size n."""
    if n in D2_TABLE:
        return D2_TABLE[n]
    if n <= 1:
        return 1.0
    # Large n asymptotic approximation
    return math.sqrt(2.0 * math.log(n)) - (math.log(math.log(n)) + math.log(4.0 * math.pi)) / (2.0 * math.sqrt(2.0 * math.log(n)))


def d4(n: int) -> float:
    """Unbiasing constant for median range."""
    return D4_TABLE.get(n, d2(n))


def compute_capability_indices(
    mean: float,
    stdev: float,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    tolerance_k: float = 6.0
) -> Dict[str, Optional[float]]:
    """Calculates capability indices (Cp, CPL, CPU, Cpk, Cpm) for a given mean and stdev."""
    res: Dict[str, Optional[float]] = {
        "p": None,
        "pl": None,
        "pu": None,
        "pk": None,
        "cpm": None,
        "ccpk": None
    }
    if stdev <= 0:
        return res

    half_k = tolerance_k / 2.0

    if lsl is not None and usl is not None:
        res["p"] = (usl - lsl) / (tolerance_k * stdev)

    if lsl is not None:
        res["pl"] = (mean - lsl) / (half_k * stdev)

    if usl is not None:
        res["pu"] = (usl - mean) / (half_k * stdev)

    cand = [x for x in (res["pl"], res["pu"]) if x is not None]
    if cand:
        res["pk"] = min(cand)

    if target is not None:
        denom = 3.0 * math.sqrt(stdev**2 + (mean - target)**2)
        if denom > 0:
            if lsl is not None and usl is not None:
                res["cpm"] = (usl - lsl) / (2.0 * denom)
            elif lsl is not None:
                res["cpm"] = (mean - lsl) / denom
            elif usl is not None:
                res["cpm"] = (usl - mean) / denom

    if lsl is not None and usl is not None and res["pk"] is not None:
        m = (usl + lsl) / 2.0
        d = (usl - lsl) / 2.0
        if d > 0:
            res["ccpk"] = res["pk"] * (1.0 - abs(mean - m) / d)

    return res


def compute_ppm_and_z(
    clean_obs: List[float],
    mean: float,
    stdev: float,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    as_percent: bool = False
) -> Dict[str, Any]:
    """Computes PPM (or percent) defect rates and Z-benchmarks."""
    factor = 100.0 if as_percent else 1_000_000.0
    n = len(clean_obs)

    # Observed
    obs_below = sum(1 for x in clean_obs if x < lsl) if (lsl is not None and n > 0) else 0
    obs_above = sum(1 for x in clean_obs if x > usl) if (usl is not None and n > 0) else 0
    obs_total = obs_below + obs_above

    obs_ppm_below = (obs_below / n) * factor if n > 0 else 0.0
    obs_ppm_above = (obs_above / n) * factor if n > 0 else 0.0
    obs_ppm_total = (obs_total / n) * factor if n > 0 else 0.0

    # Expected
    exp_prob_below = float(norm.cdf((lsl - mean) / stdev)) if (lsl is not None and stdev > 0) else 0.0
    exp_prob_above = float(norm.sf((usl - mean) / stdev)) if (usl is not None and stdev > 0) else 0.0
    exp_prob_total = exp_prob_below + exp_prob_above

    exp_ppm_below = exp_prob_below * factor
    exp_ppm_above = exp_prob_above * factor
    exp_ppm_total = exp_prob_total * factor

    # Z values
    z_lsl = (mean - lsl) / stdev if (lsl is not None and stdev > 0) else None
    z_usl = (usl - mean) / stdev if (usl is not None and stdev > 0) else None
    
    # Benchmark Z: Z = norm.ppf(1 - total_failure_prob)
    z_bench = None
    if exp_prob_total > 0 and exp_prob_total < 1.0:
        # Inverting the survival probability avoids rounding 1 - p to 1.
        z_bench = float(norm.isf(exp_prob_total))
    # A rounded endpoint has no finite inverse; preserve it as unavailable.

    return {
        "observed_below": obs_ppm_below,
        "observed_above": obs_ppm_above,
        "observed_total": obs_ppm_total,
        "expected_below": exp_ppm_below,
        "expected_above": exp_ppm_above,
        "expected_total": exp_ppm_total,
        "z_lsl": z_lsl,
        "z_usl": z_usl,
        "z_bench": z_bench
    }


def compute_confidence_intervals(
    index_val: Optional[float],
    index_type: str,  # 'p' (Cp/Pp) or 'pk' (Cpk/Ppk)
    n_obs: int,
    df: int,
    confidence_level: float = 95.0,
    ci_type: str = "two_sided"  # 'two_sided', 'lower', 'upper'
) -> Tuple[Optional[float], Optional[float]]:
    """Calculates confidence bounds for Cp, Pp, Cpk, or Ppk."""
    if index_val is None or df <= 0 or n_obs <= 1:
        return (None, None)

    alpha = (100.0 - confidence_level) / 100.0

    if ci_type == "two_sided":
        a_low = alpha / 2.0
        a_high = 1.0 - alpha / 2.0
        z_crit = float(norm.ppf(1.0 - a_low))
    else:
        a_low = alpha
        a_high = 1.0 - alpha
        z_crit = float(norm.ppf(1.0 - alpha))

    if index_type == "p":
        # Chi-square exact interval for Cp / Pp:
        # Lower bound = Cp * sqrt(chi2(alpha/2, df) / df)
        # Upper bound = Cp * sqrt(chi2(1-alpha/2, df) / df)
        chi2_low = float(chi2.ppf(a_low, df))
        chi2_high = float(chi2.ppf(a_high, df))
        low = index_val * math.sqrt(chi2_low / df) if chi2_low > 0 else 0.0
        high = index_val * math.sqrt(chi2_high / df) if chi2_high > 0 else None
        if ci_type == "lower":
            return (low, None)
        elif ci_type == "upper":
            return (None, high)
        return (low, high)

    elif index_type == "pk":
        # Normal approximation interval for Cpk / Ppk:
        # SE = sqrt(1 / (9 * N) + Cpk^2 / (2 * df))
        se = math.sqrt(1.0 / (9.0 * n_obs) + (index_val**2) / (2.0 * df))
        low = index_val - z_crit * se
        high = index_val + z_crit * se
        if ci_type == "lower":
            return (low, None)
        elif ci_type == "upper":
            return (None, high)
        return (low, high)

    return (None, None)


def run_normal_capability(
    data: Union[List[Any], np.ndarray],
    subgroup_spec: Any = 1,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    historical_mean: Optional[float] = None,
    historical_stdev: Optional[float] = None,
    estimate_method_gt1: str = "pooled",  # 'pooled', 'rbar', 'sbar'
    estimate_method_eq1: str = "amr",     # 'amr', 'mmr', 'srmssd'
    moving_range_len: int = 2,
    unbiased_within: bool = True,
    unbiased_overall: bool = False,
    tolerance_k: float = 6.0,
    display_unit: str = "ppm",            # 'ppm', 'percent'
    stats_type: str = "capability",       # 'capability', 'zbench'
    include_ci: bool = False,
    confidence_level: float = 95.0,
    ci_type: str = "two_sided",           # 'two_sided', 'lower', 'upper'
    variable_name: str = "Data",
    title: Optional[str] = None,
    analysis_mode: str = "normal",        # 'normal', 'between_within'
    naming_convention: str = "classical", # 'classical', 'aiag_vda'
    study_type: str = "process"           # 'process', 'machine'
) -> Dict[str, Any]:
    """Executes full Process Capability Analysis (Normal Distribution)."""

    if lsl is None and usl is None:
        raise ValueError("Enter at least one specification limit (Lower spec or Upper spec).")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("Lower specification limit must be strictly less than upper specification limit.")

    # Flatten and clean data
    # Check if data is across rows of columns (2D array/list of lists)
    is_across_rows = False
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], (list, tuple, np.ndarray)):
        is_across_rows = True

    subgroups: List[List[float]] = []
    flat_clean: List[float] = []

    if is_across_rows:
        # Data is list of rows or list of columns
        # In StatCraft "subgroups across rows of": each row across the chosen columns is a subgroup.
        num_rows = len(data)
        for r in data:
            row_clean = []
            for val in r:
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    try:
                        fval = float(val)
                        if math.isfinite(fval):
                            row_clean.append(fval)
                            flat_clean.append(fval)
                    except (ValueError, TypeError):
                        pass
            if row_clean:
                subgroups.append(row_clean)
    else:
        # Single column
        raw_vals = list(data)
        # Check subgroup_spec: int constant or list/array of subgroup indicators
        if isinstance(subgroup_spec, (list, tuple, np.ndarray)):
            # Subgroup column provided
            sub_col = list(subgroup_spec)
            if len(sub_col) != len(raw_vals):
                raise ValueError("Subgroup column length must match data column length.")
            # Group by consecutive matching indicator or categorical indicator
            # In StatCraft, subgroup column groups contiguous or unique ids
            current_group: List[float] = []
            current_id = None
            for v, g in zip(raw_vals, sub_col):
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                try:
                    fv = float(v)
                    if not math.isfinite(fv):
                        continue
                except (ValueError, TypeError):
                    continue
                flat_clean.append(fv)
                if current_id is None or g != current_id:
                    if current_group:
                        subgroups.append(current_group)
                    current_group = [fv]
                    current_id = g
                else:
                    current_group.append(fv)
            if current_group:
                subgroups.append(current_group)
        else:
            # Subgroup size constant
            try:
                sub_size = int(subgroup_spec)
            except (ValueError, TypeError):
                sub_size = 1

            if sub_size < 1:
                sub_size = 1

            # Extract clean observations
            for v in raw_vals:
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                try:
                    fv = float(v)
                    if math.isfinite(fv):
                        flat_clean.append(fv)
                except (ValueError, TypeError):
                    continue

            if sub_size == 1:
                subgroups = [[x] for x in flat_clean]
            else:
                # Partition into chunks of sub_size
                for i in range(0, len(flat_clean), sub_size):
                    chunk = flat_clean[i:i + sub_size]
                    if chunk:
                        subgroups.append(chunk)

    n_total = len(flat_clean)
    if n_total < 2:
        raise ValueError("Capability analysis requires at least two non-missing numeric observations.")

    # 1. Overall mean and standard deviation
    sample_mean = float(np.mean(flat_clean))
    mean = historical_mean if historical_mean is not None else sample_mean

    sample_stdev_overall = float(np.std(flat_clean, ddof=1))
    if unbiased_overall and n_total > 1:
        stdev_overall = sample_stdev_overall / c4(n_total)
    else:
        stdev_overall = sample_stdev_overall

    if historical_stdev is not None:
        stdev_overall = historical_stdev

    # 2. Within-subgroup standard deviation estimation
    # Check average subgroup size
    group_sizes = [len(g) for g in subgroups]
    max_size = max(group_sizes) if group_sizes else 1
    min_size = min(group_sizes) if group_sizes else 1
    avg_size = np.mean(group_sizes) if group_sizes else 1

    stdev_within: float = 0.0
    within_df: int = 1

    if max_size == 1:
        # Subgroup size = 1 (Individuals)
        span = max(2, moving_range_len)
        if len(flat_clean) >= span:
            moving_ranges = [
                max(flat_clean[i - span + 1:i + 1]) - min(flat_clean[i - span + 1:i + 1])
                for i in range(span - 1, len(flat_clean))
            ]
        else:
            moving_ranges = [abs(flat_clean[i] - flat_clean[i - 1]) for i in range(1, len(flat_clean))]
        
        if estimate_method_eq1.lower() == "mmr":
            med_mr = float(np.median(moving_ranges))
            d4_val = d4(span)
            stdev_within = med_mr / d4_val if d4_val > 0 else sample_stdev_overall
        elif estimate_method_eq1.lower() == "srmssd":
            # Square root of MSSD
            diff_sq = sum((flat_clean[i] - flat_clean[i - 1])**2 for i in range(1, len(flat_clean)))
            stdev_within = math.sqrt(diff_sq / (2.0 * (len(flat_clean) - 1)))
        else:
            # Default: AMR (Average Moving Range)
            avg_mr = float(np.mean(moving_ranges))
            d2_val = d2(span)
            stdev_within = avg_mr / d2_val if d2_val > 0 else sample_stdev_overall

        within_df = max(1, len(flat_clean) - 1)
    else:
        # Subgroup size > 1
        method = estimate_method_gt1.lower()
        if method == "rbar":
            # Rbar method
            ranges = [max(g) - min(g) for g in subgroups if len(g) > 1]
            if ranges:
                # If all equal size:
                if min_size == max_size:
                    avg_r = float(np.mean(ranges))
                    stdev_within = avg_r / d2(max_size)
                else:
                    # Varying subgroup sizes: weighted by d2
                    r_sum = sum(ranges)
                    d2_sum = sum(d2(len(g)) for g in subgroups if len(g) > 1)
                    stdev_within = r_sum / d2_sum if d2_sum > 0 else sample_stdev_overall
            else:
                stdev_within = sample_stdev_overall
            within_df = sum(len(g) - 1 for g in subgroups)

        elif method == "sbar":
            # Sbar method
            stdevs = [float(np.std(g, ddof=1)) for g in subgroups if len(g) > 1]
            if stdevs:
                if min_size == max_size:
                    avg_s = float(np.mean(stdevs))
                    c4_val = c4(max_size) if unbiased_within else 1.0
                    stdev_within = avg_s / c4_val if c4_val > 0 else sample_stdev_overall
                else:
                    c4_sum = sum(c4(len(g)) for g in subgroups if len(g) > 1)
                    stdev_within = sum(stdevs) / c4_sum if c4_sum > 0 else sample_stdev_overall
            else:
                stdev_within = sample_stdev_overall
            within_df = sum(len(g) - 1 for g in subgroups)

        else:
            # Default: Pooled standard deviation
            df_total = sum(len(g) - 1 for g in subgroups)
            sum_ss = sum((len(g) - 1) * (float(np.std(g, ddof=1))**2) for g in subgroups if len(g) > 1)
            if df_total > 0:
                s_pooled = math.sqrt(sum_ss / df_total)
                c4_pool = c4(df_total + 1) if unbiased_within else 1.0
                stdev_within = s_pooled / c4_pool if c4_pool > 0 else s_pooled
            else:
                stdev_within = sample_stdev_overall
            within_df = max(1, df_total)

    if stdev_within <= 0:
        stdev_within = 1e-9
    if stdev_overall <= 0:
        stdev_overall = 1e-9

    # Between/Within calculation
    stdev_between: Optional[float] = None
    stdev_between_within: Optional[float] = None
    target_within_sd = stdev_within

    if analysis_mode == "between_within":
        if len(subgroups) < 2 or max_size < 2:
            raise ValueError("Between/Within capability analysis requires at least two subgroups with size > 1.")

        sub_means = [float(np.mean(g)) for g in subgroups]
        k_subs = len(subgroups)
        mr_span = max(2, min(int(moving_range_len), k_subs))
        sub_mr = [
            max(sub_means[i:i + mr_span]) - min(sub_means[i:i + mr_span])
            for i in range(len(sub_means) - mr_span + 1)
        ]
        if not sub_mr:
            sub_mr = [abs(sub_means[i] - sub_means[i - 1]) for i in range(1, len(sub_means))]

        avg_mr = float(np.mean(sub_mr)) if sub_mr else 0.0
        d2_val = d2(mr_span)
        sigma_xbar = avg_mr / d2_val if d2_val > 0 else float(np.std(sub_means, ddof=1))

        if min_size == max_size:
            n_eff = float(max_size)
        else:
            sum_n = sum(group_sizes)
            sum_n2 = sum(sz * sz for sz in group_sizes)
            n_eff = (sum_n - sum_n2 / sum_n) / (k_subs - 1) if k_subs > 1 else float(avg_size)
            if n_eff <= 0:
                n_eff = float(avg_size)

        var_xbar = sigma_xbar ** 2
        var_within_part = (stdev_within ** 2) / n_eff
        var_between = max(0.0, var_xbar - var_within_part)
        stdev_between = math.sqrt(var_between)
        stdev_between_within = math.sqrt(var_between + stdev_within ** 2)
        if stdev_between_within <= 0:
            stdev_between_within = 1e-9
        target_within_sd = stdev_between_within

    # 3. Capability indices
    within_indices = compute_capability_indices(
        mean=mean,
        stdev=target_within_sd,
        lsl=lsl,
        usl=usl,
        target=target,
        tolerance_k=tolerance_k
    )

    overall_indices = compute_capability_indices(
        mean=mean,
        stdev=stdev_overall,
        lsl=lsl,
        usl=usl,
        target=target,
        tolerance_k=tolerance_k
    )

    # 4. Confidence intervals
    overall_df = max(1, n_total - 1)
    
    ci_cp = compute_confidence_intervals(within_indices["p"], "p", n_total, within_df, confidence_level, ci_type)
    ci_cpk = compute_confidence_intervals(within_indices["pk"], "pk", n_total, within_df, confidence_level, ci_type)
    ci_pp = compute_confidence_intervals(overall_indices["p"], "p", n_total, overall_df, confidence_level, ci_type)
    ci_ppk = compute_confidence_intervals(overall_indices["pk"], "pk", n_total, overall_df, confidence_level, ci_type)

    # 5. PPM and Benchmarks
    as_pct = (display_unit.lower() == "percent")
    within_ppm = compute_ppm_and_z(flat_clean, mean, target_within_sd, lsl, usl, as_percent=as_pct)
    overall_ppm = compute_ppm_and_z(flat_clean, mean, stdev_overall, lsl, usl, as_percent=as_pct)

    is_bw = (analysis_mode == "between_within")
    is_machine = (study_type == "machine")
    is_aiag_vda = (naming_convention == "aiag_vda")

    if is_machine:
        default_title = f"Machine Capability Report for {variable_name}"
    elif is_bw and is_aiag_vda:
        default_title = f"Between/Within Capability (AIAG/VDA) Report for {variable_name}"
    elif is_bw:
        default_title = f"Between/Within Capability Report for {variable_name}"
    else:
        default_title = f"Process Capability Report for {variable_name}"
    report_title = title or default_title

    return {
        "title": report_title,
        "variable_name": variable_name,
        "analysis_mode": analysis_mode,
        "naming_convention": naming_convention,
        "study_type": study_type,
        "sample_n": n_total,
        "subgroup_count": len(subgroups),
        "subgroup_avg_size": avg_size,
        "mean": mean,
        "sample_mean": sample_mean,
        "stdev_within": stdev_within,
        "stdev_between": stdev_between,
        "stdev_between_within": stdev_between_within,
        "stdev_overall": stdev_overall,
        "lsl": lsl,
        "usl": usl,
        "target": target,
        "tolerance_k": tolerance_k,
        "display_unit": display_unit,
        "stats_type": stats_type,
        "include_ci": include_ci,
        "confidence_level": confidence_level,
        "ci_type": ci_type,
        "observations": flat_clean,
        "subgroups": subgroups,
        # Within stats
        "cp": within_indices["p"],
        "cpl": within_indices["pl"],
        "cpu": within_indices["pu"],
        "cpk": within_indices["pk"],
        "ccpk": within_indices["ccpk"],
        "cpm": within_indices["cpm"],
        "ci_cp": ci_cp,
        "ci_cpk": ci_cpk,
        # Machine Capability (AIAG/VDA)
        "cm": within_indices["p"] if is_machine else None,
        "cml": within_indices["pl"] if is_machine else None,
        "cmu": within_indices["pu"] if is_machine else None,
        "cmk": within_indices["pk"] if is_machine else None,
        "ci_cm": ci_cp if is_machine else None,
        "ci_cmk": ci_cpk if is_machine else None,
        # Between/Within Capability (AIAG/VDA)
        "cbw": within_indices["p"] if (is_bw and is_aiag_vda) else None,
        "cbwl": within_indices["pl"] if (is_bw and is_aiag_vda) else None,
        "cbwu": within_indices["pu"] if (is_bw and is_aiag_vda) else None,
        "cbwk": within_indices["pk"] if (is_bw and is_aiag_vda) else None,
        "ci_cbw": ci_cp if (is_bw and is_aiag_vda) else None,
        "ci_cbwk": ci_cpk if (is_bw and is_aiag_vda) else None,
        # Overall stats
        "pp": overall_indices["p"],
        "ppl": overall_indices["pl"],
        "ppu": overall_indices["pu"],
        "ppk": overall_indices["pk"],
        "ci_pp": ci_pp,
        "ci_ppk": ci_ppk,
        # PPM and Performance
        "within_perf": within_ppm,
        "overall_perf": overall_ppm,
        "observed_perf": {
            "below": within_ppm["observed_below"],
            "above": within_ppm["observed_above"],
            "total": within_ppm["observed_total"]
        }
    }
