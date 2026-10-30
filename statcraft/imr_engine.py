"""Statistical engine for Individuals and Moving Range (I-MR) Control Charts.

Implements native StatCraft PE resource fidelity and statistical formulas matching:
- 0811-IMRCHARTDATASOURCE.MDF (Main I-MR Dialog)
- 0812-INDIVIDUALCHARTESTIMATE.MDF (Estimate Tab: AMR, MMR, SRMSSD, span, Nelson estimate, omission)
- 0813-INDIVIDUALCHARTPARAMETERS.MDF (Parameters Tab: historical mean, historical sigma)
- QCHARTSLIMITS.MDF (Limits Tab: K sigma, upper/lower limit display toggles)
- QCHARTTESTS.MDF (Tests Tab: Nelson tests 1, 2, 3, 4 on Individual chart; Test 1 on MR chart)
- QCHARTSTORAGE.MDF (Storage Tab: Individuals, Moving Ranges, Center Lines, Control Limits, Test Results)
"""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from .capability_engine import d2, d4
from .subgroup_control import d3, evaluate_nelson_tests


def compute_moving_ranges(values: List[Optional[float]], span: int = 2) -> List[Optional[float]]:
    """Compute moving ranges of specified span over observation sequence.
    
    Missing values (None) break spans and are not bridged, matching StatCraft.
    """
    n = len(values)
    mr: List[Optional[float]] = [None] * n
    if span < 2 or n < span:
        return mr

    for i in range(span - 1, n):
        window = values[i - span + 1 : i + 1]
        if any(v is None or not math.isfinite(v) for v in window):
            mr[i] = None
        else:
            clean_win = [float(v) for v in window]  # type: ignore
            mr[i] = float(max(clean_win) - min(clean_win))
    return mr


def d3_constant(span: int) -> float:
    """Standard deviation constant d3 for moving range of length span."""
    return d3(span)


def parse_subgroup_omission(omit_spec: Union[str, List[int], set]) -> set[int]:
    """Parse subgroup omission specification (e.g. '3 12:15' or [3, 12, 13, 14, 15])."""
    if isinstance(omit_spec, (set, list, tuple)):
        return {int(x) for x in omit_spec if isinstance(x, (int, float)) and int(x) > 0}
    if not isinstance(omit_spec, str):
        return set()

    res: set[int] = set()
    tokens = omit_spec.replace(',', ' ').split()
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if ':' in tok:
            parts = tok.split(':')
            if len(parts) == 2:
                try:
                    start, end = int(parts[0]), int(parts[1])
                    if start <= end:
                        res.update(range(start, end + 1))
                    else:
                        res.update(range(end, start + 1))
                except ValueError:
                    pass
        elif '-' in tok and not tok.startswith('-'):
            parts = tok.split('-')
            if len(parts) == 2:
                try:
                    start, end = int(parts[0]), int(parts[1])
                    if start <= end:
                        res.update(range(start, end + 1))
                    else:
                        res.update(range(end, start + 1))
                except ValueError:
                    pass
        else:
            try:
                val = int(tok)
                if val > 0:
                    res.add(val)
            except ValueError:
                pass
    return res


