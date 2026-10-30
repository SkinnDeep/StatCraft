"""Statistical engine for Attributes Control Charts (P, NP, C, U Charts).

Implements native StatCraft PE resource fidelity and statistical formulas matching:
- 0922-PCHARTDATASOURCE.MDF (P Chart: Proportions of defectives)
- 0876-NPCHARTDATASOURCE.MDF (NP Chart: Number of defectives)
- 0472-CCHARTDATASOURCE.MDF (C Chart: Count of defects per unit)
- 1159-UCHARTDATASOURCE.MDF (U Chart: Defects per unit)
- 1000-QCHARTATTRIBUTEPARAMETERS.MDF (Parameters: historical P / Mean)
- 1014-QCHARTTESTS4.MDF (Tests: 1, 2, 3, 4 for attribute charts)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np

from .capability_engine import d2
from .subgroup_control import evaluate_nelson_tests


def parse_subgroup_omission(omit_spec: Union[str, Sequence[int], Set[int], None]) -> Set[int]:
    """Parse subgroup omission specification (e.g. '3 12:15' or [3, 12, 13, 14, 15])."""
    if omit_spec is None:
        return set()
    if isinstance(omit_spec, (set, list, tuple)):
        return {int(x) for x in omit_spec if isinstance(x, (int, float)) and int(x) > 0}
    if not isinstance(omit_spec, str):
        return set()

    res: Set[int] = set()
    tokens = omit_spec.replace(',', ' ').split()
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        sep = ':' if ':' in tok else ('-' if '-' in tok and not tok.startswith('-') else None)
        if sep is not None:
            parts = tok.split(sep)
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
                res.add(int(tok))
            except ValueError:
                pass
    return res


def run_attribute_control(
    chart_type: str,
    counts: Sequence[Any],
    sample_sizes: Union[float, int, Sequence[Any], None] = None,
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Defects",
    subgroup_size_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute attribute control chart (P, NP, C, or U).
    
    Parameters
    ----------
    chart_type : str
        One of 'P', 'NP', 'C', 'U' (case-insensitive).
    counts : sequence
        List of counts (defectives for P/NP, defects for C/U).
    sample_sizes : float, int, sequence, or None
        Constant sample size or sequence of subgroup sizes / exposures.
        Ignored for 'C' chart (fixed at 1).
    options : dict, optional
        Configuration options:
        - 'historical_p': float (historical proportion for P/NP)
        - 'historical_mean': float (historical mean for C/U)
        - 'omit_subgroups': str or sequence of 1-based subgroup indices to omit from estimation
        - 'k_sigma': float (default 3.0)
        - 'display_upper': bool (default True)
        - 'display_lower': bool (default True)
        - 'tests': dict of test configurations {test1: {enabled, k}, ...}
    variable_name : str
        Name of the count column.
    subgroup_size_name : str, optional
        Name of the sample size column, if provided as a column.
    """
    raw_type = chart_type.upper().strip().replace("′", "'")
    if raw_type in ("P'", "P_PRIME", "LANEY_P", "LANEY P'", "LANEY P′"):
        chart_upper = "P'"
    elif raw_type in ("U'", "U_PRIME", "LANEY_U", "LANEY U'", "LANEY U′"):
        chart_upper = "U'"
    elif raw_type in ("P", "NP", "C", "U"):
        chart_upper = raw_type
    else:
        raise ValueError(f"Unsupported attribute chart type: '{chart_type}'. Must be P, NP, C, U, P', or U'.")

    opts = options or {}
    k_sigma = float(opts.get("k_sigma", 3.0))
    display_upper = bool(opts.get("display_upper", True))
    display_lower = bool(opts.get("display_lower", True))
    omit_set = parse_subgroup_omission(opts.get("omit_subgroups"))

    n_rows = len(counts)
    if n_rows == 0:
        raise ValueError(f"{chart_upper} Chart requires at least one observation.")

    # Parse counts
    clean_counts: List[Optional[float]] = []
    for c in counts:
        if c is None or (isinstance(c, float) and (math.isnan(c) or math.isinf(c))):
            clean_counts.append(None)
        else:
            try:
                val = float(c)
                if val < 0:
                    raise ValueError(f"Count values for {chart_upper} Chart cannot be negative: {val}")
                clean_counts.append(val)
            except (ValueError, TypeError):
                clean_counts.append(None)

    # Parse sample sizes
    clean_sizes: List[Optional[float]] = []
    is_constant_size = False
    constant_size_val: Optional[float] = None

    if chart_upper == "C":
        # C chart always has constant size 1.0
        clean_sizes = [1.0] * n_rows
        is_constant_size = True
        constant_size_val = 1.0
    else:
        if sample_sizes is None:
            if chart_upper == "NP":
                raise ValueError("NP Chart requires a specified subgroup size.")
            elif chart_upper in ("P", "P'", "U", "U'"):
                raise ValueError(f"{chart_upper} Chart requires subgroup size (constant or column).")
        elif isinstance(sample_sizes, (int, float)):
            constant_size_val = float(sample_sizes)
            if constant_size_val <= 0:
                raise ValueError("Subgroup size must be positive.")
            clean_sizes = [constant_size_val] * n_rows
            is_constant_size = True
        elif isinstance(sample_sizes, Sequence):
            if len(sample_sizes) != n_rows:
                raise ValueError("Counts and subgroup size column must have the same length.")
            for s in sample_sizes:
                if s is None or (isinstance(s, float) and (math.isnan(s) or math.isinf(s))):
                    clean_sizes.append(None)
                else:
                    try:
                        val = float(s)
                        if val <= 0:
                            raise ValueError(f"Subgroup sizes must be positive: {val}")
                        clean_sizes.append(val)
                    except (ValueError, TypeError):
                        clean_sizes.append(None)
            # Check if all valid sizes are identical
            valid_sizes = [s for s in clean_sizes if s is not None]
            if valid_sizes and all(abs(s - valid_sizes[0]) < 1e-12 for s in valid_sizes):
                is_constant_size = True
                constant_size_val = valid_sizes[0]
        else:
            raise ValueError("Subgroup sizes must be a positive number or a column.")

    # Validation: For P chart, defective count cannot exceed sample size
    for i, (c, s) in enumerate(zip(clean_counts, clean_sizes)):
        if c is not None and s is not None:
            if chart_upper in ("P", "P'") and c > s:
                raise ValueError(f"Row {i + 1}: Defective count ({c}) cannot exceed subgroup size ({s}).")

    # Complete subgroups indices (1-based)
    complete_subgroups: List[int] = []
    for i, (c, s) in enumerate(zip(clean_counts, clean_sizes)):
        if c is not None and s is not None:
            complete_subgroups.append(i + 1)

    if not complete_subgroups:
        raise ValueError(f"{chart_upper} Chart requires at least one complete subgroup.")

    # Estimation subsets (excluding omitted subgroups)
    estimation_subgroups = [idx for idx in complete_subgroups if idx not in omit_set]
    if not estimation_subgroups:
        raise ValueError("All complete subgroups were omitted from estimation. At least one subgroup must be included.")

    # Calculate parameter estimate or use historical parameter
    historical_p = opts.get("historical_p")
    historical_mean = opts.get("historical_mean")

    param_value: float = 0.0
    is_historical = False

    if chart_upper in ("P", "P'", "NP"):
        if historical_p is not None:
            param_value = float(historical_p)
            if not 0.0 <= param_value <= 1.0:
                raise ValueError(f"Historical proportion must be between 0 and 1, got {param_value}")
            is_historical = True
        else:
            total_defectives = sum(clean_counts[idx - 1] for idx in estimation_subgroups)  # type: ignore
            total_trials = sum(clean_sizes[idx - 1] for idx in estimation_subgroups)  # type: ignore
            if total_trials <= 0:
                raise ValueError("Total trials for estimation must be positive.")
            param_value = total_defectives / total_trials
    else:  # 'C', 'U', "U'"
        if historical_mean is not None:
            param_value = float(historical_mean)
            if param_value < 0:
                raise ValueError(f"Historical mean defect count cannot be negative: {param_value}")
            is_historical = True
        else:
            total_defects = sum(clean_counts[idx - 1] for idx in estimation_subgroups)  # type: ignore
            total_exposure = sum(clean_sizes[idx - 1] for idx in estimation_subgroups)  # type: ignore
            if total_exposure <= 0:
                raise ValueError("Total exposure for estimation must be positive.")
            param_value = total_defects / total_exposure

    # Laney Sigma Z calculation for P' and U' charts
    sigma_z = 1.0
    if chart_upper in ("P'", "U'"):
        z_vals: List[float] = []
        for idx in estimation_subgroups:
            c = clean_counts[idx - 1]
            s = clean_sizes[idx - 1]
            if c is None or s is None or s <= 0:
                continue
            if chart_upper == "P'":
                obs_k = c / s
                se_k = math.sqrt(param_value * (1.0 - param_value) / s) if param_value * (1.0 - param_value) > 0 else 0.0
            else:  # U'
                obs_k = c / s
                se_k = math.sqrt(param_value / s) if param_value > 0 else 0.0
            if se_k > 0:
                z_vals.append((obs_k - param_value) / se_k)
        if len(z_vals) >= 2:
            mr_list = [abs(z_vals[j] - z_vals[j - 1]) for j in range(1, len(z_vals))]
            amr_z = float(np.mean(mr_list))
            d2_val = d2(2)  # 1.128
            sigma_z = amr_z / d2_val if d2_val > 0 else 1.0
            if sigma_z <= 0:
                sigma_z = 1.0

    # Compute plotted observations, center line, and control limits per subgroup
    observations: List[Optional[float]] = [None] * n_rows
    center_lines: List[Optional[float]] = [None] * n_rows
    sigmas: List[Optional[float]] = [None] * n_rows
    ucl_values: List[Optional[float]] = [None] * n_rows
    lcl_values: List[Optional[float]] = [None] * n_rows

    for i in range(n_rows):
        c = clean_counts[i]
        s = clean_sizes[i]
        if c is None or s is None:
            continue

        if chart_upper in ("P", "P'"):
            obs = c / s
            cl = param_value
            sig_base = math.sqrt(param_value * (1.0 - param_value) / s) if param_value * (1.0 - param_value) > 0 else 0.0
            sig = sig_base * sigma_z if chart_upper == "P'" else sig_base
            ucl = min(1.0, cl + k_sigma * sig) if display_upper else None
            lcl = max(0.0, cl - k_sigma * sig) if display_lower else None
        elif chart_upper == "NP":
            obs = c
            cl = s * param_value
            sig = math.sqrt(s * param_value * (1.0 - param_value)) if param_value * (1.0 - param_value) > 0 else 0.0
            ucl = min(s, cl + k_sigma * sig) if display_upper else None
            lcl = max(0.0, cl - k_sigma * sig) if display_lower else None
        elif chart_upper == "C":
            obs = c
            cl = param_value
            sig = math.sqrt(param_value) if param_value > 0 else 0.0
            ucl = cl + k_sigma * sig if display_upper else None
            lcl = max(0.0, cl - k_sigma * sig) if display_lower else None
        elif chart_upper in ("U", "U'"):
            obs = c / s
            cl = param_value
            sig_base = math.sqrt(param_value / s) if param_value > 0 else 0.0
            sig = sig_base * sigma_z if chart_upper == "U'" else sig_base
            ucl = cl + k_sigma * sig if display_upper else None
            lcl = max(0.0, cl - k_sigma * sig) if display_lower else None

        observations[i] = obs
        center_lines[i] = cl
        sigmas[i] = sig
        ucl_values[i] = ucl
        lcl_values[i] = lcl

    # Configure tests
    tests_cfg = opts.get("tests", {})
    if not tests_cfg:
        # Default in StatCraft: Test 1 enabled with K=3.0
        tests_cfg = {
            "test1": {"enabled": True, "k": 3.0},
            "test2": {"enabled": False, "k": 9},
            "test3": {"enabled": False, "k": 6},
            "test4": {"enabled": False, "k": 14},
        }

    # Evaluate Nelson tests
    # Note: For evaluate_nelson_tests, if center_lines vary (NP with varying n), pass center=param_value or center per point
    # In NP chart with varying sizes, center is s_i * p.
    # evaluate_nelson_tests takes float center and list of sigmas.
    # To handle variable centers cleanly (e.g. NP with varying size), we standardize observations:
    # z_i = (obs_i - cl_i) / sig_i, and evaluate against standardized center 0.0 and sigmas = [1.0 if sig_i > 0 else None]!
    n_pts = len(observations)
    std_means: List[Optional[float]] = []
    std_sigmas: List[Optional[float]] = []
    for i in range(n_pts):
        obs = observations[i]
        cl = center_lines[i]
        sig = sigmas[i]
        if obs is not None and cl is not None and sig is not None and sig > 0:
            std_means.append(obs - cl)
            std_sigmas.append(sig)
        else:
            std_means.append(None)
            std_sigmas.append(None)

    # For tests 2, 3, 4, run on std_means / std_sigmas
    raw_test_failures = evaluate_nelson_tests(std_means, 0.0, std_sigmas, tests_cfg)

    # Format result structure
    avg_size = float(np.mean([s for s in clean_sizes if s is not None])) if clean_sizes else 0.0

    result: Dict[str, Any] = {
        "analysis": "attribute_control",
        "chart": chart_upper,
        "chart_type": chart_upper,
        "variable_name": variable_name,
        "subgroup_size_name": subgroup_size_name,
        "n_rows": n_rows,
        "n_subgroups": len(complete_subgroups),
        "missing_subgroups": n_rows - len(complete_subgroups),
        "is_constant_size": is_constant_size,
        "constant_size": constant_size_val,
        "average_subgroup_size": avg_size,
        "counts": clean_counts,
        "subgroup_sizes": clean_sizes,
        "observations": observations,
        "center_lines": center_lines,
        "center": param_value,
        "sigmas": sigmas,
        "sigma_z": sigma_z,
        "ucl": ucl_values,
        "lcl": lcl_values,
        "k_sigma": k_sigma,
        "display_upper": display_upper,
        "display_lower": display_lower,
        "is_historical": is_historical,
        "omitted_subgroups": sorted(list(omit_set)),
        "estimation_subgroups_count": len(estimation_subgroups),
        "test_failures": raw_test_failures,
        "tests_cfg": tests_cfg,
        "options": dict(opts),
    }

    # For backwards-compatibility with any legacy consumers:
    result["signals"] = sorted([idx for idx, fails in raw_test_failures.items() if 1 in fails])
    result["signal_flags"] = [(i + 1 in result["signals"]) if clean_counts[i] is not None else None for i in range(n_rows)]
    result["total_count"] = sum(c for c in clean_counts if c is not None)
    result["total_sample_size"] = sum(s for s in clean_sizes if s is not None)
    result["count"] = len(complete_subgroups)
    result["missing"] = n_rows - len(complete_subgroups)

    return result
