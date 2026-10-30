"""Statistical calculations for native StatCraft Two-Sample t test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from scipy import stats
import numpy as np


def two_sample_t_settings(
    data_format: int = 1,  # 0: Stacked, 1: Unstacked, 2: Summarized
    sample1_col: Optional[int] = None,
    sample2_col: Optional[int] = None,
    samples_col: Optional[int] = None,
    sample_ids_col: Optional[int] = None,
    summarized: Optional[Dict[str, float]] = None,
    confidence_level: float = 95.0,
    hypothesized_difference: float = 0.0,
    alternative: str = "not_equal",  # "not_equal", "less_than", "greater_than"
    assume_equal_variances: bool = False,
    graphs: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    return {
        "data_format": int(data_format),
        "sample1_col": sample1_col,
        "sample2_col": sample2_col,
        "samples_col": samples_col,
        "sample_ids_col": sample_ids_col,
        "summarized": summarized or {
            "n1": 10, "mean1": 0.0, "sd1": 1.0,
            "n2": 10, "mean2": 0.0, "sd2": 1.0,
        },
        "confidence_level": float(confidence_level),
        "hypothesized_difference": float(hypothesized_difference),
        "alternative": alternative,
        "assume_equal_variances": bool(assume_equal_variances),
        "graphs": graphs or {"individual_value_plot": True, "boxplot": True},
    }


def run_two_sample_t(
    worksheet_or_samples: Any,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Two-Sample t test with exact StatCraft formulas."""
    data_format = settings.get("data_format", 1)
    conf_level = float(settings.get("confidence_level", 95.0))
    if not (0.0 < conf_level < 100.0):
        conf_level = 95.0
    alpha = (100.0 - conf_level) / 100.0

    hyp_diff = float(settings.get("hypothesized_difference", 0.0))
    alt = settings.get("alternative", "not_equal")
    assume_equal = bool(settings.get("assume_equal_variances", False))
    graphs = settings.get("graphs", {"individual_value_plot": False, "boxplot": False})

    sample1_name = "Sample 1"
    sample2_name = "Sample 2"
    raw_s1: Optional[List[float]] = None
    raw_s2: Optional[List[float]] = None

    if data_format == 2:  # Summarized data
        summ = settings.get("summarized", {})
        n1 = int(summ.get("n1", 0))
        m1 = float(summ.get("mean1", 0.0))
        s1 = float(summ.get("sd1", 0.0))
        n2 = int(summ.get("n2", 0))
        m2 = float(summ.get("mean2", 0.0))
        s2 = float(summ.get("sd2", 0.0))
        if n1 < 2 or n2 < 2:
            raise ValueError("Sample sizes must be at least 2.")
        if s1 < 0 or s2 < 0:
            raise ValueError("Standard deviations cannot be negative.")
    elif data_format == 0:  # Stacked
        ws = worksheet_or_samples
        samples_idx = settings["samples_col"]
        ids_idx = settings["sample_ids_col"]
        col_samples = ws.columns[samples_idx]
        col_ids = ws.columns[ids_idx]
        sample1_name = f"{col_samples.name} ({col_ids.name})"

        # Clean rows
        pairs = []
        for v, grp in zip(col_samples.values, col_ids.values):
            if v is not None and str(v).strip() != "" and grp is not None and str(grp).strip() != "":
                try:
                    fv = float(v)
                    pairs.append((fv, str(grp).strip()))
                except (ValueError, TypeError):
                    continue
        groups: Dict[str, List[float]] = {}
        for fv, grp in pairs:
            groups.setdefault(grp, []).append(fv)

        unique_groups = list(groups.keys())
        if len(unique_groups) != 2:
            raise ValueError(f"Stacked data must contain exactly 2 groups; found {len(unique_groups)}.")

        g1_name, g2_name = unique_groups[0], unique_groups[1]
        sample1_name = g1_name
        sample2_name = g2_name
        raw_s1 = groups[g1_name]
        raw_s2 = groups[g2_name]
        if len(raw_s1) < 2 or len(raw_s2) < 2:
            raise ValueError("Each group must contain at least 2 observations.")

        n1, m1, s1 = len(raw_s1), float(np.mean(raw_s1)), float(np.std(raw_s1, ddof=1))
        n2, m2, s2 = len(raw_s2), float(np.mean(raw_s2)), float(np.std(raw_s2, ddof=1))
    else:  # Unstacked (1)
        ws = worksheet_or_samples
        s1_idx = settings["sample1_col"]
        s2_idx = settings["sample2_col"]
        col1 = ws.columns[s1_idx]
        col2 = ws.columns[s2_idx]
        sample1_name = col1.name
        sample2_name = col2.name

        def clean_col(c):
            vals = []
            for v in c.values:
                if v is not None and str(v).strip() != "":
                    try:
                        vals.append(float(v))
                    except (ValueError, TypeError):
                        continue
            return vals

        raw_s1 = clean_col(col1)
        raw_s2 = clean_col(col2)
        if len(raw_s1) < 2 or len(raw_s2) < 2:
            raise ValueError("Each sample column must contain at least 2 valid numeric observations.")

        n1, m1, s1 = len(raw_s1), float(np.mean(raw_s1)), float(np.std(raw_s1, ddof=1))
        n2, m2, s2 = len(raw_s2), float(np.mean(raw_s2)), float(np.std(raw_s2, ddof=1))

    # Standard error of the means
    se1 = s1 / math.sqrt(n1)
    se2 = s2 / math.sqrt(n2)

    diff = m1 - m2
    pooled_sd: Optional[float] = None

    if assume_equal:
        df = n1 + n2 - 2
        sp_squared = ((n1 - 1) * (s1 ** 2) + (n2 - 1) * (s2 ** 2)) / max(1, df)
        pooled_sd = math.sqrt(max(0.0, sp_squared))
        se_diff = pooled_sd * math.sqrt(1.0 / n1 + 1.0 / n2)
    else:
        var1_n = (s1 ** 2) / n1
        var2_n = (s2 ** 2) / n2
        se_diff = math.sqrt(var1_n + var2_n)
        denom = ((var1_n ** 2) / (n1 - 1)) + ((var2_n ** 2) / (n2 - 1))
        if denom > 0:
            df_welch = ((var1_n + var2_n) ** 2) / denom
        else:
            df_welch = float(n1 + n2 - 2)
        df = int(round(df_welch))

    # T-value
    if se_diff > 0:
        t_val = (diff - hyp_diff) / se_diff
    else:
        t_val = 0.0

    # P-value & Confidence interval
    if alt == "less_than":
        p_val = float(stats.t.cdf(t_val, df))
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = None
        ci_upper = diff + t_crit * se_diff
    elif alt == "greater_than":
        p_val = float(1.0 - stats.t.cdf(t_val, df))
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = diff - t_crit * se_diff
        ci_upper = None
    else:  # not_equal
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_val), df)))
        t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        ci_lower = diff - t_crit * se_diff
        ci_upper = diff + t_crit * se_diff

    return {
        "sample1": {
            "name": sample1_name,
            "n": n1,
            "mean": m1,
            "stdev": s1,
            "se_mean": se1,
            "raw": raw_s1,
        },
        "sample2": {
            "name": sample2_name,
            "n": n2,
            "mean": m2,
            "stdev": s2,
            "se_mean": se2,
            "raw": raw_s2,
        },
        "difference": diff,
        "se_difference": se_diff,
        "pooled_stdev": pooled_sd,
        "df": df,
        "t_statistic": t_val,
        "p_value": p_val,
        "confidence_level": conf_level,
        "hypothesized_difference": hyp_diff,
        "alternative": alt,
        "assume_equal_variances": assume_equal,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "graphs": graphs,
        "data_format": data_format,
    }
