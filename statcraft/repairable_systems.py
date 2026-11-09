"""Computational engine for Repairable Systems Analysis (Recurrent Event Data).

Provides 1:1 parity with Minitab Repairable Systems Analysis:
1. Nonparametric Growth Curve:
   - Mean Cumulative Function (MCF) via Nelson / Lawless-Nadeau estimator.
   - Variance and pointwise confidence intervals.
   - Supports event times, system IDs, censoring/end times, and event counts/costs.

2. Parametric Growth Curve:
   - Non-Homogeneous Poisson Process (NHPP) with Power Law (Crow-AMSAA) intensity:
     nu(t) = lambda * beta * t^(beta - 1)
     Cumulative events: mu(t) = lambda * t^beta
   - Maximum Likelihood Estimates (MLE) of shape (beta) and scale (lambda).
   - Unbiased shape estimate (MIL-HDBK-189).
   - Trend tests for constant failure rate (H0: beta = 1):
     * MIL-HDBK-189 Chi-square test
     * Laplace trend test (Z-score and p-value)
   - Failure rate and Instantaneous MTBF (Mean Time Between Failures) table with 95% CIs.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import stats


def clean_repairable_data(
    system: Sequence[Any],
    time: Sequence[Any],
    event: Optional[Sequence[Any]] = None,
    cost: Optional[Sequence[Any]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Clean and sort repairable systems data into (systems, times, events, costs)."""
    n = min(len(system), len(time))
    clean_sys: List[str] = []
    clean_t: List[float] = []
    clean_ev: List[int] = []
    clean_c: List[float] = []

    for i in range(n):
        s_val = system[i]
        t_val = time[i]
        ev_val = event[i] if event is not None and i < len(event) else 1
        c_val = cost[i] if cost is not None and i < len(cost) else 1.0

        if s_val is None or t_val is None:
            continue
        try:
            ft = float(t_val)
            fev = int(ev_val) if ev_val is not None else 1
            fc = float(c_val) if c_val is not None else 1.0
            if math.isnan(ft) or ft < 0:
                continue
            clean_sys.append(str(s_val).strip())
            clean_t.append(ft)
            clean_ev.append(fev)
            clean_c.append(fc)
        except (ValueError, TypeError):
            continue

    if not clean_t:
        raise ValueError("No valid recurrent event data available.")

    arr_s = np.array(clean_sys)
    arr_t = np.array(clean_t, dtype=float)
    arr_ev = np.array(clean_ev, dtype=int)
    arr_c = np.array(clean_c, dtype=float)

    # Sort primarily by time
    order = np.argsort(arr_t)
    return arr_s[order], arr_t[order], arr_ev[order], arr_c[order]


