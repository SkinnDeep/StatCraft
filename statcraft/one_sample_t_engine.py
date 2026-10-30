"""Statistical calculations for native StatCraft One-Sample t test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from scipy import stats
import numpy as np


def one_sample_t_settings(
    data_format: int = 0,  # 0: One or more sample columns, 2: Summarized
    sample_cols: Optional[List[int]] = None,
    summarized: Optional[Dict[str, float]] = None,
    perform_test: bool = True,
    hypothesized_mean: float = 0.0,
    confidence_level: float = 95.0,
    alternative: str = "not_equal",  # "not_equal", "less_than", "greater_than"
    graphs: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    return {
        "data_format": int(data_format),
        "sample_cols": sample_cols or [],
        "summarized": summarized or {"n": 10, "mean": 0.0, "sd": 1.0},
        "perform_test": bool(perform_test),
        "hypothesized_mean": float(hypothesized_mean),
        "confidence_level": float(confidence_level),
        "alternative": alternative,
        "graphs": graphs or {
            "histogram": True,
            "individual_value_plot": True,
            "boxplot": True,
        },
    }


def _calculate_sample_stats(
    n: int,
    mean: float,
    sd: float,
    conf_level: float,
    perform_test: bool,
    hyp_mean: float,
    alt: str,
    raw_data: Optional[List[float]] = None,
    name: str = "Sample",
) -> Dict[str, Any]:
    if n < 2:
        raise ValueError("Sample size must be at least 2.")
    if sd < 0:
        raise ValueError("Standard deviation cannot be negative.")

    alpha = (100.0 - conf_level) / 100.0
    df = n - 1
    se_mean = sd / math.sqrt(n)

    # Confidence interval bounds
    if alt == "less_than":
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = None
        ci_upper = mean + t_crit * se_mean
    elif alt == "greater_than":
        t_crit = float(stats.t.ppf(1.0 - alpha, df))
        ci_lower = mean - t_crit * se_mean
        ci_upper = None
    else:  # not_equal
        t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        ci_lower = mean - t_crit * se_mean
        ci_upper = mean + t_crit * se_mean

    # Hypothesis test
    t_stat = None
    p_val = None
    if perform_test:
        if se_mean > 0:
            t_stat = (mean - hyp_mean) / se_mean
        else:
            t_stat = 0.0

        if alt == "less_than":
            p_val = float(stats.t.cdf(t_stat, df))
        elif alt == "greater_than":
            p_val = float(1.0 - stats.t.cdf(t_stat, df))
        else:  # not_equal
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df)))

    return {
        "name": name,
        "n": n,
        "mean": mean,
        "sd": sd,
        "se_mean": se_mean,
        "df": df,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "t_statistic": t_stat,
        "p_value": p_val,
        "raw_data": raw_data,
    }


def run_one_sample_t(
    worksheet_or_samples: Any,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute One-Sample t test with exact StatCraft formulas."""
    data_format = settings.get("data_format", 0)
    conf_level = float(settings.get("confidence_level", 95.0))
    if not (0.0 < conf_level < 100.0):
        conf_level = 95.0
    perform_test = bool(settings.get("perform_test", True))
    hyp_mean = float(settings.get("hypothesized_mean", 0.0))
    alt = settings.get("alternative", "not_equal")
    if alt not in ("not_equal", "less_than", "greater_than"):
        alt = "not_equal"

    graphs = settings.get("graphs", {
        "histogram": True,
        "individual_value_plot": True,
        "boxplot": True,
    })

    samples_results: List[Dict[str, Any]] = []

    if data_format == 2:  # Summarized data
        sum_dict = settings.get("summarized", {})
        n = int(sum_dict.get("n", 10))
        mean = float(sum_dict.get("mean", 0.0))
        sd = float(sum_dict.get("sd", 1.0))
        sample_res = _calculate_sample_stats(
            n=n,
            mean=mean,
            sd=sd,
            conf_level=conf_level,
            perform_test=perform_test,
            hyp_mean=hyp_mean,
            alt=alt,
            raw_data=None,
            name="Sample",
        )
        samples_results.append(sample_res)
        graphs = {"histogram": False, "individual_value_plot": False, "boxplot": False}
    else:  # Raw sample columns
        sample_cols = settings.get("sample_cols", [])
        if not sample_cols:
            raise ValueError("Please specify at least one sample column.")

        # Extract columns from worksheet or dict
        ws = worksheet_or_samples
        for col_spec in sample_cols:
            col_name = str(col_spec)
            col_values = []
            if hasattr(ws, "columns"):
                if isinstance(col_spec, int):
                    if 0 <= col_spec < len(ws.columns):
                        col_obj = ws.columns[col_spec]
                        col_name = col_obj.name
                        col_values = col_obj.values
                else:
                    for idx, c in enumerate(ws.columns):
                        if c.name.strip().upper() == str(col_spec).strip().upper() or f"C{idx+1}".upper() == str(col_spec).strip().upper():
                            col_name = c.name
                            col_values = c.values
                            break
            elif isinstance(ws, dict):
                col_values = ws.get(col_spec, [])

            # Filter valid numbers
            clean_vals: List[float] = []
            for v in col_values:
                if v is None or v == "" or v == "*":
                    continue
                try:
                    f = float(v)
                    if not math.isnan(f):
                        clean_vals.append(f)
                except (ValueError, TypeError):
                    continue

            if len(clean_vals) < 2:
                raise ValueError(f"Column '{col_name}' must contain at least 2 valid numeric observations.")

            n = len(clean_vals)
            mean = float(np.mean(clean_vals))
            sd = float(np.std(clean_vals, ddof=1))

            sample_res = _calculate_sample_stats(
                n=n,
                mean=mean,
                sd=sd,
                conf_level=conf_level,
                perform_test=perform_test,
                hyp_mean=hyp_mean,
                alt=alt,
                raw_data=clean_vals,
                name=col_name,
            )
            samples_results.append(sample_res)

    return {
        "data_format": data_format,
        "confidence_level": conf_level,
        "perform_test": perform_test,
        "hypothesized_mean": hyp_mean,
        "alternative": alt,
        "samples": samples_results,
        "graphs": graphs,
    }