def run_imr_chart(
    values: List[Optional[float]],
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Data",
) -> Dict[str, Any]:
    """Run full I-MR control chart analysis matching StatCraft."""
    opts = copy.deepcopy(options or {})

    # 1. Configuration options
    span = int(opts.get("span", 2))
    if span < 2:
        span = 2
    if span > 100:
        span = 100

    est_method = str(opts.get("estimation_method", "amr")).lower()
    if est_method not in ("amr", "mmr", "srmssd"):
        est_method = "amr"

    unbiasing = bool(opts.get("unbiasing", True))
    use_nelson = bool(opts.get("use_nelson", True))

    k_raw = opts.get("k_sigma", 3.0)
    if isinstance(k_raw, str):
        try:
            parts = [float(x) for x in k_raw.replace(',', ' ').split()]
            k_sigma = parts[-1] if parts else 3.0
            k_list = parts if len(parts) > 1 else [k_sigma]
        except (ValueError, TypeError):
            k_sigma = 3.0
            k_list = [3.0]
    elif isinstance(k_raw, (list, tuple)):
        k_list = [float(x) for x in k_raw]
        k_sigma = k_list[-1] if k_list else 3.0
    else:
        k_sigma = float(k_raw)
        k_list = [k_sigma]

    warning_limits = bool(opts.get("warning_limits", False)) or len(k_list) > 1
    warning_k = float(opts.get("warning_k", 2.0))
    if len(k_list) > 1 and k_list[0] < k_sigma:
        warning_k = k_list[0]
    display_zones = bool(opts.get("display_zones", False)) or (len(k_list) >= 3)

    display_upper = bool(opts.get("display_upper", True))
    display_lower = bool(opts.get("display_lower", True))

    hist_mean = opts.get("historical_mean")
    if hist_mean is not None:
        try:
            hist_mean = float(hist_mean)
        except (ValueError, TypeError):
            hist_mean = None

    hist_sigma = opts.get("historical_sigma")
    if hist_sigma is not None:
        try:
            hist_sigma = float(hist_sigma)
            if hist_sigma <= 0:
                hist_sigma = None
        except (ValueError, TypeError):
            hist_sigma = None

    omit_subgroups = parse_subgroup_omission(opts.get("omit_subgroups", set()))

    # Normalize observations
    observations: List[Optional[float]] = []
    for v in values:
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            observations.append(None)
        else:
            try:
                observations.append(float(v))
            except (ValueError, TypeError):
                observations.append(None)

    n_total = len(observations)
    clean_obs = [v for v in observations if v is not None]
    if len(clean_obs) < 2:
        raise ValueError("I-MR Chart requires at least two non-missing observations.")

    # 2. Moving Ranges
    moving_ranges = compute_moving_ranges(observations, span=span)

    # 3. Parameter Estimation
    # Determine indices eligible for estimation (1-based not in omit_subgroups and observation is not None)
    est_obs_indices = [
        i for i, v in enumerate(observations)
        if (i + 1) not in omit_subgroups and v is not None
    ]
    if not est_obs_indices:
        raise ValueError("All observations omitted; cannot estimate parameters.")

    # Mean center line
    if hist_mean is not None:
        i_center = hist_mean
    else:
        i_center = float(np.mean([observations[i] for i in est_obs_indices]))

    # Sigma estimation
    if hist_sigma is not None:
        sigma_within = hist_sigma
        mr_center = d2(span) * hist_sigma
    else:
        # Determine valid moving ranges for estimation:
        # An MR at index i is valid if non-None and no point in [i - span + 1 .. i] is omitted
        est_mr_vals: List[float] = []
        for i in range(span - 1, n_total):
            mr_val = moving_ranges[i]
            if mr_val is not None:
                pts = range(i - span + 1 + 1, i + 1 + 1)  # 1-based points in window
                if not any(pt in omit_subgroups for pt in pts):
                    est_mr_vals.append(mr_val)

        if not est_mr_vals and est_method in ("amr", "mmr"):
            # Fallback to available clean observations sample stdev if no MR pairs remain
            est_vals = [observations[i] for i in est_obs_indices]  # type: ignore
            sigma_within = float(np.std(est_vals, ddof=1)) if len(est_vals) > 1 else 0.0
            mr_center = d2(span) * sigma_within
        elif est_method == "mmr":
            med_mr = float(np.median(est_mr_vals))
            d4_val = d4(span) if unbiasing else 1.0
            sigma_within = med_mr / d4_val if d4_val > 0 else 0.0
            mr_center = med_mr
        elif est_method == "srmssd":
            # Square root of MSSD over consecutive non-omitted valid pairs
            sq_diffs: List[float] = []
            for i in range(1, n_total):
                if (i + 1) not in omit_subgroups and i not in omit_subgroups:
                    v1, v2 = observations[i - 1], observations[i]
                    if v1 is not None and v2 is not None:
                        sq_diffs.append((v2 - v1) ** 2)
            if sq_diffs:
                sigma_within = math.sqrt(sum(sq_diffs) / (2.0 * len(sq_diffs)))
            else:
                est_vals = [observations[i] for i in est_obs_indices]  # type: ignore
                sigma_within = float(np.std(est_vals, ddof=1)) if len(est_vals) > 1 else 0.0
            mr_center = d2(span) * sigma_within
        else:
            # Default: AMR (Average Moving Range)
            avg_mr = float(np.mean(est_mr_vals))
            d2_val = d2(span) if (unbiasing or use_nelson) else 1.0
            sigma_within = avg_mr / d2_val if d2_val > 0 else 0.0
            mr_center = avg_mr

    # 4. Control Limits
    # Individual Chart Limits
    i_lcl = (i_center - k_sigma * sigma_within) if display_lower else None
    i_ucl = (i_center + k_sigma * sigma_within) if display_upper else None

    # Moving Range Chart Limits
    d2_val = d2(span)
    d3_val = d3(span)
    # Standard formula: D3 = max(0, 1 - 3*d3/d2), D4 = 1 + 3*d3/d2
    d3_factor = max(0.0, 1.0 - 3.0 * (d3_val / d2_val)) if d2_val > 0 else 0.0
    d4_factor = (1.0 + 3.0 * (d3_val / d2_val)) if d2_val > 0 else 1.0

    mr_lcl = max(0.0, d3_factor * mr_center) if display_lower else None
    mr_ucl = (d4_factor * mr_center) if display_upper else None

    # Warning limits
    i_uwl = (i_center + warning_k * sigma_within) if (warning_limits or display_zones) and display_upper else None
    i_lwl = (i_center - warning_k * sigma_within) if (warning_limits or display_zones) and display_lower else None

    d3_warn_factor = max(0.0, 1.0 - warning_k * (d3_val / d2_val)) if d2_val > 0 else 0.0
    d4_warn_factor = (1.0 + warning_k * (d3_val / d2_val)) if d2_val > 0 else 1.0
    mr_lwl = max(0.0, d3_warn_factor * mr_center) if (warning_limits or display_zones) and display_lower else None
    mr_uwl = (d4_warn_factor * mr_center) if (warning_limits or display_zones) and display_upper else None

    # 5. Evaluate Special Cause Tests
    # Individual Chart: evaluate Nelson tests 1, 2, 3, 4
    tests_cfg = opts.get("tests", {})
    t1_enabled = bool(tests_cfg.get("test1", {}).get("enabled", True))
    t1_k = float(tests_cfg.get("test1", {}).get("k", 3.0))

    t2_enabled = bool(tests_cfg.get("test2", {}).get("enabled", False))
    t2_k = int(tests_cfg.get("test2", {}).get("k", 9))

    t3_enabled = bool(tests_cfg.get("test3", {}).get("enabled", False))
    t3_k = int(tests_cfg.get("test3", {}).get("k", 6))

    t4_enabled = bool(tests_cfg.get("test4", {}).get("enabled", False))
    t4_k = int(tests_cfg.get("test4", {}).get("k", 14))

    nelson_rules = {
        "test1": {"enabled": t1_enabled, "k": t1_k},
        "test2": {"enabled": t2_enabled, "k": t2_k},
        "test3": {"enabled": t3_enabled, "k": t3_k},
        "test4": {"enabled": t4_enabled, "k": t4_k},
    }

    # Standard errors for individuals: sigma_within for all points
    se_list = [sigma_within if v is not None else None for v in observations]
    i_test_failures = evaluate_nelson_tests(observations, i_center, se_list, nelson_rules)

    # Legacy i_signals list of 1-based indices for Test 1
    i_signals = [
        i + 1 for i, v in enumerate(observations)
        if v is not None and ((i_lcl is not None and v < i_lcl) or (i_ucl is not None and v > i_ucl))
    ]

    # Moving Range Chart: Test 1 (points exceeding MR limits)
    mr_signals = [
        i + 1 for i, v in enumerate(moving_ranges)
        if v is not None and ((mr_lcl is not None and v < mr_lcl) or (mr_ucl is not None and v > mr_ucl))
    ]

    warnings: List[str] = []
    if sigma_within == 0.0:
        warnings.append("Zero estimated within-subgroup variation: control limits coincide.")
    if omit_subgroups:
        warnings.append(f"Observations omitted from estimation: {sorted(omit_subgroups)}")

    return {
        "analysis": "imr_control",
        "graph": "imr_chart",
        "chart_type": "imr",
        "variable_name": variable_name,
        "count": len(clean_obs),
        "missing": n_total - len(clean_obs),
        "observations": observations,
        "moving_ranges": moving_ranges,
        "mean": i_center,
        "i_center": i_center,
        "i_lcl": i_lcl,
        "i_ucl": i_ucl,
        "within_stdev": sigma_within,
        "disp_center": mr_center,
        "average_moving_range": mr_center,
        "mr_center": mr_center,
        "disp_lcl": mr_lcl,
        "mr_lcl": mr_lcl,
        "disp_ucl": mr_ucl,
        "mr_ucl": mr_ucl,
        "i_uwl": i_uwl,
        "i_lwl": i_lwl,
        "mr_uwl": mr_uwl,
        "mr_lwl": mr_lwl,
        "warning_limits": warning_limits,
        "warning_k": warning_k,
        "display_zones": display_zones,
        "span": span,
        "estimation_method": est_method,
        "unbiasing": unbiasing,
        "use_nelson": use_nelson,
        "omit_subgroups": sorted(omit_subgroups),
        "test_failures": i_test_failures,
        "i_signals": i_signals,
        "mr_signals": mr_signals,
        "options": opts,
        "warnings": warnings,
    }
