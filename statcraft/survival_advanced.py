"""Advanced Reliability & Survival Analysis: Cox Proportional Hazards & Warranty Forecasting."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
from scipy import optimize, stats


def cox_ph_regression(
    worksheet,
    time_index: int,
    event_index: int,
    covariate_indices: Sequence[int],
    event_value: Any = 1,
) -> Dict[str, Any]:
    """Fit Cox Proportional Hazards model via Breslow Partial Log-Likelihood."""
    if not covariate_indices:
        raise ValueError("Select at least one continuous covariate.")
    if time_index == event_index or time_index in covariate_indices or event_index in covariate_indices:
        raise ValueError("Time, Event/Censoring, and Covariate columns must be distinct.")

    t_col = worksheet.columns[time_index]
    e_col = worksheet.columns[event_index]
    x_cols = [worksheet.columns[i] for i in covariate_indices]
    target_evt = str(event_value).strip()

    rows_t: List[float] = []
    rows_e: List[int] = []
    rows_x: List[List[float]] = []

    for r in range(worksheet.row_count):
        tv = t_col.values[r] if r < len(t_col.values) else None
        ev = e_col.values[r] if r < len(e_col.values) else None
        xvs = [c.values[r] if r < len(c.values) else None for c in x_cols]
        if tv is None or ev is None or any(v is None for v in xvs):
            continue
        try:
            tf = float(tv)
            xf = [float(v) for v in xvs]
        except (ValueError, TypeError):
            continue
        if tf <= 0 or not (math.isfinite(tf) and all(math.isfinite(x) for x in xf)):
            continue
        ev_str = str(int(ev)) if isinstance(ev, float) and ev.is_integer() else str(ev).strip()
        is_event = 1 if ev_str.casefold() == target_evt.casefold() else 0
        rows_t.append(tf)
        rows_e.append(is_event)
        rows_x.append(xf)

    n = len(rows_t)
    p = len(covariate_indices)
    events_total = sum(rows_e)
    if n < p + 3 or events_total < 2:
        raise ValueError("Cox regression requires at least 2 uncensored events and complete observations.")

    # Sort descending by time so cumulative risk set sums are O(n)
    order = np.argsort(-np.asarray(rows_t, dtype=float), kind="mergesort")
    t_arr = np.asarray(rows_t, dtype=float)[order]
    e_arr = np.asarray(rows_e, dtype=int)[order]
    X = np.asarray(rows_x, dtype=float)[order]

    # Precompute tied event groups in descending time order
    unique_event_times = sorted(set(float(t_arr[i]) for i in range(n) if e_arr[i] == 1), reverse=True)

    def _partial_ll_grad_hess(beta: np.ndarray):
        eta = np.clip(X @ beta, -30.0, 30.0)
        exp_eta = np.exp(eta)
        # Risk set weights S0(t), S1(t), S2(t) via cumulative sums on descending-sorted arrays
        cum_s0 = np.cumsum(exp_eta)
        cum_s1 = np.cumsum(exp_eta[:, None] * X, axis=0)
        # S2 flattened: (n, p*p)
        outer_x = exp_eta[:, None, None] * (X[:, :, None] * X[:, None, :])
        cum_s2 = np.cumsum(outer_x, axis=0)

        ll = 0.0
        grad = np.zeros(p, dtype=float)
        hess = np.zeros((p, p), dtype=float)

        for ut in unique_event_times:
            ev_mask = (t_arr == ut) & (e_arr == 1)
            d = int(np.sum(ev_mask))
            last_risk_idx = int(np.where(t_arr >= ut)[0][-1])
            s0 = float(cum_s0[last_risk_idx])
            s1 = cum_s1[last_risk_idx]
            s2 = cum_s2[last_risk_idx]
            sum_x_ev = np.sum(X[ev_mask], axis=0)
            sum_eta_ev = float(np.sum(eta[ev_mask]))

            ll += sum_eta_ev - d * math.log(max(s0, 1e-18))
            mean_x = s1 / max(s0, 1e-18)
            grad += sum_x_ev - d * mean_x
            cov_x = (s2 / max(s0, 1e-18)) - np.outer(mean_x, mean_x)
            hess -= d * cov_x

        return float(ll), grad, hess

    beta = np.zeros(p, dtype=float)
    ll_null, _, _ = _partial_ll_grad_hess(beta)
    for _ in range(35):
        ll_curr, grad, hess = _partial_ll_grad_hess(beta)
        info = -hess + 1e-9 * np.eye(p)
        try:
            step = np.linalg.solve(info, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(info) @ grad
        # Backtracking line search
        alpha_step = 1.0
        while alpha_step > 1e-4:
            cand = beta + alpha_step * step
            cand_ll, _, _ = _partial_ll_grad_hess(cand)
            if cand_ll >= ll_curr - 1e-9:
                beta = cand
                break
            alpha_step *= 0.5
        if float(np.max(np.abs(alpha_step * step))) < 1e-7:
            break

    ll_final, _, hess_final = _partial_ll_grad_hess(beta)
    try:
        cov_beta = np.linalg.inv(-hess_final)
    except np.linalg.LinAlgError:
        cov_beta = np.linalg.pinv(-hess_final)
    se_beta = np.sqrt(np.maximum(np.diag(cov_beta), 1e-18))

    coeffs = []
    for col, b, se in zip(x_cols, beta, se_beta):
        z = float(b / se) if se > 0 else 0.0
        pv = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))
        hr = float(math.exp(min(b, 50.0)))
        hr_lo = float(math.exp(max(-50.0, b - 1.959964 * se)))
        hr_hi = float(math.exp(min(50.0, b + 1.959964 * se)))
        coeffs.append({
            "covariate": col.name,
            "coef": float(b),
            "se_coef": float(se),
            "hazard_ratio": hr,
            "hr_95_low": hr_lo,
            "hr_95_high": hr_hi,
            "z_value": z,
            "p_value": pv,
        })

    # Harrell's Concordance index (C-statistic)
    risk_scores = X @ beta
    concordant = 0.0
    permissible = 0.0
    for i in range(n):
        if e_arr[i] != 1:
            continue
        for j in range(n):
            if t_arr[j] > t_arr[i]:
                permissible += 1.0
                if risk_scores[i] > risk_scores[j]:
                    concordant += 1.0
                elif risk_scores[i] == risk_scores[j]:
                    concordant += 0.5
    c_index = (concordant / permissible) if permissible > 0 else 0.5

    lr_stat = max(0.0, 2.0 * (ll_final - ll_null))
    lr_p = float(1.0 - stats.chi2.cdf(lr_stat, p))

    return {
        "analysis": "cox_ph_regression",
        "time_variable": t_col.name,
        "event_variable": e_col.name,
        "n": int(n),
        "events": int(events_total),
        "censored": int(n - events_total),
        "log_likelihood_null": float(ll_null),
        "log_likelihood": float(ll_final),
        "lr_chi_sq": float(lr_stat),
        "lr_df": int(p),
        "lr_p_value": lr_p,
        "concordance": float(c_index),
        "coefficients": coeffs,
    }


def warranty_analysis(
    ages: Sequence[Any],
    fail_counts: Sequence[Any],
    at_risk_total: float,
    forecast_horizon: float = 12.0,
) -> Dict[str, Any]:
    """Fit Weibull warranty failure trend on binned age intervals & forecast cumulative claims."""
    grouped: Dict[float, float] = {}
    for a, c in zip(ages, fail_counts):
        if a is None or c is None:
            continue
        try:
            af, cf = float(a), float(c)
        except (ValueError, TypeError):
            continue
        if af > 0 and cf >= 0 and math.isfinite(af) and math.isfinite(cf):
            grouped[af] = grouped.get(af, 0.0) + cf
    pairs = sorted(grouped.items(), key=lambda item: item[0])
    if len(pairs) < 2:
        raise ValueError("Warranty Analysis requires at least 2 distinct positive age intervals with nonnegative counts.")
    if at_risk_total <= 0:
        raise ValueError("Total units in field (at risk) must be positive.")

    cum_fails = np.cumsum([p[1] for p in pairs])
    age_arr = np.asarray([p[0] for p in pairs], dtype=float)
    total_obs_fails = float(cum_fails[-1])
    if total_obs_fails <= 0:
        raise ValueError("At least 1 observed warranty claim is required to fit trend.")
    if total_obs_fails >= at_risk_total:
        raise ValueError("Observed total claims cannot meet or exceed total units at risk.")

    # Kaplan-style cumulative incidence F(t) = min(0.99, cum_fails / (at_risk_total + 1)) -> Weibull linearized fit
    f_hat = np.clip(cum_fails / (float(at_risk_total) + 1.0), 1e-6, 0.99)
    x_ln = np.log(age_arr)
    y_ln = np.log(-np.log(1.0 - f_hat))
    slope, intercept = np.polyfit(x_ln, y_ln, 1)
    shape_beta = max(0.1, float(slope))
    scale_eta = float(math.exp(-intercept / shape_beta))

    horizon = max(float(forecast_horizon), float(age_arr[-1]))
    step_ages = [float(age_arr[-1]) * 1.25, horizon]
    if horizon <= age_arr[-1]:
        step_ages = [horizon]
    forecasts = []
    for h_age in sorted(set(step_ages)):
        prob = 1.0 - math.exp(-((h_age / scale_eta) ** shape_beta))
        expected_cum = float(at_risk_total) * prob
        forecasts.append({
            "age": float(h_age),
            "cum_failure_pct": float(prob * 100.0),
            "expected_total_claims": expected_cum,
            "additional_future_claims": max(0.0, expected_cum - total_obs_fails),
        })

    return {
        "analysis": "warranty_analysis",
        "units_at_risk": float(at_risk_total),
        "observed_claims": total_obs_fails,
        "observed_claim_rate_pct": 100.0 * total_obs_fails / float(at_risk_total),
        "weibull_shape": shape_beta,
        "weibull_scale": scale_eta,
        "distinct_ages": len(pairs),
        "age_points": [{"age": float(a), "failures": float(c)} for a, c in pairs],
        "forecasts": forecasts,
    }


def format_survival_advanced_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    lines = []
    if kind == "cox_ph_regression":
        lines.extend([
            f"Cox Proportional Hazards Regression: Time = {result['time_variable']}, Event = {result['event_variable']}",
            f"  N = {result['n']}   |   Events = {result['events']}   |   Censored = {result['censored']}",
            f"  Log-Likelihood = {result['log_likelihood']:.3f}   |   Harrell C-Index = {result['concordance']:.4f}",
            f"  Overall LR Chi-Sq = {result['lr_chi_sq']:.3f} (DF = {result['lr_df']}, P-Value = {result['lr_p_value']:.4f})",
            "",
            "  Covariate       Coef      SE Coef   Hazard Ratio   95% CI Low   95% CI High   P-Value",
            "  " + "-" * 84,
        ])
        for c in result["coefficients"]:
            lines.append(
                f"  {c['covariate']:<13} {c['coef']:>8.4f}  {c['se_coef']:>10.4f}  {c['hazard_ratio']:>13.4f}  {c['hr_95_low']:>11.4f}  {c['hr_95_high']:>12.4f}  {c['p_value']:>8.4f}"
            )
    elif kind == "warranty_analysis":
        lines.extend([
            "Warranty Failure Analysis & Forecast (Weibull Trend Model)",
            f"  Units at Risk = {result['units_at_risk']:.0f}   |   Observed Claims = {result['observed_claims']:.0f} ({result['observed_claim_rate_pct']:.3f}%)",
            f"  Estimated Weibull Shape = {result['weibull_shape']:.4f}   |   Characteristic Life (Scale) = {result['weibull_scale']:.4f}",
            "",
            "  Forecast Age     Cum Claim %     Expected Total Claims     Additional Future Claims",
            "  " + "-" * 82,
        ])
        for fc in result["forecasts"]:
            lines.append(
                f"  {fc['age']:>12.2f}     {fc['cum_failure_pct']:>10.3f}%     {fc['expected_total_claims']:>21.2f}     {fc['additional_future_claims']:>24.2f}"
            )
    return "\n".join(lines)
