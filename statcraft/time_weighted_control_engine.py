"""Statistical engine for Time-Weighted Control Charts (CUSUM, EWMA, Moving Average).

Implements native StatCraft PE resource fidelity and statistical formulas matching:
- 0716-EWMADATASOURCE.MDF (EWMA Chart: MenuID 41039, HelpID 86100)
- 0836-MACHARTDATASOURCE.MDF (Moving Average Chart: MenuID 41040, HelpID 86000)
- 1026-RCUSUMDATASOURCE.MDF (CUSUM Chart: MenuID 41041, HelpID 86200)
- 1027-RCUSUMPLANANDTYPE.MDF (CUSUM Plan & Type: h, k, FIR, Reset, V-mask)
- 1008-QCHARTPARAMETERS.MDF (Parameters: Mean, Sigma, Tests)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np

from .capability_engine import c4, d2
from .attribute_control_engine import parse_subgroup_omission


def _clean_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "*":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def organize_subgroups(
    data: Sequence[Any],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
    rows_are_subgroups: bool = False,
    data_columns: Optional[Sequence[Sequence[Any]]] = None,
) -> Tuple[List[List[float]], List[int]]:
    """Organize input data into a list of subgroups (list of float lists) and sizes."""
    subgroups: List[List[float]] = []
    sizes: List[int] = []

    if rows_are_subgroups and data_columns is not None and len(data_columns) > 0:
        # Observations for a subgroup are in one row across columns
        n_rows = len(data_columns[0])
        for r in range(n_rows):
            row_vals: List[float] = []
            for col in data_columns:
                if r < len(col):
                    v = _clean_float(col[r])
                    if v is not None:
                        row_vals.append(v)
            subgroups.append(row_vals)
            sizes.append(len(row_vals))
        return subgroups, sizes

    # If subgroup_size is a sequence/column of subgroup IDs
    if isinstance(subgroup_size, (list, tuple, np.ndarray)) and len(subgroup_size) == len(data):
        curr_id = None
        curr_grp: List[float] = []
        for val, sg_id in zip(data, subgroup_size):
            v = _clean_float(val)
            if v is None:
                continue
            if curr_id is None:
                curr_id = sg_id
                curr_grp.append(v)
            elif sg_id == curr_id:
                curr_grp.append(v)
            else:
                if curr_grp:
                    subgroups.append(curr_grp)
                    sizes.append(len(curr_grp))
                curr_id = sg_id
                curr_grp = [v]
        if curr_grp:
            subgroups.append(curr_grp)
            sizes.append(len(curr_grp))
        return subgroups, sizes

    # Constant subgroup size
    n_const = 1
    if subgroup_size is not None and not isinstance(subgroup_size, (list, tuple, np.ndarray)):
        try:
            n_const = max(1, int(subgroup_size))
        except (ValueError, TypeError):
            n_const = 1

    clean_vals = [_clean_float(x) for x in data]
    clean_vals = [x for x in clean_vals if x is not None]

    if n_const == 1:
        for x in clean_vals:
            subgroups.append([x])
            sizes.append(1)
    else:
        for i in range(0, len(clean_vals), n_const):
            chunk = clean_vals[i : i + n_const]
            if chunk:
                subgroups.append(chunk)
                sizes.append(len(chunk))

    return subgroups, sizes


def estimate_within_sigma(
    subgroups: List[List[float]],
    subgroup_sizes: List[int],
    omit_indices: Set[int],
    method: str = "pooled_stdev",
) -> float:
    """Estimate within-subgroup standard deviation sigma."""
    included = [i for i in range(len(subgroups)) if (i + 1) not in omit_indices and subgroup_sizes[i] >= 1]
    if not included:
        return 1.0

    # If all subgroups are size 1 (individual observations)
    all_n1 = all(subgroup_sizes[i] == 1 for i in included)
    if all_n1:
        vals = [subgroups[i][0] for i in included]
        if len(vals) < 2:
            return 1.0
        # Average moving range of length 2
        mr_list = [abs(vals[j] - vals[j - 1]) for j in range(1, len(vals))]
        avg_mr = float(np.mean(mr_list)) if mr_list else 1.0
        d2_val = d2(2)
        return avg_mr / d2_val if d2_val > 0 else 1.0

    # Subgroups with size >= 2
    disp_indices = [i for i in included if subgroup_sizes[i] >= 2]
    if not disp_indices:
        # Fall back to stdev of subgroup means
        means = [float(np.mean(subgroups[i])) for i in included]
        return float(np.std(means, ddof=1)) if len(means) > 1 else 1.0

    if method == "rbar":
        ranges = [float(np.ptp(subgroups[i])) for i in disp_indices]
        rbar = float(np.mean(ranges)) if ranges else 0.0
        avg_n = max(2, min(50, int(round(np.mean([subgroup_sizes[i] for i in disp_indices])))))
        d2_val = d2(avg_n)
        return rbar / d2_val if d2_val > 0 else 1.0
    elif method == "sbar":
        stdevs = [float(np.std(subgroups[i], ddof=1)) for i in disp_indices]
        sbar = float(np.mean(stdevs)) if stdevs else 0.0
        avg_n = max(2, min(50, int(round(np.mean([subgroup_sizes[i] for i in disp_indices])))))
        c4_val = c4(avg_n)
        return sbar / c4_val if c4_val > 0 else 1.0
    else:
        # pooled_stdev (default in StatCraft)
        sum_ss = sum((subgroup_sizes[i] - 1) * (float(np.std(subgroups[i], ddof=1)) ** 2) for i in disp_indices)
        total_df = sum(subgroup_sizes[i] - 1 for i in disp_indices)
        if total_df > 0:
            sp = math.sqrt(sum_ss / total_df)
            c4_val = c4(total_df + 1)
            return sp / c4_val if c4_val > 0 else sp
        return 1.0


def run_ewma_control(
    data: Sequence[Any],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
    weight: float = 0.2,
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Data",
    subgroup_size_name: Optional[str] = None,
    rows_are_subgroups: bool = False,
    data_columns: Optional[Sequence[Sequence[Any]]] = None,
) -> Dict[str, Any]:
    """Compute Exponentially Weighted Moving Average (EWMA) control chart."""
    opts = options or {}
    lambda_w = max(0.001, min(1.0, float(opts.get("weight", weight))))
    k_sigma = float(opts.get("k_sigma", 3.0))
    hist_mean = _clean_float(opts.get("historical_mean"))
    hist_sigma = _clean_float(opts.get("historical_sigma"))
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    method = str(opts.get("estimation_method", "pooled_stdev")).lower()

    subgroups, sizes = organize_subgroups(data, subgroup_size, rows_are_subgroups, data_columns)
    m = len(subgroups)
    if m == 0:
        raise ValueError("No valid observations provided for EWMA Chart.")

    means: List[float] = [float(np.mean(g)) if len(g) > 0 else 0.0 for g in subgroups]

    # Center Line (Mean)
    included = [i for i in range(m) if (i + 1) not in omit and sizes[i] >= 1]
    if not included:
        included = list(range(m))

    if hist_mean is not None:
        cl = hist_mean
    else:
        tot_n = sum(sizes[i] for i in included)
        cl = sum(sizes[i] * means[i] for i in included) / tot_n if tot_n > 0 else float(np.mean(means))

    # Standard deviation sigma
    if hist_sigma is not None and hist_sigma > 0:
        sigma = hist_sigma
    else:
        sigma = estimate_within_sigma(subgroups, sizes, omit, method)
        if sigma <= 0:
            sigma = 1.0

    # Calculate EWMA statistics and dynamic control limits
    ewma_values: List[float] = []
    ucl_list: List[float] = []
    lcl_list: List[float] = []
    se_list: List[float] = []

    prev_z = cl
    cumulative_term = 0.0

    for i in range(m):
        xi = means[i]
        ni = max(1, sizes[i])
        zi = lambda_w * xi + (1.0 - lambda_w) * prev_z
        ewma_values.append(zi)
        prev_z = zi

        # Dynamic exact variance for equal or unequal subgroup sizes
        # For equal n: sigma * sqrt(lambda / (2 - lambda) * [1 - (1 - lambda)^(2*(i+1))]) / sqrt(n)
        # General: sum_{j=0}^i (1 - lambda)^(2*(i - j)) * (sigma^2 / n_j) * (lambda^2)
        # Note: at j=i, factor is lambda^2 / ni
        cumulative_term = (1.0 - lambda_w) ** 2 * cumulative_term + (lambda_w ** 2) / ni
        var_zi = (sigma ** 2) * cumulative_term
        se_zi = math.sqrt(max(0.0, var_zi))
        se_list.append(se_zi)

        ucl_list.append(cl + k_sigma * se_zi)
        lcl_list.append(cl - k_sigma * se_zi)

    # Test 1: Beyond control limits
    test1_signals: List[int] = []
    for i in range(m):
        z = ewma_values[i]
        if z > ucl_list[i] or z < lcl_list[i]:
            test1_signals.append(i + 1)

    return {
        "analysis": "time_weighted_control",
        "chart_type": "EWMA",
        "variable_name": variable_name,
        "subgroup_size_name": subgroup_size_name,
        "weight": lambda_w,
        "k_sigma": k_sigma,
        "center_line": cl,
        "sigma": sigma,
        "estimation_method": method,
        "historical_mean": hist_mean,
        "historical_sigma": hist_sigma,
        "omit_subgroups": sorted(omit),
        "k_subgroups": m,
        "subgroup_sizes": sizes,
        "means": means,
        "values": ewma_values,
        "ucl": ucl_list,
        "lcl": lcl_list,
        "se": se_list,
        "test_failures": {1: test1_signals} if test1_signals else {},
        "signals": test1_signals,
    }


def run_moving_average_control(
    data: Sequence[Any],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
    span: int = 3,
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Data",
    subgroup_size_name: Optional[str] = None,
    rows_are_subgroups: bool = False,
    data_columns: Optional[Sequence[Sequence[Any]]] = None,
) -> Dict[str, Any]:
    """Compute Moving Average (MA) control chart."""
    opts = options or {}
    w = max(1, int(opts.get("span", opts.get("length", span))))
    k_sigma = float(opts.get("k_sigma", 3.0))
    hist_mean = _clean_float(opts.get("historical_mean"))
    hist_sigma = _clean_float(opts.get("historical_sigma"))
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    method = str(opts.get("estimation_method", "pooled_stdev")).lower()

    subgroups, sizes = organize_subgroups(data, subgroup_size, rows_are_subgroups, data_columns)
    m = len(subgroups)
    if m == 0:
        raise ValueError("No valid observations provided for Moving Average Chart.")

    means: List[float] = [float(np.mean(g)) if len(g) > 0 else 0.0 for g in subgroups]

    # Center Line (Mean)
    included = [i for i in range(m) if (i + 1) not in omit and sizes[i] >= 1]
    if not included:
        included = list(range(m))

    if hist_mean is not None:
        cl = hist_mean
    else:
        tot_n = sum(sizes[i] for i in included)
        cl = sum(sizes[i] * means[i] for i in included) / tot_n if tot_n > 0 else float(np.mean(means))

    # Standard deviation sigma
    if hist_sigma is not None and hist_sigma > 0:
        sigma = hist_sigma
    else:
        sigma = estimate_within_sigma(subgroups, sizes, omit, method)
        if sigma <= 0:
            sigma = 1.0

    # Calculate Moving Average statistics and limits
    ma_values: List[float] = []
    ucl_list: List[float] = []
    lcl_list: List[float] = []
    se_list: List[float] = []

    for i in range(m):
        start_idx = max(0, i - w + 1)
        window_sizes = sizes[start_idx : i + 1]
        window_means = means[start_idx : i + 1]

        sum_n = sum(window_sizes)
        if sum_n > 0:
            ma_val = sum(n_j * m_j for n_j, m_j in zip(window_sizes, window_means)) / sum_n
            # SE = sigma / sqrt(sum_n)
            se_ma = sigma / math.sqrt(sum_n)
        else:
            ma_val = cl
            se_ma = 0.0

        ma_values.append(ma_val)
        se_list.append(se_ma)
        ucl_list.append(cl + k_sigma * se_ma)
        lcl_list.append(cl - k_sigma * se_ma)

    # Test 1: Beyond control limits
    test1_signals: List[int] = []
    for i in range(m):
        val = ma_values[i]
        if val > ucl_list[i] or val < lcl_list[i]:
            test1_signals.append(i + 1)

    return {
        "analysis": "time_weighted_control",
        "chart_type": "MA",
        "variable_name": variable_name,
        "subgroup_size_name": subgroup_size_name,
        "span": w,
        "k_sigma": k_sigma,
        "center_line": cl,
        "sigma": sigma,
        "estimation_method": method,
        "historical_mean": hist_mean,
        "historical_sigma": hist_sigma,
        "omit_subgroups": sorted(omit),
        "k_subgroups": m,
        "subgroup_sizes": sizes,
        "means": means,
        "values": ma_values,
        "ucl": ucl_list,
        "lcl": lcl_list,
        "se": se_list,
        "test_failures": {1: test1_signals} if test1_signals else {},
        "signals": test1_signals,
    }


def run_cusum_control(
    data: Sequence[Any],
    subgroup_size: Union[int, float, Sequence[Any], None] = 1,
    target: Optional[float] = None,
    h: float = 4.0,
    k: float = 0.5,
    options: Optional[Dict[str, Any]] = None,
    variable_name: str = "Data",
    subgroup_size_name: Optional[str] = None,
    rows_are_subgroups: bool = False,
    data_columns: Optional[Sequence[Sequence[Any]]] = None,
) -> Dict[str, Any]:
    """Compute Cumulative Sum (CUSUM) control chart (Tabular CUSUM or V-mask)."""
    opts = options or {}
    h_val = float(opts.get("h", h))
    k_val = float(opts.get("k", k))
    use_fir = bool(opts.get("use_fir", False))
    fir_val = float(opts.get("fir", h_val / 2.0 if use_fir else 0.0))
    reset_ooc = bool(opts.get("reset", False))
    cusum_type = str(opts.get("cusum_type", "tabular")).lower()
    omit = parse_subgroup_omission(opts.get("omit_subgroups"))
    method = str(opts.get("estimation_method", "pooled_stdev")).lower()

    subgroups, sizes = organize_subgroups(data, subgroup_size, rows_are_subgroups, data_columns)
    m = len(subgroups)
    if m == 0:
        raise ValueError("No valid observations provided for CUSUM Chart.")

    means: List[float] = [float(np.mean(g)) if len(g) > 0 else 0.0 for g in subgroups]

    included = [i for i in range(m) if (i + 1) not in omit and sizes[i] >= 1]
    if not included:
        included = list(range(m))

    tgt_opt = _clean_float(opts.get("target", target))
    if tgt_opt is not None:
        target_val = tgt_opt
    else:
        tot_n = sum(sizes[i] for i in included)
        target_val = sum(sizes[i] * means[i] for i in included) / tot_n if tot_n > 0 else float(np.mean(means))

    hist_sigma = _clean_float(opts.get("historical_sigma"))
    if hist_sigma is not None and hist_sigma > 0:
        sigma = hist_sigma
    else:
        sigma = estimate_within_sigma(subgroups, sizes, omit, method)
        if sigma <= 0:
            sigma = 1.0

    # Calculate Tabular CUSUM
    # C+_i = max(0, y_i - k + C+_{i-1})
    # C-_i = max(0, -y_i - k + C-_{i-1})
    # where y_i = (mean_i - target) / (sigma / sqrt(n_i))
    c_plus: List[float] = []
    c_minus: List[float] = []
    c_minus_plotted: List[float] = []  # Plotted as negative values (-C-) matching StatCraft
    ucl_list: List[float] = []
    lcl_list: List[float] = []
    cl_list: List[float] = []
    y_scores: List[float] = []

    prev_cp = fir_val if use_fir else 0.0
    prev_cm = fir_val if use_fir else 0.0

    test1_signals: List[int] = []

    for i in range(m):
        ni = max(1, sizes[i])
        se_i = sigma / math.sqrt(ni)
        yi = (means[i] - target_val) / se_i if se_i > 0 else 0.0
        y_scores.append(yi)

        cp = max(0.0, yi - k_val + prev_cp)
        cm = max(0.0, -yi - k_val + prev_cm)

        c_plus.append(cp)
        c_minus.append(cm)
        c_minus_plotted.append(-cm)

        ucl_list.append(h_val)
        lcl_list.append(-h_val)
        cl_list.append(0.0)

        # Check out of control
        if cp > h_val or cm > h_val:
            test1_signals.append(i + 1)
            if reset_ooc:
                cp = fir_val if use_fir else 0.0
                cm = fir_val if use_fir else 0.0

        prev_cp = cp
        prev_cm = cm

    return {
        "analysis": "time_weighted_control",
        "chart_type": "CUSUM",
        "cusum_type": cusum_type,
        "variable_name": variable_name,
        "subgroup_size_name": subgroup_size_name,
        "target": target_val,
        "h": h_val,
        "k": k_val,
        "use_fir": use_fir,
        "fir": fir_val,
        "reset": reset_ooc,
        "center_line": 0.0,
        "sigma": sigma,
        "estimation_method": method,
        "historical_sigma": hist_sigma,
        "omit_subgroups": sorted(omit),
        "k_subgroups": m,
        "subgroup_sizes": sizes,
        "means": means,
        "y_scores": y_scores,
        "c_plus": c_plus,
        "c_minus": c_minus,
        "values": c_plus,  # default values for plotting/interaction
        "c_minus_plotted": c_minus_plotted,
        "ucl": ucl_list,
        "lcl": lcl_list,
        "test_failures": {1: test1_signals} if test1_signals else {},
        "signals": test1_signals,
    }