def fit_nonparametric_mcf(
    system: Sequence[Any],
    time: Sequence[Any],
    event: Optional[Sequence[Any]] = None,
    cost: Optional[Sequence[Any]] = None,
    confidence: float = 0.95,
    system_name: str = "System",
    time_name: str = "Time",
) -> Dict[str, Any]:
    """Compute Nonparametric Mean Cumulative Function (MCF) table with Lawless-Nadeau variance."""
    arr_s, arr_t, arr_ev, arr_c = clean_repairable_data(system, time, event, cost)

    unique_systems = np.unique(arr_s)
    k_systems = len(unique_systems)

    # Determine end/censoring time for each system (maximum time recorded for that system)
    sys_end_times = {s: float(np.max(arr_t[arr_s == s])) for s in unique_systems}

    # Distinct failure event times (where event > 0)
    event_mask = (arr_ev > 0)
    event_times = arr_t[event_mask]
    event_costs = arr_c[event_mask]
    event_sys = arr_s[event_mask]

    distinct_times = np.unique(event_times)
    mcf_table = []

    cum_mcf = 0.0
    cum_var = 0.0
    z_crit = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)

    # Track cumulative events per system for Lawless-Nadeau variance
    sys_cum_events = {s: 0.0 for s in unique_systems}

    for t_cur in distinct_times:
        # Systems at risk at t_cur (end time >= t_cur)
        at_risk = [s for s, t_end in sys_end_times.items() if t_end >= t_cur]
        r_t = len(at_risk)
        if r_t == 0:
            continue

        # Events occurring at t_cur
        mask_cur = (event_times == t_cur)
        d_cur = float(np.sum(event_costs[mask_cur]))
        count_cur = int(np.sum(mask_cur))

        # Update MCF
        d_mcf = d_cur / r_t
        cum_mcf += d_mcf

        # Update each system's events at t_cur
        cur_sys_at_t = event_sys[mask_cur]
        cur_costs_at_t = event_costs[mask_cur]
        for s_i, c_i in zip(cur_sys_at_t, cur_costs_at_t):
            sys_cum_events[s_i] += c_i

        # Sample variance among at-risk systems (Lawless & Nadeau standard)
        if r_t > 1:
            # Events in this interval for systems at risk
            sys_events_cur = [
                float(np.sum(cur_costs_at_t[cur_sys_at_t == s])) if np.any(cur_sys_at_t == s) else 0.0
                for s in at_risk
            ]
            s2 = float(np.var(sys_events_cur, ddof=1))
            var_inc = s2 / (r_t ** 2)
        else:
            var_inc = (d_mcf ** 2)

        cum_var += var_inc
        se_mcf = math.sqrt(max(0.0, cum_var))

        ci_lower = max(0.0, cum_mcf - z_crit * se_mcf)
        ci_upper = cum_mcf + z_crit * se_mcf

        mcf_table.append({
            "time": float(t_cur),
            "events": count_cur,
            "cost": d_cur,
            "at_risk": r_t,
            "mcf": cum_mcf,
            "se": se_mcf,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
        })

    return {
        "analysis": "nonparametric_growth_curve",
        "title": f"Nonparametric Growth Curve (MCF): {time_name} by {system_name}",
        "system_name": system_name,
        "time_name": time_name,
        "n_systems": k_systems,
        "total_events": int(np.sum(event_mask)),
        "confidence": confidence,
        "mcf_table": mcf_table,
    }


