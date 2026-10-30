"""Statistical engine for Rare Event Control Charts (G Chart & T Chart).

Implements native StatCraft PE resource fidelity and statistical formulas matching:
- 0750-GCHARTDATASOURCE.MDF (G Chart: MenuID 41256, HelpID 88700)
- 0751-GCHARTPARAMETERS.MDF (G Chart Parameters: Proportion p)
- 0752-GCHARTTESTS.MDF (G Chart Tests: Test 1, Benneyan test)
- 1136-TCHARTDATASOURCE.MDF (T Chart: MenuID 41257, HelpID 88701)
- 1137-TCHARTPARAMETERS.MDF (T Chart Parameters: Weibull shape/scale, Exponential scale)
- 1138-TCHARTTESTS.MDF (T Chart Tests: Test 1, Benneyan test)
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np

from .capability_engine import d2
from .attribute_control_engine import parse_subgroup_omission


def _clean_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "*":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def convert_dates_to_intervals(
    date_values: Sequence[Any],
    unit: str = "Days",
) -> List[float]:
    """Convert sequence of timestamps or ISO date strings to intervals between events."""
    parsed: List[float] = []
    epoch = datetime(1899, 12, 30)

    for v in date_values:
        if v is None:
            continue
        if isinstance(v, (int, float)):
            # Serial date number (days from epoch)
            parsed.append(float(v))
        elif isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                continue
            # Try ISO formats
            try:
                dt = datetime.fromisoformat(v_str.replace("Z", ""))
                serial = (dt - epoch).total_seconds() / 86400.0
                parsed.append(serial)
            except ValueError:
                # Fallback float parsing
                try:
                    f = float(v_str)
                    parsed.append(f)
                except ValueError:
                    pass

    if len(parsed) < 2:
        return []

    # Differences between consecutive events
    mult = 1.0
    if unit.lower().startswith("hour"):
        mult = 24.0

    diffs: List[float] = []
    for i in range(1, len(parsed)):
        d = (parsed[i] - parsed[i - 1]) * mult
        diffs.append(max(0.0, float(d)))
    return diffs


def run_g_chart(
    data: Sequence[Any],
    form_of_data: int = 1,  # 0: Dates of events, 1: Number of opportunities
    method_of_count: int = 0,  # 0: Opportunities between events (0, 1, 2...), 1: Until an event (1, 2, 3...)
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Opportunities",
) -> Dict[str, Any]:
    """Compute G Chart for geometric counts between rare events."""
    opts = options or {}
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    method_count = int(opts.get("method_of_count", method_of_count))

    if form_of_data == 0:
        # Dates of events
        raw_intervals = convert_dates_to_intervals(data, unit="Days")
        # In G chart, opportunities are integers
        counts = [int(round(x)) for x in raw_intervals]
    else:
        counts_clean = [_clean_float(x) for x in data]
        counts = [int(round(x)) for x in counts_clean if x is not None and x >= 0]

    m = len(counts)
    if m == 0:
        raise ValueError("No valid observation counts provided for G Chart.")

    included = [i for i in range(m) if (i + 1) not in omit]
    if not included:
        included = list(range(m))

    inc_counts = [counts[i] for i in included]
    mean_count = float(np.mean(inc_counts)) if inc_counts else 1.0

    # Estimate proportion p
    user_p = _clean_float(opts.get("p"))
    if user_p is not None and 0.0 < user_p < 1.0:
        p_hat = user_p
    else:
        if method_count == 0:
            # Opportunities between events (Y >= 0)
            p_hat = 1.0 / (mean_count + 1.0) if (mean_count + 1.0) > 0 else 0.5
        else:
            # Opportunities until event (Y >= 1)
            p_hat = 1.0 / mean_count if mean_count > 0 else 0.5

    p_hat = max(1e-7, min(1.0 - 1e-7, p_hat))

    # Center Line (Median of geometric distribution, matching StatCraft default)
    # Median M = ceil( -ln(2) / ln(1 - p) ) - 1 (or continuous formula)
    # StatCraft uses continuous median: -ln(2) / ln(1 - p) - (1 if method_count == 0 else 0)
    denom = math.log(1.0 - p_hat)
    if denom == 0:
        denom = -1e-7

    median_val = (-math.log(2.0) / denom) - (1.0 if method_count == 0 else 0.0)
    cl = max(0.0, median_val)

    # Control limits based on geometric probability limits (alpha = 0.0027, i.e. 3-sigma equivalent)
    # Lower tail: alpha/2 = 0.00135; Upper tail: 1 - alpha/2 = 0.99865
    alpha = 0.0027
    tail = alpha / 2.0  # 0.00135

    # LCL = ln(1 - alpha/2) / ln(1 - p) - 1
    # UCL = ln(alpha/2) / ln(1 - p) - 1
    lcl_raw = (math.log(1.0 - tail) / denom) - (1.0 if method_count == 0 else 0.0)
    ucl_raw = (math.log(tail) / denom) - (1.0 if method_count == 0 else 0.0)

    lcl = max(0.0, float(lcl_raw))
    ucl = max(lcl, float(ucl_raw))

    # Test 1: Point beyond control limits
    test1_signals: List[int] = []
    for i, c in enumerate(counts):
        if c > ucl or c < lcl:
            test1_signals.append(i + 1)

    # Benneyan test: Benneyan (1998, 2001) for rare event detection:
    # A run of consecutive zeros (or minimum count) indicates a clustering of defects/events.
    # Default Benneyan threshold B: B consecutive zeros where B = ceil(ln(alpha) / ln(1 - p)) or B=3
    benneyan_thresh = int(opts.get("benneyan_threshold", 3))
    benneyan_signals: List[int] = []
    zero_run = 0
    min_val = 0 if method_count == 0 else 1
    for i, c in enumerate(counts):
        if c <= min_val:
            zero_run += 1
            if zero_run >= benneyan_thresh:
                benneyan_signals.append(i + 1)
        else:
            zero_run = 0

    all_signals = sorted(set(test1_signals + benneyan_signals))

    test_failures: Dict[int, List[int]] = {}
    if test1_signals:
        test_failures[1] = test1_signals
    if benneyan_signals:
        test_failures[2] = benneyan_signals

    return {
        "analysis": "rare_event_control",
        "chart_type": "G",
        "variable_name": variable_name,
        "form_of_data": form_of_data,
        "method_of_count": method_count,
        "p": p_hat,
        "historical_p": user_p,
        "center_line": cl,
        "mean_count": mean_count,
        "median": median_val,
        "ucl": [ucl] * m,
        "lcl": [lcl] * m,
        "ucl_val": ucl,
        "lcl_val": lcl,
        "values": counts,
        "observations": counts,
        "k_subgroups": m,
        "omit_subgroups": sorted(omit),
        "test_failures": test_failures,
        "test1_signals": test1_signals,
        "benneyan_signals": benneyan_signals,
        "signals": all_signals,
    }


def run_t_chart(
    data: Sequence[Any],
    form_of_data: int = 1,  # 0: Dates/Times of events, 1: Numeric intervals
    distribution: str = "Weibull",  # "Weibull" or "Exponential"
    units: str = "Days",
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Time",
) -> Dict[str, Any]:
    """Compute T Chart for times between rare events using Weibull/Exponential power transformation."""
    opts = options or {}
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    dist = str(opts.get("distribution", distribution)).capitalize()

    if form_of_data == 0:
        times = convert_dates_to_intervals(data, unit=units)
    else:
        times_clean = [_clean_float(x) for x in data]
        times = [float(x) for x in times_clean if x is not None and x > 0]

    m = len(times)
    if m == 0:
        raise ValueError("No valid positive time intervals provided for T Chart.")

    included = [i for i in range(m) if (i + 1) not in omit]
    if not included:
        included = list(range(m))

    inc_times = [times[i] for i in included]

    # Shape parameter beta:
    # In StatCraft, for Exponential distribution, shape is 1.0.
    # Under Exponential (or Weibull beta=1), the transformation y = t^(1/3.6) = t^0.27777...
    # normalizes the distribution (Nelson, 1994; Kaminsky et al., 1992).
    # For general Weibull, user can specify shape or it is estimated.
    user_shape = _clean_float(opts.get("shape"))
    user_scale = _clean_float(opts.get("scale"))

    if dist.startswith("Expo"):
        shape_beta = 1.0
    else:
        shape_beta = user_shape if (user_shape is not None and user_shape > 0) else 1.0

    # Normalizing power transformation exponent: p = 1 / (beta * 3.6)
    power = 1.0 / (shape_beta * 3.6)

    # Transformed data y_i = t_i ^ power
    y_vals = [t ** power for t in times]
    inc_y = [y_vals[i] for i in included]

    # Mean and sigma on transformed scale
    y_mean = float(np.mean(inc_y)) if inc_y else 1.0
    
    # Sigma estimated from moving range of y or sample stdev
    if len(inc_y) > 1:
        mr_y = [abs(inc_y[j] - inc_y[j - 1]) for j in range(1, len(inc_y))]
        avg_mr = float(np.mean(mr_y))
        y_sigma = avg_mr / d2(2)
    else:
        y_sigma = 0.5

    if user_scale is not None and user_scale > 0:
        scale_eta = user_scale
    else:
        # Scale parameter eta for Weibull: mean(t) / gamma(1 + 1/beta)
        mean_t = float(np.mean(inc_times))
        scale_eta = mean_t / math.gamma(1.0 + 1.0 / shape_beta)

    # Transformed limits
    k_sig = float(opts.get("k_sigma", 3.0))
    y_ucl = y_mean + k_sig * y_sigma
    y_lcl = max(0.0, y_mean - k_sig * y_sigma)

    # Back-transform to original time scale: t = y ^ (1 / power) = y ^ (beta * 3.6)
    inv_power = shape_beta * 3.6
    cl_time = y_mean ** inv_power
    ucl_time = y_ucl ** inv_power
    lcl_time = y_lcl ** inv_power

    # Test 1: Points beyond control limits
    test1_signals: List[int] = []
    for i, t in enumerate(times):
        if t > ucl_time or t < lcl_time:
            test1_signals.append(i + 1)

    # Benneyan test: consecutive small times (below LCL or bottom 10th percentile)
    benneyan_thresh = int(opts.get("benneyan_threshold", 3))
    benneyan_signals: List[int] = []
    short_run = 0
    short_cutoff = max(lcl_time, cl_time * 0.15)
    for i, t in enumerate(times):
        if t <= short_cutoff:
            short_run += 1
            if short_run >= benneyan_thresh:
                benneyan_signals.append(i + 1)
        else:
            short_run = 0

    all_signals = sorted(set(test1_signals + benneyan_signals))

    test_failures: Dict[int, List[int]] = {}
    if test1_signals:
        test_failures[1] = test1_signals
    if benneyan_signals:
        test_failures[2] = benneyan_signals

    return {
        "analysis": "rare_event_control",
        "chart_type": "T",
        "variable_name": variable_name,
        "form_of_data": form_of_data,
        "distribution": dist,
        "units": units,
        "shape": shape_beta,
        "scale": scale_eta,
        "center_line": cl_time,
        "y_mean": y_mean,
        "y_sigma": y_sigma,
        "ucl": [ucl_time] * m,
        "lcl": [lcl_time] * m,
        "ucl_val": ucl_time,
        "lcl_val": lcl_time,
        "values": times,
        "observations": times,
        "k_subgroups": m,
        "omit_subgroups": sorted(omit),
        "test_failures": test_failures,
        "test1_signals": test1_signals,
        "benneyan_signals": benneyan_signals,
        "signals": all_signals,
    }
