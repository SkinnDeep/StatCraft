"""Statistical calculations for native StatCraft One-Sample Proportion test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from scipy import stats
import numpy as np


def one_sample_proportion_settings(
    data_format: int = 0,  # 0: One or more samples in a column, 2: Summarized data
    sample_cols: Optional[List[Union[int, str]]] = None,
    summarized: Optional[Dict[str, int]] = None,
    perform_test: bool = True,
    hypothesized_proportion: float = 0.5,
    confidence_level: float = 95.0,
    alternative: str = "not_equal",  # "not_equal", "less_than", "greater_than"
    method: str = "exact",  # "exact", "normal"
) -> Dict[str, Any]:
    return {
        "data_format": int(data_format),
        "sample_cols": sample_cols or [],
        "summarized": summarized or {"events": 10, "trials": 20},
        "perform_test": bool(perform_test),
        "hypothesized_proportion": float(hypothesized_proportion),
        "confidence_level": float(confidence_level),
        "alternative": alternative,
        "method": method,
    }


def _calculate_proportion_stats(
    n: int,
    events: int,
    conf_level: float,
    perform_test: bool,
    hyp_p: float,
    alt: str,
    method: str,
    name: str = "Sample",
) -> Dict[str, Any]:
    if n < 1:
        raise ValueError("Number of trials must be at least 1.")
    if events < 0:
        raise ValueError("Number of events cannot be negative.")
    if events > n:
        raise ValueError("Number of events cannot exceed number of trials.")
    if not (0.0 < hyp_p < 1.0):
        raise ValueError("Hypothesized proportion must be between 0 and 1.")

    alpha = (100.0 - conf_level) / 100.0
    p_hat = float(events / n)

    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    z_stat: Optional[float] = None
    p_val: Optional[float] = None

    if method == "normal":
        # Normal approximation
        se_sample = math.sqrt(p_hat * (1.0 - p_hat) / n) if (0.0 < p_hat < 1.0) else 0.0

        if alt == "less_than":
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            ci_lower = None
            ci_upper = min(1.0, p_hat + z_crit * se_sample)
        elif alt == "greater_than":
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            ci_lower = max(0.0, p_hat - z_crit * se_sample)
            ci_upper = None
        else:  # not_equal
            z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
            ci_lower = max(0.0, p_hat - z_crit * se_sample)
            ci_upper = min(1.0, p_hat + z_crit * se_sample)

        if perform_test:
            se_0 = math.sqrt(hyp_p * (1.0 - hyp_p) / n)
            if se_0 > 0:
                z_stat = (p_hat - hyp_p) / se_0
                if alt == "less_than":
                    p_val = float(stats.norm.cdf(z_stat))
                elif alt == "greater_than":
                    p_val = float(1.0 - stats.norm.cdf(z_stat))
                else:  # not_equal
                    p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z_stat))))
    else:
        # Exact method (Clopper-Pearson CI and exact Binomial test)
        scipy_alt = "less" if alt == "less_than" else "greater" if alt == "greater_than" else "two-sided"
        bt = stats.binomtest(events, n, p=hyp_p, alternative=scipy_alt)

        ci = bt.proportion_ci(confidence_level=conf_level / 100.0, method="exact")
        if alt == "less_than":
            ci_lower = None
            ci_upper = float(ci.high)
        elif alt == "greater_than":
            ci_lower = float(ci.low)
            ci_upper = None
        else:
            ci_lower = float(ci.low)
            ci_upper = float(ci.high)

        if perform_test:
            p_val = float(bt.pvalue)

    return {
        "name": name,
        "n": n,
        "events": events,
        "sample_p": p_hat,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "z_statistic": z_stat,
        "p_value": p_val,
        "method": method,
    }


def run_one_sample_proportion(
    worksheet_or_samples: Any,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute One-Sample Proportion test with exact StatCraft formulas."""
    data_format = settings.get("data_format", 0)
    conf_level = float(settings.get("confidence_level", 95.0))
    if not (0.0 < conf_level < 100.0):
        conf_level = 95.0

    perform_test = bool(settings.get("perform_test", True))
    hyp_p = float(settings.get("hypothesized_proportion", 0.5))
    if perform_test and not (0.0 < hyp_p < 1.0):
        raise ValueError("Hypothesized proportion must be between 0 and 1.")

    alt = settings.get("alternative", "not_equal")
    if alt not in ("not_equal", "less_than", "greater_than"):
        alt = "not_equal"

    method = settings.get("method", "exact")
    if method not in ("exact", "normal"):
        method = "exact"

    samples_results: List[Dict[str, Any]] = []

    if data_format == 2:  # Summarized data
        sum_dict = settings.get("summarized", {})
        events = int(sum_dict.get("events", 10))
        trials = int(sum_dict.get("trials", 20))
        sample_res = _calculate_proportion_stats(
            n=trials,
            events=events,
            conf_level=conf_level,
            perform_test=perform_test,
            hyp_p=hyp_p,
            alt=alt,
            method=method,
            name="Sample",
        )
        samples_results.append(sample_res)
    else:  # Raw sample columns
        sample_cols = settings.get("sample_cols", [])
        if not sample_cols:
            raise ValueError("Please specify at least one sample column.")

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

            # Filter valid non-missing observations
            clean_vals: List[Any] = []
            for v in col_values:
                if v is None or v == "" or v == "*":
                    continue
                if isinstance(v, float) and math.isnan(v):
                    continue
                clean_vals.append(v)

            if len(clean_vals) < 1:
                raise ValueError(f"Column '{col_name}' must contain at least 1 valid observation.")

            # Identify events and trials
            # If 0 and 1, 1 is the event.
            # Otherwise, count occurrences of event value (second sorted distinct value or highest).
            num_numeric = 0
            num_ones = 0
            for v in clean_vals:
                try:
                    f = float(v)
                    num_numeric += 1
                    if f == 1.0:
                        num_ones += 1
                except (ValueError, TypeError):
                    pass

            if num_numeric == len(clean_vals) and set(clean_vals).issubset({0, 1, 0.0, 1.0}):
                events = num_ones
                n = len(clean_vals)
            else:
                # Categorical or non-standard binary
                distinct = sorted(list(set(clean_vals)), key=lambda x: str(x))
                if len(distinct) == 1:
                    events = len(clean_vals)
                    n = len(clean_vals)
                else:
                    event_target = distinct[-1]
                    events = sum(1 for v in clean_vals if v == event_target)
                    n = len(clean_vals)

            sample_res = _calculate_proportion_stats(
                n=n,
                events=events,
                conf_level=conf_level,
                perform_test=perform_test,
                hyp_p=hyp_p,
                alt=alt,
                method=method,
                name=col_name,
            )
            samples_results.append(sample_res)

    return {
        "data_format": data_format,
        "confidence_level": conf_level,
        "perform_test": perform_test,
        "hypothesized_proportion": hyp_p,
        "alternative": alt,
        "method": method,
        "samples": samples_results,
    }
