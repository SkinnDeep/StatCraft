"""Statistical calculations for native StatCraft Two-Sample Proportion test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from scipy import stats
import numpy as np


def two_sample_proportion_settings(
    data_format: int = 1,  # 0: Stacked, 1: Unstacked, 2: Summarized
    samples_col: Optional[Union[int, str]] = None,
    sample_ids_col: Optional[Union[int, str]] = None,
    sample1_col: Optional[Union[int, str]] = None,
    sample2_col: Optional[Union[int, str]] = None,
    summarized: Optional[Dict[str, int]] = None,
    confidence_level: float = 95.0,
    hypothesized_difference: float = 0.0,
    alternative: str = "not_equal",  # "not_equal", "less_than", "greater_than"
    test_method: str = "pooled",  # "unpooled", "pooled"
) -> Dict[str, Any]:
    return {
        "data_format": int(data_format),
        "samples_col": samples_col,
        "sample_ids_col": sample_ids_col,
        "sample1_col": sample1_col,
        "sample2_col": sample2_col,
        "summarized": summarized or {
            "events1": 10, "trials1": 20,
            "events2": 10, "trials2": 20,
        },
        "confidence_level": float(confidence_level),
        "hypothesized_difference": float(hypothesized_difference),
        "alternative": alternative,
        "test_method": test_method,
    }


def _extract_events_and_trials(vals: List[Any]) -> Tuple[int, int]:
    clean_vals = [v for v in vals if v is not None and v != "" and v != "*" and not (isinstance(v, float) and math.isnan(v))]
    if len(clean_vals) < 1:
        raise ValueError("Sample must contain at least 1 valid observation.")

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
        return num_ones, len(clean_vals)
    else:
        distinct = sorted(list(set(clean_vals)), key=lambda x: str(x))
        if len(distinct) == 1:
            return len(clean_vals), len(clean_vals)
        event_target = distinct[-1]
        events = sum(1 for v in clean_vals if v == event_target)
        return events, len(clean_vals)


def run_two_sample_proportion(
    worksheet_or_samples: Any,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Two-Sample Proportion test with exact StatCraft formulas."""
    data_format = settings.get("data_format", 1)
    conf_level = float(settings.get("confidence_level", 95.0))
    if not (0.0 < conf_level < 100.0):
        conf_level = 95.0

    hyp_diff = float(settings.get("hypothesized_difference", 0.0))
    alt = settings.get("alternative", "not_equal")
    if alt not in ("not_equal", "less_than", "greater_than"):
        alt = "not_equal"

    test_method = settings.get("test_method", "pooled")
    if test_method not in ("unpooled", "pooled"):
        test_method = "pooled"

    ws = worksheet_or_samples

    s1_name = "Sample 1"
    s2_name = "Sample 2"
    x1, n1 = 0, 0
    x2, n2 = 0, 0

    if data_format == 2:  # Summarized
        s = settings.get("summarized", {})
        x1 = int(s.get("events1", 0))
        n1 = int(s.get("trials1", 1))
        x2 = int(s.get("events2", 0))
        n2 = int(s.get("trials2", 1))
    elif data_format == 0:  # Stacked
        s_col = settings.get("samples_col")
        id_col = settings.get("sample_ids_col")
        if s_col is None or id_col is None:
            raise ValueError("Please specify both the samples column and sample ID column.")

        vals, ids = [], []
        if hasattr(ws, "columns"):
            # find cols
            for idx, c in enumerate(ws.columns):
                if s_col in (idx, f"C{idx+1}", c.name):
                    vals = c.values
                if id_col in (idx, f"C{idx+1}", c.name):
                    ids = c.values
        elif isinstance(ws, dict):
            vals = ws.get(s_col, [])
            ids = ws.get(id_col, [])

        # group by id
        distinct_ids: List[Any] = []
        grouped: Dict[Any, List[Any]] = {}
        for v, g in zip(vals, ids):
            if g is None or g == "" or g == "*":
                continue
            if v is None or v == "" or v == "*":
                continue
            if g not in grouped:
                grouped[g] = []
                distinct_ids.append(g)
            grouped[g].append(v)

        if len(distinct_ids) < 2:
            raise ValueError("Sample ID column must contain at least two distinct groups.")

        s1_name = str(distinct_ids[0])
        s2_name = str(distinct_ids[1])
        x1, n1 = _extract_events_and_trials(grouped[distinct_ids[0]])
        x2, n2 = _extract_events_and_trials(grouped[distinct_ids[1]])
    else:  # Unstacked (Default)
        c1 = settings.get("sample1_col")
        c2 = settings.get("sample2_col")
        if c1 is None or c2 is None:
            raise ValueError("Please specify both sample columns.")

        vals1, vals2 = [], []
        if hasattr(ws, "columns"):
            for idx, c in enumerate(ws.columns):
                if c1 in (idx, f"C{idx+1}", c.name):
                    s1_name = c.name
                    vals1 = c.values
                if c2 in (idx, f"C{idx+1}", c.name):
                    s2_name = c.name
                    vals2 = c.values
        elif isinstance(ws, dict):
            vals1 = ws.get(c1, [])
            vals2 = ws.get(c2, [])

        x1, n1 = _extract_events_and_trials(vals1)
        x2, n2 = _extract_events_and_trials(vals2)

    # Validation
    if n1 < 1 or n2 < 1:
        raise ValueError("Sample sizes must be at least 1.")
    if x1 < 0 or x2 < 0 or x1 > n1 or x2 > n2:
        raise ValueError("Events must be non-negative and cannot exceed trials.")

    p1 = x1 / n1
    p2 = x2 / n2
    diff = p1 - p2

    alpha = (100.0 - conf_level) / 100.0

    # Unpooled standard error for confidence intervals
    se_diff = math.sqrt(p1 * (1.0 - p1) / n1 + p2 * (1.0 - p2) / n2)

    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None

    if alt == "less_than":
        z_crit = float(stats.norm.ppf(1.0 - alpha))
        ci_lower = None
        ci_upper = diff + z_crit * se_diff
    elif alt == "greater_than":
        z_crit = float(stats.norm.ppf(1.0 - alpha))
        ci_lower = diff - z_crit * se_diff
        ci_upper = None
    else:  # not_equal
        z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
        ci_lower = diff - z_crit * se_diff
        ci_upper = diff + z_crit * se_diff

    # Hypothesis Testing
    z_stat = None
    p_val_z = None
    if test_method == "pooled" and hyp_diff == 0.0:
        p_pool = (x1 + x2) / (n1 + n2)
        se_test = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
    else:
        se_test = se_diff

    if se_test > 0:
        z_stat = (diff - hyp_diff) / se_test
        if alt == "less_than":
            p_val_z = float(stats.norm.cdf(z_stat))
        elif alt == "greater_than":
            p_val_z = float(1.0 - stats.norm.cdf(z_stat))
        else:
            p_val_z = float(2.0 * (1.0 - stats.norm.cdf(abs(z_stat))))

    # Fisher's Exact Test
    fisher_p = None
    try:
        fisher_alt = "less" if alt == "less_than" else "greater" if alt == "greater_than" else "two-sided"
        table = [[x1, n1 - x1], [x2, n2 - x2]]
        _, fisher_p = stats.fisher_exact(table, alternative=fisher_alt)
        fisher_p = float(fisher_p)
    except Exception:
        fisher_p = None

    return {
        "data_format": data_format,
        "sample1": {
            "name": s1_name,
            "events": x1,
            "n": n1,
            "sample_p": p1,
        },
        "sample2": {
            "name": s2_name,
            "events": x2,
            "n": n2,
            "sample_p": p2,
        },
        "difference": diff,
        "hypothesized_difference": hyp_diff,
        "confidence_level": conf_level,
        "alternative": alt,
        "test_method": test_method,
        "se_difference": se_diff,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "z_statistic": z_stat,
        "p_value": p_val_z,
        "fisher_p_value": fisher_p,
    }
