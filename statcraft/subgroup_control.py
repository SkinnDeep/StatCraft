"""Subgroup control charts (Xbar-R and Xbar-S) statistical engine.

Implements StatCraft PE resource fidelity and statistical formulas for:
- XRCHARTDATASOURCE.MDF (Xbar-R Chart)
- XSCHARTDATASOURCE.MDF (Xbar-S Chart)
- QCHARTPARAMETERS.MDF (Parameters, Estimation, Limits, Tests, Storage)
- QCHARTESTIMATE.MDF (Rbar, Sbar, Pooled StDev, unbiasing constants c4, c5, d2, d3, subgroup omission)
- QCHARTSLIMITS.MDF (K sigma, upper/lower limit toggles)
- QCHARTTESTS.MDF (All 8 Nelson / Western Electric tests)
- QCHARTSTORAGE.MDF (Storage of plotted points, center lines, control limits, subgroup sizes, test results)
"""
from __future__ import annotations

import copy
import math
from typing import Any
import numpy as np

from .engine import normalize_numeric
from .model import Column, Worksheet

# Standard published d2 and d3 constants table for n=2..50 (NIST / StatCraft unbiasing tables).
D2_TABLE = {
    2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078,
    11: 3.173, 12: 3.258, 13: 3.336, 14: 3.407, 15: 3.472, 16: 3.532, 17: 3.588, 18: 3.640,
    19: 3.689, 20: 3.735, 21: 3.778, 22: 3.819, 23: 3.858, 24: 3.895, 25: 3.931,
    26: 3.964, 27: 3.997, 28: 4.027, 29: 4.057, 30: 4.086, 31: 4.113, 32: 4.139, 33: 4.165,
    34: 4.189, 35: 4.213, 36: 4.236, 37: 4.259, 38: 4.280, 39: 4.301, 40: 4.322,
    41: 4.341, 42: 4.361, 43: 4.379, 44: 4.398, 45: 4.415, 46: 4.433, 47: 4.450,
    48: 4.466, 49: 4.482, 50: 4.498,
}

D3_TABLE = {
    2: 0.8525, 3: 0.8884, 4: 0.8798, 5: 0.8641, 6: 0.8480, 7: 0.8332, 8: 0.8198, 9: 0.8078, 10: 0.7971,
    11: 0.7873, 12: 0.7785, 13: 0.7704, 14: 0.7630, 15: 0.7562, 16: 0.7499, 17: 0.7441, 18: 0.7386,
    19: 0.7335, 20: 0.7287, 21: 0.7242, 22: 0.7199, 23: 0.7159, 24: 0.7121, 25: 0.7084,
    26: 0.7050, 27: 0.7017, 28: 0.6985, 29: 0.6955, 30: 0.6927, 31: 0.6899, 32: 0.6873, 33: 0.6848,
    34: 0.6823, 35: 0.6800, 36: 0.6778, 37: 0.6756, 38: 0.6735, 39: 0.6715, 40: 0.6696,
    41: 0.6677, 42: 0.6659, 43: 0.6641, 44: 0.6624, 45: 0.6608, 46: 0.6592, 47: 0.6577,
    48: 0.6562, 49: 0.6547, 50: 0.6533,
}


def c4(n: int) -> float:
    """Exact unbiasing constant for sample standard deviation: E(S) / sigma."""
    if n < 2:
        return 1.0
    return math.sqrt(2.0 / (n - 1)) * math.exp(math.lgamma(n / 2.0) - math.lgamma((n - 1) / 2.0))


def c5(n: int) -> float:
    """Standard error constant for sample standard deviation: Var(S)^0.5 / sigma."""
    if n < 2:
        return 0.0
    c = c4(n)
    return math.sqrt(max(0.0, 1.0 - c * c))


def d2(n: int) -> float:
    """Expected sample range from standard normal distribution."""
    if n in D2_TABLE:
        return D2_TABLE[n]
    if n < 2:
        return 1.0
    # Approximate for large n
    return 3.0 * math.sqrt(math.log(n))


def d3(n: int) -> float:
    """Standard deviation of sample range from standard normal distribution."""
    if n in D3_TABLE:
        return D3_TABLE[n]
    if n < 2:
        return 0.0
    return 0.65


