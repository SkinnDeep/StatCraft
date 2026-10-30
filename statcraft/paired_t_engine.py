"""Statistical calculations for native StatCraft Paired t test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from scipy import stats
import numpy as np


def paired_t_settings(
    data_format: int = 1,  # 1: Each sample is in a column, 2: Summarized data (differences)
    sample1_col: Optional[Union[int, str]] = None,
    sample2_col: Optional[Union[int, str]] = None,
    summarized: Optional[Dict[str, float]] = None,
    confidence_level: float = 95.0,
    hypothesized_difference: float = 0.0,
    alternative: str = "not_equal",  # "not_equal", "less_than", "greater_than"
    graphs: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    return {
        "data_format": int(data_format),
        "sample1_col": sample1_col,
        "sample2_col": sample2_col,
        "summarized": summarized or {"n": 10, "mean": 0.0, "sd": 1.0},
        "confidence_level": float(confidence_level),
        "hypothesized_difference": float(hypothesized_difference),
        "alternative": alternative,
        "graphs": graphs or {
            "histogram": True,
            "individual_value_plot": True,
            "boxplot": True,
        },
    }


def run_paired_t(
    worksheet_or_samples: Any,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Paired t test with exact StatCraft formulas."""
    data_format = settings.get("data_format", 1)
    conf_level = float(settings.get("confidence_level", 95.0))
    if not (0.0 < conf_level < 100.0):
        conf_level = 95.0
    alpha = (100.0 - conf_level) / 100.0
    hyp_diff = float(settings.get("hypothesized_difference", 0.0))
    alt = settings.get("alternative", "not_equal")
    if alt not in ("not_equal", "less_than", "greater_than"):
        alt = "not_equal"

    graphs = settings.get("graphs", {
        "histogram": True,
        "individual_value_plot": True,
        "boxplot": True,
    })

    if data_format == 2:  # Summarized differences
        sum_dict = settings.get("summarized", {})
        n = int(sum_dict.get("n", 10))
        mean_d = float(sum_dict.get("mean", 0.0))
        sd_d = float(sum_dict.get("sd", 1.0))
        if n < 2:
            raise ValueError("Sample size must be at least 2.")
        if sd_d < 0:
            raise ValueError("Standard deviation cannot be negative.")

        se_d = sd_d / math.sqrt(n)
        df = n - 1
        sample1_stats = None
        sample2_stats = None
        diff_data = None
        s1_name = "Sample 1"
        s2_name = "Sample 2"
        graphs = {"histogram": False, "individual_value_plot": False, "boxplot": False}
    else:  # Raw paired columns
        s1_spec = settings.get("sample1_col")
        s2_spec = settings.get("sample2_col")
        if s1_spec is None or s2_spec is None:
            raise ValueError("Please specify both Sample 1 and Sample 2 columns.")

        ws = worksheet_or_samples
        v1_raw: List[Any] = []
        v2_raw: List[Any] = []
        s1_name = str(s1_spec)
        s2_name = str(s2_spec)

        def resolve_col(spec):
            if hasattr(ws, "columns"):
                if isinstance(spec, int):
                    if 0 <= spec < len(ws.columns):
                        return ws.columns[spec].name, ws.columns[spec].values
                else:
                    for idx, c in enumerate(ws.columns):
                        if c.name.strip().upper() == str(spec).strip().upper() or f"C{idx+1}".upper() == str(spec).strip().upper():
                            return c.name, c.values
            elif isinstance(ws, dict):
                return str(spec), ws.get(spec, [])
            return str(spec), []

        s1_name, v1_raw = resolve_col(s1_spec)
        s2_name, v2_raw = resolve_col(s2_spec)

        # Row-aligned filtering: pair is valid only if both elements are valid numbers
        max_len = max(len(v1_raw), len(v2_raw))
        clean_s1: List[float] = []
        clean_s2: List[float] = []
        clean_diff: List[float] = []

        for i in range(max_len):
            val1 = v1_raw[i] if i < len(v1_raw) else None
            val2 = v2_raw[i] if i < len(v2_raw) else None
            if val1 is None or val1 == "" or val1 == "*" or val2 is None or val2 == "" or val2 == "*":
                continue
            try:
                f1 = float(val1)
                f2 = float(val2)
                if not (math.isnan(f1) or math.isnan(f2)):
                    clean_s1.append(f1)
                    clean_s2.append(f2)
                    clean_diff.append(f1 - f2)
            except (ValueError, TypeError):
                continue

        n = len(clean_diff)
        if n < 2:
            raise ValueError("At least 2 complete pairs of numeric observations are required.")

        df = n - 1
        m1 = float(np.mean(clean_s1))
        sd1 = float(np.std(clean_s1, ddof=1))
        se1 = sd1 / math.sqrt(n)

        m2 = float(np.mean(clean_s2))
        sd2 = float(np.std(clean_s2, ddof=1))
        se2 = sd2 / math.sqrt(n)

        mean_d = float(np.mean(clean_diff))
        sd_d = float(np.std(clean_diff, ddof=1))
        se_d = sd_d / math.sqrt(n)

        sample1_stats = {
            "name": s1_name,
            "n": n,
            "mean": m1,
            "sd": sd1,
            "se_mean": se1,
            "raw": clean_s1,
        }
        sample2_stats = {
            "name": s2_name,
            "n": n,
            "mean": m2,
            "sd": sd2,
            "se_mean": se2,
            "raw": clean_s2,
        }
        diff_data = clean_diff

    # T-statistic
    if se_d > 0:
        t_stat = (mean_d - hyp_diff) / se_d
    else:
        t_stat = 0.0

    # P-value & Confidence interval
    if alt == "less_than":
        p_val = float(stats.t.cdf(t_stat, df))
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = None
        ci_upper = mean_d + t_crit * se_d
    elif alt == "greater_than":
        p_val = float(1.0 - stats.t.cdf(t_stat, df))
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = mean_d - t_crit * se_d
        ci_upper = None
    else:  # not_equal
        p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df)))
        t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        ci_lower = mean_d - t_crit * se_d
        ci_upper = mean_d + t_crit * se_d

    return {
        "data_format": data_format,
        "sample1_name": s1_name,
        "sample2_name": s2_name,
        "sample1": sample1_stats,
        "sample2": sample2_stats,
        "differences": {
            "n": n,
            "mean": mean_d,
            "sd": sd_d,
            "se_mean": se_d,
            "df": df,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "raw": diff_data,
        },
        "confidence_level": conf_level,
        "hypothesized_difference": hyp_diff,
        "alternative": alt,
        "t_statistic": t_stat,
        "df": df,
        "p_value": p_val,
        "graphs": graphs,
    }