def fit_parametric_growth_curve(
    system: Sequence[Any],
    time: Sequence[Any],
    event: Optional[Sequence[Any]] = None,
    confidence: float = 0.95,
    system_name: str = "System",
    time_name: str = "Time",
) -> Dict[str, Any]:
    """Fit Parametric Growth Curve (Crow-AMSAA / Power Law NHPP) with trend tests."""
    arr_s, arr_t, arr_ev, _ = clean_repairable_data(system, time, event)

    unique_systems = np.unique(arr_s)
    k_systems = len(unique_systems)

    event_mask = (arr_ev > 0)
    total_events = int(np.sum(event_mask))
    if total_events < 2:
        raise ValueError("At least 2 failure events are required for parametric growth curve.")

    # Determine censoring/end time T_k for each system
    sys_end_times = {s: float(np.max(arr_t[arr_s == s])) for s in unique_systems}

    # MLE of beta (shape) across multiple systems:
    # beta_hat = N / sum_k sum_i ln(T_k / t_ki)
    sum_log_ratio = 0.0
    for s in unique_systems:
        t_end = sys_end_times[s]
        if t_end <= 0:
            continue
        ev_times_s = arr_t[(arr_s == s) & event_mask]
        for t_ij in ev_times_s:
            if t_ij > 0 and t_ij <= t_end:
                sum_log_ratio += math.log(t_end / t_ij)

    if sum_log_ratio <= 1e-12:
        beta_mle = 1.0
    else:
        beta_mle = float(total_events / sum_log_ratio)

    # MIL-HDBK-189 Unbiased estimate: beta_unbiased = ((N - 1) / N) * beta_mle (for single) or (N - 2)/N
    beta_unbiased = ((total_events - 1.0) / total_events) * beta_mle if total_events > 1 else beta_mle

    # Scale lambda_hat = N / sum(T_k^beta)
    sum_t_beta = sum(t_end ** beta_mle for t_end in sys_end_times.values())
    lambda_mle = float(total_events / sum_t_beta) if sum_t_beta > 0 else 1.0

    # Standard errors of parameters via Fisher Information
    # Var(beta) = beta^2 / N
    se_beta = beta_mle / math.sqrt(total_events) if total_events > 0 else 0.0
    se_lambda = lambda_mle / math.sqrt(total_events) if total_events > 0 else 0.0

    z_crit = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    ci_beta = (max(0.0, beta_mle - z_crit * se_beta), beta_mle + z_crit * se_beta)
    ci_lambda = (max(0.0, lambda_mle - z_crit * se_lambda), lambda_mle + z_crit * se_lambda)

    # ----------------------------------------------------
    # Trend Tests for H0: beta = 1 (Homogeneous Poisson Process / Constant Failure Rate)
    # ----------------------------------------------------
    # 1. Military Handbook Test (Chi-Square)
    # Under H0, 2*N / beta_mle ~ Chi2(2*N)
    mil_stat = 2.0 * total_events / beta_mle if beta_mle > 0 else 0.0
    mil_df = 2 * total_events
    mil_p = 2.0 * min(stats.chi2.cdf(mil_stat, mil_df), 1.0 - stats.chi2.cdf(mil_stat, mil_df))

    # 2. Laplace Trend Test
    # Tests whether event times are uniformly distributed over [0, T]
    # U = (sum(t_i) - N*T/2) / (T * sqrt(N / 12))
    all_ev_times = arr_t[event_mask]
    t_max = max(sys_end_times.values())
    laplace_num = float(np.sum(all_ev_times)) - total_events * (t_max / 2.0)
    laplace_denom = t_max * math.sqrt(total_events / 12.0) if t_max > 0 else 1.0
    laplace_z = laplace_num / laplace_denom
    laplace_p = 2.0 * (1.0 - stats.norm.cdf(abs(laplace_z)))

    # Interpretation:
    if beta_mle < 0.95 and (mil_p < 0.05 or laplace_p < 0.05):
        trend_desc = "Reliability Growth (Failure rate is decreasing over time)"
    elif beta_mle > 1.05 and (mil_p < 0.05 or laplace_p < 0.05):
        trend_desc = "System Deterioration (Failure rate is increasing over time)"
    else:
        trend_desc = "Constant Failure Rate (No significant reliability trend)"

    # Predictions / Horizons Table
    # Times chosen at 25%, 50%, 75%, 100%, 125%, 150% of maximum operating time
    time_horizons = [t_max * factor for factor in [0.25, 0.50, 0.75, 1.0, 1.25, 1.50]]
    prediction_table = []

    for t_h in time_horizons:
        if t_h <= 0:
            continue
        cum_events = lambda_mle * (t_h ** beta_mle)
        fail_rate = lambda_mle * beta_mle * (t_h ** (beta_mle - 1.0))
        mtbf = 1.0 / fail_rate if fail_rate > 0 else 0.0

        # Log-scale Delta method confidence limits for MTBF
        var_log_mtbf = (1.0 / total_events) + ((math.log(t_h) * se_beta) ** 2)
        se_log_mtbf = math.sqrt(max(0.0, var_log_mtbf))
        ci_mtbf_lower = mtbf * math.exp(-z_crit * se_log_mtbf)
        ci_mtbf_upper = mtbf * math.exp(z_crit * se_log_mtbf)

        prediction_table.append({
            "time": t_h,
            "cumulative_events": cum_events,
            "failure_rate": fail_rate,
            "mtbf": mtbf,
            "ci_mtbf_lower": ci_mtbf_lower,
            "ci_mtbf_upper": ci_mtbf_upper,
        })

    return {
        "analysis": "parametric_growth_curve",
        "title": f"Parametric Growth Curve (Power Law / Crow-AMSAA): {time_name} by {system_name}",
        "system_name": system_name,
        "time_name": time_name,
        "n_systems": k_systems,
        "total_events": total_events,
        "confidence": confidence,
        "parameters": {
            "shape_beta_mle": beta_mle,
            "shape_beta_unbiased": beta_unbiased,
            "se_beta": se_beta,
            "ci_beta": ci_beta,
            "scale_lambda_mle": lambda_mle,
            "se_lambda": se_lambda,
            "ci_lambda": ci_lambda,
        },
        "trend_tests": {
            "mil_hdbk_stat": mil_stat,
            "mil_hdbk_df": mil_df,
            "mil_hdbk_p": mil_p,
            "laplace_z": laplace_z,
            "laplace_p": laplace_p,
            "trend_description": trend_desc,
        },
        "predictions": prediction_table,
    }