def control_chart_settings(options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and normalize settings for subgroup control charts."""
    opts = copy.deepcopy(options or {})
    chart_type = str(opts.get('chart_type', 'xbar_r')).lower()
    if chart_type not in ('xbar_r', 'xbar_s', 'xbar', 'r', 's'):
        raise ValueError("Chart type must be 'xbar_r', 'xbar_s', 'xbar', 'r', or 's'.")

    k_raw = opts.get('k_sigma', 3.0)
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

    if not (0.1 <= k_sigma <= 10.0):
        raise ValueError("Number of standard deviations (k_sigma) must be between 0.1 and 10.0.")

    warning_limits = bool(opts.get('warning_limits', False)) or len(k_list) > 1
    warning_k = float(opts.get('warning_k', 2.0))
    if len(k_list) > 1 and k_list[0] < k_sigma:
        warning_k = k_list[0]
    display_zones = bool(opts.get('display_zones', False)) or (len(k_list) >= 3)

    display_upper = bool(opts.get('display_upper', True))
    display_lower = bool(opts.get('display_lower', True))

    historical_mean = opts.get('historical_mean')
    if historical_mean is not None:
        try:
            historical_mean = float(historical_mean)
        except (ValueError, TypeError):
            raise ValueError("Historical mean must be a finite number.")

    historical_sigma = opts.get('historical_sigma')
    if historical_sigma is not None:
        try:
            historical_sigma = float(historical_sigma)
            if historical_sigma <= 0:
                raise ValueError("Historical standard deviation must be positive.")
        except (ValueError, TypeError):
            raise ValueError("Historical standard deviation must be a positive number.")

    method = str(opts.get('estimation_method', 'default')).lower()
    if method == 'default':
        method = 'rbar' if chart_type in ('xbar_r', 'xbar', 'r') else 'sbar'
    if method not in ('rbar', 'sbar', 'pooled_stdev'):
        raise ValueError("Estimation method must be 'rbar', 'sbar', or 'pooled_stdev'.")

    unbiasing = bool(opts.get('unbiasing', True))

    omit_subgroups_raw = opts.get('omit_subgroups', [])
    omit_subgroups: list[int] = []
    if isinstance(omit_subgroups_raw, (list, tuple, set)):
        for item in omit_subgroups_raw:
            try:
                v = int(item)
                if v > 0:
                    omit_subgroups.append(v)
            except (ValueError, TypeError):
                pass
    elif isinstance(omit_subgroups_raw, str):
        tokens = omit_subgroups_raw.replace(',', ' ').split()
        for tok in tokens:
            try:
                omit_subgroups.append(int(tok))
            except ValueError:
                pass
    omit_subgroups = sorted(set(omit_subgroups))

    # Nelson Tests 1-8 configuration
    tests_in = opts.get('tests', {})
    tests_cfg = {
        'test1': {'enabled': bool(tests_in.get('test1', {}).get('enabled', True)), 'k': float(tests_in.get('test1', {}).get('k', 3.0))},
        'test2': {'enabled': bool(tests_in.get('test2', {}).get('enabled', False)), 'k': int(tests_in.get('test2', {}).get('k', 9))},
        'test3': {'enabled': bool(tests_in.get('test3', {}).get('enabled', False)), 'k': int(tests_in.get('test3', {}).get('k', 6))},
        'test4': {'enabled': bool(tests_in.get('test4', {}).get('enabled', False)), 'k': int(tests_in.get('test4', {}).get('k', 14))},
        'test5': {'enabled': bool(tests_in.get('test5', {}).get('enabled', False)), 'k': int(tests_in.get('test5', {}).get('k', 2))},
        'test6': {'enabled': bool(tests_in.get('test6', {}).get('enabled', False)), 'k': int(tests_in.get('test6', {}).get('k', 4))},
        'test7': {'enabled': bool(tests_in.get('test7', {}).get('enabled', False)), 'k': int(tests_in.get('test7', {}).get('k', 15))},
        'test8': {'enabled': bool(tests_in.get('test8', {}).get('enabled', False)), 'k': int(tests_in.get('test8', {}).get('k', 8))},
    }

    # Storage options
    store_in = opts.get('storage', {})
    storage_cfg = {
        'points': bool(store_in.get('points', False)),
        'center_line': bool(store_in.get('center_line', False)),
        'control_limits': bool(store_in.get('control_limits', False)),
        'subgroup_sizes': bool(store_in.get('subgroup_sizes', False)),
        'test_results': bool(store_in.get('test_results', False)),
    }

    return {
        'chart_type': chart_type,
        'k_sigma': k_sigma,
        'k_list': k_list,
        'warning_limits': warning_limits,
        'warning_k': warning_k,
        'display_zones': display_zones,
        'display_upper': display_upper,
        'display_lower': display_lower,
        'historical_mean': historical_mean,
        'historical_sigma': historical_sigma,
        'estimation_method': method,
        'unbiasing': unbiasing,
        'omit_subgroups': omit_subgroups,
        'tests': tests_cfg,
        'storage': storage_cfg,
    }


def evaluate_nelson_tests(means: list[float | None],
                          center: float,
                          sigmas: list[float | None],
                          tests_cfg: dict[str, Any]) -> dict[int, list[int]]:
    """Evaluate 8 Nelson / Western Electric control chart rules on subgroup means.

    Returns mapping from 1-based subgroup number to list of failed test numbers.
    """
    failures: dict[int, list[int]] = {}

    def add_fail(subgroup_idx_1based: int, test_num: int):
        failures.setdefault(subgroup_idx_1based, []).append(test_num)

    n_pts = len(means)
    z_scores: list[float | None] = []
    for m, s in zip(means, sigmas):
        if m is not None and s is not None and s > 0:
            z_scores.append((m - center) / s)
        else:
            z_scores.append(None)

    # Test 1: 1 point > K standard deviations from center line
    t1 = tests_cfg.get('test1', {})
    if t1.get('enabled', True):
        k1 = float(t1.get('k', 3.0))
        for i, z in enumerate(z_scores):
            if z is not None and abs(z) > k1:
                add_fail(i + 1, 1)

    # Test 2: K points in a row on same side of center line
    t2 = tests_cfg.get('test2', {})
    if t2.get('enabled', False):
        k2 = int(t2.get('k', 9))
        if k2 >= 2:
            pos_run = 0
            neg_run = 0
            for i, z in enumerate(z_scores):
                if z is None:
                    pos_run = 0
                    neg_run = 0
                    continue
                if z > 0:
                    pos_run += 1
                    neg_run = 0
                elif z < 0:
                    neg_run += 1
                    pos_run = 0
                else:
                    pos_run = 0
                    neg_run = 0
                if pos_run >= k2 or neg_run >= k2:
                    add_fail(i + 1, 2)

    # Test 3: K points in a row, all increasing or all decreasing
    t3 = tests_cfg.get('test3', {})
    if t3.get('enabled', False):
        k3 = int(t3.get('k', 6))
        if k3 >= 3:
            inc_run = 1
            dec_run = 1
            for i in range(1, n_pts):
                m_prev = means[i - 1]
                m_curr = means[i]
                if m_prev is None or m_curr is None:
                    inc_run = 1
                    dec_run = 1
                    continue
                if m_curr > m_prev:
                    inc_run += 1
                    dec_run = 1
                elif m_curr < m_prev:
                    dec_run += 1
                    inc_run = 1
                else:
                    inc_run = 1
                    dec_run = 1
                if inc_run >= k3 or dec_run >= k3:
                    add_fail(i + 1, 3)

    # Test 4: K points in a row, alternating up and down
    t4 = tests_cfg.get('test4', {})
    if t4.get('enabled', False):
        k4 = int(t4.get('k', 14))
        if k4 >= 4:
            alt_run = 1
            last_dir = 0
            for i in range(1, n_pts):
                m_prev = means[i - 1]
                m_curr = means[i]
                if m_prev is None or m_curr is None:
                    alt_run = 1
                    last_dir = 0
                    continue
                diff = m_curr - m_prev
                if diff > 0:
                    current_dir = 1
                elif diff < 0:
                    current_dir = -1
                else:
                    current_dir = 0
                if current_dir != 0 and current_dir == -last_dir:
                    alt_run += 1
                    last_dir = current_dir
                elif current_dir != 0:
                    alt_run = 2
                    last_dir = current_dir
                else:
                    alt_run = 1
                    last_dir = 0
                if alt_run >= k4:
                    add_fail(i + 1, 4)

    # Test 5: K out of K+1 points > 2 standard deviations from center line (same side)
    t5 = tests_cfg.get('test5', {})
    if t5.get('enabled', False):
        k5 = int(t5.get('k', 2))
        win_size = k5 + 1
        for i in range(win_size - 1, n_pts):
            window = z_scores[i - win_size + 1 : i + 1]
            if any(z is None for z in window):
                continue
            pos_count = sum(1 for z in window if z > 2.0)
            neg_count = sum(1 for z in window if z < -2.0)
            if pos_count >= k5 or neg_count >= k5:
                add_fail(i + 1, 5)

    # Test 6: K out of K+1 points > 1 standard deviations from center line (same side)
    t6 = tests_cfg.get('test6', {})
    if t6.get('enabled', False):
        k6 = int(t6.get('k', 4))
        win_size = k6 + 1
        for i in range(win_size - 1, n_pts):
            window = z_scores[i - win_size + 1 : i + 1]
            if any(z is None for z in window):
                continue
            pos_count = sum(1 for z in window if z > 1.0)
            neg_count = sum(1 for z in window if z < -1.0)
            if pos_count >= k6 or neg_count >= k6:
                add_fail(i + 1, 6)

    # Test 7: K points in a row within 1 standard deviation of center line (either side)
    t7 = tests_cfg.get('test7', {})
    if t7.get('enabled', False):
        k7 = int(t7.get('k', 15))
        zone_c_run = 0
        for i, z in enumerate(z_scores):
            if z is not None and -1.0 <= z <= 1.0:
                zone_c_run += 1
            else:
                zone_c_run = 0
            if zone_c_run >= k7:
                add_fail(i + 1, 7)

    # Test 8: K points in a row > 1 standard deviation from center line (either side)
    t8 = tests_cfg.get('test8', {})
    if t8.get('enabled', False):
        k8 = int(t8.get('k', 8))
        no_zone_c_run = 0
        for i, z in enumerate(z_scores):
            if z is not None and abs(z) > 1.0:
                no_zone_c_run += 1
            else:
                no_zone_c_run = 0
            if no_zone_c_run >= k8:
                add_fail(i + 1, 8)

    # Sort test numbers per subgroup
    for k in failures:
        failures[k] = sorted(set(failures[k]))
    return failures


def fit_subgroups(subgroups: list[list[float | None]],
                  chart_type: str = 'xbar_r',
                  options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fit Xbar-R or Xbar-S control chart on subgroup data."""
    opts = control_chart_settings({**(options or {}), 'chart_type': chart_type})
    k_sigma = opts['k_sigma']
    method = opts['estimation_method']
    unbiasing = opts['unbiasing']
    omit = set(opts['omit_subgroups'])

    if not subgroups:
        raise ValueError("Subgroup data must contain at least one subgroup.")

    subgroup_sizes: list[int] = []
    means: list[float | None] = []
    ranges: list[float | None] = []
    stdevs: list[float | None] = []

    for group in subgroups:
        clean = [float(v) for v in group if v is not None and math.isfinite(v)]
        n = len(clean)
        subgroup_sizes.append(n)
        if n == 0:
            means.append(None)
            ranges.append(None)
            stdevs.append(None)
        else:
            m = float(np.mean(clean))
            means.append(m)
            if n >= 2:
                r = float(np.ptp(clean))
                s = float(np.std(clean, ddof=1))
                ranges.append(r)
                stdevs.append(s)
            else:
                ranges.append(None)
                stdevs.append(None)

    k_subgroups = len(subgroups)
    est_indices = [i for i in range(k_subgroups) if (i + 1) not in omit and subgroup_sizes[i] >= 1]
    if not est_indices:
        raise ValueError("At least one subgroup must be available to estimate parameters.")

    # 1. Center Line for Xbar
    if opts['historical_mean'] is not None:
        xbar_center = opts['historical_mean']
    else:
        total_obs = sum(subgroup_sizes[i] for i in est_indices)
        if total_obs == 0:
            raise ValueError("No observations available to calculate center line.")
        xbar_center = sum(subgroup_sizes[i] * means[i] for i in est_indices if means[i] is not None) / total_obs

    # 2. Estimate within-subgroup variation sigma
    disp_indices = [i for i in est_indices if subgroup_sizes[i] >= 2]
    if opts['historical_sigma'] is not None:
        sigma_hat = opts['historical_sigma']
        disp_center = None
    elif not disp_indices:
        sigma_hat = 0.0
        disp_center = 0.0
    else:
        if method == 'pooled_stdev':
            sum_ss = sum((subgroup_sizes[i] - 1) * (stdevs[i] ** 2) for i in disp_indices if stdevs[i] is not None)
            total_df = sum(subgroup_sizes[i] - 1 for i in disp_indices)
            if total_df > 0:
                sp = math.sqrt(sum_ss / total_df)
                c4_val = c4(total_df + 1) if unbiasing else 1.0
                sigma_hat = sp / c4_val if c4_val > 0 else sp
            else:
                sigma_hat = 0.0
        elif chart_type in ('xbar_r', 'xbar', 'r'):
            # Rbar method
            r_vals = [ranges[i] for i in disp_indices if ranges[i] is not None]
            rbar = float(np.mean(r_vals)) if r_vals else 0.0
            avg_n = int(round(np.mean([subgroup_sizes[i] for i in disp_indices])))
            d2_val = d2(avg_n) if unbiasing else 1.0
            sigma_hat = rbar / d2_val if d2_val > 0 else 0.0
        else:
            # Sbar method
            s_vals = [stdevs[i] for i in disp_indices if stdevs[i] is not None]
            sbar = float(np.mean(s_vals)) if s_vals else 0.0
            avg_n = int(round(np.mean([subgroup_sizes[i] for i in disp_indices])))
            c4_val = c4(avg_n) if unbiasing else 1.0
            sigma_hat = sbar / c4_val if c4_val > 0 else 0.0

    # Dispersion center line
    if chart_type in ('xbar_r', 'xbar', 'r'):
        if opts['historical_sigma'] is not None:
            avg_n = int(round(np.mean([subgroup_sizes[i] for i in range(k_subgroups) if subgroup_sizes[i] >= 2]))) if any(n >= 2 for n in subgroup_sizes) else 2
            disp_center = d2(avg_n) * sigma_hat
        else:
            r_valid = [ranges[i] for i in est_indices if ranges[i] is not None]
            disp_center = float(np.mean(r_valid)) if r_valid else 0.0
    else:
        if opts['historical_sigma'] is not None:
            avg_n = int(round(np.mean([subgroup_sizes[i] for i in range(k_subgroups) if subgroup_sizes[i] >= 2]))) if any(n >= 2 for n in subgroup_sizes) else 2
            disp_center = (c4(avg_n) if unbiasing else 1.0) * sigma_hat
        else:
            s_valid = [stdevs[i] for i in est_indices if stdevs[i] is not None]
            disp_center = float(np.mean(s_valid)) if s_valid else 0.0

    # 3. Control Limits for each subgroup
    xbar_lcl_list: list[float | None] = []
    xbar_ucl_list: list[float | None] = []
    xbar_se_list: list[float | None] = []
    disp_lcl_list: list[float | None] = []
    disp_ucl_list: list[float | None] = []

    for n in subgroup_sizes:
        if n >= 1 and sigma_hat >= 0:
            se = sigma_hat / math.sqrt(n)
            xbar_se_list.append(se)
            lcl = xbar_center - k_sigma * se if opts['display_lower'] else None
            ucl = xbar_center + k_sigma * se if opts['display_upper'] else None
            xbar_lcl_list.append(lcl)
            xbar_ucl_list.append(ucl)
        else:
            xbar_se_list.append(None)
            xbar_lcl_list.append(None)
            xbar_ucl_list.append(None)

        if n >= 2 and sigma_hat >= 0:
            if chart_type in ('xbar_r', 'xbar', 'r'):
                d2_val = d2(n)
                d3_val = d3(n)
                r_cl = d2_val * sigma_hat if opts['historical_sigma'] is not None else disp_center
                r_lcl = max(0.0, r_cl - 3.0 * d3_val * sigma_hat) if opts['display_lower'] else None
                r_ucl = r_cl + 3.0 * d3_val * sigma_hat if opts['display_upper'] else None
                disp_lcl_list.append(r_lcl)
                disp_ucl_list.append(r_ucl)
            else:
                c4_val = c4(n)
                c5_val = c5(n)
                s_cl = (c4_val if unbiasing else 1.0) * sigma_hat if opts['historical_sigma'] is not None else disp_center
                s_lcl = max(0.0, s_cl - 3.0 * c5_val * sigma_hat) if opts['display_lower'] else None
                s_ucl = s_cl + 3.0 * c5_val * sigma_hat if opts['display_upper'] else None
                disp_lcl_list.append(s_lcl)
                disp_ucl_list.append(s_ucl)
        else:
            disp_lcl_list.append(None)
            disp_ucl_list.append(None)

    # Warning Limits (Shewhart Extended Limits)
    xbar_uwl_list: list[float | None] = []
    xbar_lwl_list: list[float | None] = []
    disp_uwl_list: list[float | None] = []
    disp_lwl_list: list[float | None] = []

    has_warn = opts.get('warning_limits', False) or opts.get('display_zones', False)
    warn_k = float(opts.get('warning_k', 2.0))

    for idx, n in enumerate(subgroup_sizes):
        se = xbar_se_list[idx]
        if has_warn and se is not None:
            uwl = xbar_center + warn_k * se if opts['display_upper'] else None
            lwl = xbar_center - warn_k * se if opts['display_lower'] else None
            xbar_uwl_list.append(uwl)
            xbar_lwl_list.append(lwl)
        else:
            xbar_uwl_list.append(None)
            xbar_lwl_list.append(None)

        if has_warn and n >= 2 and sigma_hat >= 0:
            if chart_type == 'xbar_r':
                d2_val = d2(n)
                d3_val = d3(n)
                r_cl = d2_val * sigma_hat if opts['historical_sigma'] is not None else disp_center
                r_lwl = max(0.0, r_cl - warn_k * d3_val * sigma_hat) if opts['display_lower'] else None
                r_uwl = r_cl + warn_k * d3_val * sigma_hat if opts['display_upper'] else None
                disp_lwl_list.append(r_lwl)
                disp_uwl_list.append(r_uwl)
            else:
                c4_val = c4(n)
                c5_val = c5(n)
                s_cl = (c4_val if unbiasing else 1.0) * sigma_hat if opts['historical_sigma'] is not None else disp_center
                s_lwl = max(0.0, s_cl - warn_k * c5_val * sigma_hat) if opts['display_lower'] else None
                s_uwl = s_cl + warn_k * c5_val * sigma_hat if opts['display_upper'] else None
                disp_lwl_list.append(s_lwl)
                disp_uwl_list.append(s_uwl)
        else:
            disp_lwl_list.append(None)
            disp_uwl_list.append(None)

    # 4. Evaluate Tests 1-8 on Xbar
    test_failures = evaluate_nelson_tests(means, xbar_center, xbar_se_list, opts['tests'])

    # Test 1 on dispersion chart (R or S)
    disp_signals: list[int] = []
    disp_vals = ranges if chart_type in ('xbar_r', 'xbar', 'r') else stdevs
    for i in range(k_subgroups):
        v = disp_vals[i]
        lcl = disp_lcl_list[i]
        ucl = disp_ucl_list[i]
        if v is not None:
            if (lcl is not None and v < lcl) or (ucl is not None and v > ucl):
                disp_signals.append(i + 1)

    warnings: list[str] = []
    if len(disp_indices) == 1:
        warnings.append("Only one complete subgroup: estimated limits are preliminary.")
    if sigma_hat == 0:
        warnings.append("Zero estimated within-subgroup variation: control limits coincide.")
    if omit:
        warnings.append(f"Subgroups omitted from estimation: {sorted(omit)}")

    return {
        'analysis': 'subgroup_control',
        'chart_type': chart_type,
        'options': opts,
        'k_subgroups': k_subgroups,
        'subgroup_sizes': subgroup_sizes,
        'means': means,
        'ranges': ranges,
        'stdevs': stdevs,
        'disp_values': ranges if chart_type in ('xbar_r', 'xbar', 'r') else stdevs,
        'xbar_center': xbar_center,
        'xbar_lcl': xbar_lcl_list,
        'xbar_ucl': xbar_ucl_list,
        'disp_center': disp_center,
        'disp_lcl': disp_lcl_list,
        'disp_ucl': disp_ucl_list,
        'xbar_uwl': xbar_uwl_list,
        'xbar_lwl': xbar_lwl_list,
        'disp_uwl': disp_uwl_list,
        'disp_lwl': disp_lwl_list,
        'warning_limits': has_warn,
        'warning_k': warn_k,
        'display_zones': opts.get('display_zones', False),
        'within_stdev': sigma_hat,
        'estimation_method': method,
        'unbiasing': unbiasing,
        'test_failures': test_failures,
        'disp_signals': disp_signals,
        'warnings': warnings,
    }


def fit_from_worksheet(worksheet: Worksheet,
                       stacked: bool,
                       response_index: int | None = None,
                       factor_index: int | None = None,
                       indices: list[int] | None = None,
                       subgroup_size: int | None = None,
                       chart_type: str = 'xbar_r',
                       options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fit subgroup control chart directly from worksheet columns."""
    subgroups: list[list[float | None]] = []
    variable_name: str = ""

    if stacked:
        if response_index is None or response_index < 0 or response_index >= len(worksheet.columns):
            raise ValueError("Select a valid numeric response column.")
        resp_col = worksheet.columns[response_index]
        if resp_col.kind != 'number':
            raise ValueError(f"Response column '{resp_col.name}' must be numeric.")
        variable_name = resp_col.name
        vals = [normalize_numeric(v) for v in resp_col.values]

        if factor_index is not None:
            if factor_index < 0 or factor_index >= len(worksheet.columns) or factor_index == response_index:
                raise ValueError("Select a distinct subgroup ID column.")
            fac_col = worksheet.columns[factor_index]
            group_dict: dict[Any, list[float | None]] = {}
            for r in range(max(len(resp_col.values), len(fac_col.values))):
                lvl = fac_col.values[r] if r < len(fac_col.values) else None
                if lvl is None or lvl == '':
                    continue
                val = vals[r] if r < len(vals) else None
                group_dict.setdefault(lvl, []).append(val)
            subgroups = list(group_dict.values())
        else:
            sz = int(subgroup_size or 5)
            if sz < 2:
                raise ValueError("Subgroup size must be at least 2.")
            for start in range(0, len(vals), sz):
                subgroups.append(vals[start : start + sz])
    else:
        if not indices or len(indices) < 2:
            raise ValueError("Select 2 or more columns for subgroup row arrangement.")
        cols = [worksheet.columns[i] for i in indices]
        for c in cols:
            if c.kind != 'number':
                raise ValueError(f"Subgroup column '{c.name}' must be numeric.")
        variable_name = ", ".join(c.name for c in cols)
        n_rows = max(len(c.values) for c in cols)
        for r in range(n_rows):
            subgroups.append([normalize_numeric(c.values[r] if r < len(c.values) else None) for c in cols])

    result = fit_subgroups(subgroups, chart_type=chart_type, options=options)
    result['variable_name'] = variable_name
    result['stacked'] = stacked
    result['response_index'] = response_index
    result['factor_index'] = factor_index
    result['indices'] = list(indices) if indices else None
    result['subgroup_size'] = subgroup_size

    # Storage execution
    store_opts = result['options']['storage']
    stored_cols: list[str] = []
    k_pts = result['k_subgroups']

    def _add_col(prefix: str, col_vals: list) -> str:
        existing = {c.name.upper() for c in worksheet.columns if c.name}
        cname = prefix
        if cname.upper() in existing:
            idx = 1
            while f"{prefix}{idx}".upper() in existing:
                idx += 1
            cname = f"{prefix}{idx}"
        worksheet.columns.append(Column(cname, 'number', col_vals))
        return cname

    if store_opts.get('points'):
        stored_cols.append(_add_col(f"XBAR_{variable_name[:6]}", [None if v is None else round(v, 6) for v in result['means']]))
        disp_prefix = "RANGE" if chart_type == 'xbar_r' else "STDEV"
        stored_cols.append(_add_col(f"{disp_prefix}_{variable_name[:6]}", [None if v is None else round(v, 6) for v in result['disp_values']]))

    if store_opts.get('center_line'):
        stored_cols.append(_add_col(f"CENL_{variable_name[:6]}", [round(result['xbar_center'], 6)] * k_pts))

    if store_opts.get('control_limits'):
        stored_cols.append(_add_col(f"LCON_{variable_name[:6]}", [None if v is None else round(v, 6) for v in result['xbar_lcl']]))
        stored_cols.append(_add_col(f"UCON_{variable_name[:6]}", [None if v is None else round(v, 6) for v in result['xbar_ucl']]))

    if store_opts.get('subgroup_sizes'):
        stored_cols.append(_add_col(f"SSIZ_{variable_name[:6]}", list(result['subgroup_sizes'])))

    if store_opts.get('test_results'):
        stored_cols.append(_add_col(f"TEST_{variable_name[:6]}", [result['test_failures'].get(i + 1, [0])[0] for i in range(k_pts)]))

    result['stored_columns'] = stored_cols
    return result
