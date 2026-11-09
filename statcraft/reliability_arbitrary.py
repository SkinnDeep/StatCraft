"""Computational engine for Parametric Distribution Analysis (Arbitrary Censoring).

Provides 1:1 parity with Minitab Reliability/Survival:
- Arbitrary censoring intervals: (Start, End)
    * Exact failure: Start == End
    * Left censored: Start is None/0, End is finite
    * Right censored: Start is finite, End is None/inf
    * Interval censored: 0 < Start < End < inf
- Maximum Likelihood Estimation across Minitab distributions:
    * Weibull (Shape, Scale)
    * Lognormal (Location, Scale)
    * Exponential (Scale)
    * Normal (Mean, StDev)
    * Loglogistic (Location, Scale)
- Summary of observations (Exact, Left, Right, Interval censored, Total)
- Parameter estimates with SE and 95% confidence intervals
- Table of Percentiles (1%, 5%, 10%, 50%, 90%, 95%, 99%) with SE and CI via delta method
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import optimize, stats


def clean_arbitrary_censoring_data(
    start_times: Sequence[Any],
    end_times: Sequence[Any],
    frequencies: Optional[Sequence[Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Clean and classify interval-censored survival observations."""
    n_raw = min(len(start_times), len(end_times))
    if frequencies is not None:
        n_raw = min(n_raw, len(frequencies))

    records: List[Dict[str, Any]] = []
    counts = {"exact": 0, "left": 0, "right": 0, "interval": 0, "total": 0}

    for i in range(n_raw):
        s_val = start_times[i]
        e_val = end_times[i]
        w = 1.0

        if frequencies is not None:
            f_val = frequencies[i]
            if f_val is None:
                continue
            try:
                w = float(f_val)
                if w <= 0 or math.isnan(w):
                    continue
            except (ValueError, TypeError):
                continue

        # Parse start and end
        fs: Optional[float] = None
        fe: Optional[float] = None

        if s_val is not None:
            try:
                v = float(s_val)
                if not (math.isnan(v) or math.isinf(v)) and v >= 0:
                    fs = v
            except (ValueError, TypeError):
                pass

        if e_val is not None:
            try:
                v = float(e_val)
                if not (math.isnan(v) or math.isinf(v)) and v > 0:
                    fe = v
            except (ValueError, TypeError):
                pass

        if fs is None and fe is None:
            continue

        int_w = int(round(w))

        if fs is not None and fe is not None:
            if abs(fs - fe) < 1e-9:
                # Exact failure
                records.append({"type": "exact", "start": fs, "end": fe, "weight": w})
                counts["exact"] += int_w
            elif fs < fe:
                if fs == 0.0:
                    # Left censored
                    records.append({"type": "left", "start": 0.0, "end": fe, "weight": w})
                    counts["left"] += int_w
                else:
                    # Interval censored
                    records.append({"type": "interval", "start": fs, "end": fe, "weight": w})
                    counts["interval"] += int_w
            else:
                continue
        elif fs is None and fe is not None:
            # Left censored
            records.append({"type": "left", "start": 0.0, "end": fe, "weight": w})
            counts["left"] += int_w
        elif fs is not None and fe is None:
            # Right censored
            records.append({"type": "right", "start": fs, "end": float("inf"), "weight": w})
            counts["right"] += int_w

        counts["total"] += int_w

    return records, counts


def fit_parametric_arbitrary_censoring(
    start_times: Sequence[Any],
    end_times: Sequence[Any],
    frequencies: Optional[Sequence[Any]] = None,
    distribution: str = "weibull",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Fit parametric arbitrary censoring model matching Minitab."""
    records, counts = clean_arbitrary_censoring_data(start_times, end_times, frequencies)
    if counts["total"] < 3:
        raise ValueError("At least 3 valid observations required for distribution analysis.")

    dist = distribution.lower()
    valid_dists = ("weibull", "lognormal", "exponential", "normal", "loglogistic")
    if dist not in valid_dists:
        raise ValueError(f"Unknown distribution '{distribution}'. Choose from {valid_dists}.")

    # Collect midpoints for initial parameter estimates
    midpoints = []
    for r in records:
        t_type = r["type"]
        if t_type == "exact":
            midpoints.extend([r["start"]] * int(round(r["weight"])))
        elif t_type == "interval":
            midpoints.extend([(r["start"] + r["end"]) / 2.0] * int(round(r["weight"])))
        elif t_type == "left":
            midpoints.extend([r["end"] / 2.0] * int(round(r["weight"])))
        elif t_type == "right":
            midpoints.extend([r["start"] * 1.2] * int(round(r["weight"])))

    m_arr = np.asarray(midpoints, dtype=float)
    mean_m = float(np.mean(m_arr))
    std_m = max(1e-4, float(np.std(m_arr, ddof=1)))
    log_m = np.log(np.maximum(1e-6, m_arr))
    mean_log = float(np.mean(log_m))
    std_log = max(1e-4, float(np.std(log_m, ddof=1)))

    if dist == "weibull":
        # Shape beta, Scale alpha
        # init: beta ~ 1.2 / std_log, alpha ~ exp(mean_log)
        init_beta = max(0.5, 1.2 / std_log)
        init_alpha = max(1e-4, math.exp(mean_log))
        init_params = [math.log(init_beta), math.log(init_alpha)]
        param_names = ["Shape", "Scale"]
    elif dist == "lognormal":
        # Location mu, Scale sigma
        init_params = [mean_log, math.log(std_log)]
        param_names = ["Location", "Scale"]
    elif dist == "exponential":
        # Scale theta
        init_params = [math.log(mean_m)]
        param_names = ["Scale"]
    elif dist == "normal":
        # Mean mu, StDev sigma
        init_params = [mean_m, math.log(std_m)]
        param_names = ["Mean", "StDev"]
    elif dist == "loglogistic":
        # Location mu, Scale sigma
        init_params = [mean_log, math.log(std_log * (math.sqrt(3) / math.pi))]
        param_names = ["Location", "Scale"]

    def cdf_fn(t: float, raw_params: np.ndarray) -> float:
        if t <= 0 and dist in ("weibull", "lognormal", "exponential", "loglogistic"):
            return 0.0
        if dist == "weibull":
            beta = math.exp(raw_params[0])
            alpha = math.exp(raw_params[1])
            return float(1.0 - math.exp(-((t / alpha) ** beta)))
        elif dist == "lognormal":
            mu = raw_params[0]
            sigma = math.exp(raw_params[1])
            return float(stats.norm.cdf((math.log(t) - mu) / sigma))
        elif dist == "exponential":
            theta = math.exp(raw_params[0])
            return float(1.0 - math.exp(-t / theta))
        elif dist == "normal":
            mu = raw_params[0]
            sigma = math.exp(raw_params[1])
            return float(stats.norm.cdf((t - mu) / sigma))
        elif dist == "loglogistic":
            mu = raw_params[0]
            sigma = math.exp(raw_params[1])
            z = (math.log(t) - mu) / sigma
            return float(1.0 / (1.0 + math.exp(-np.clip(z, -30.0, 30.0))))
        return 0.0

    def pdf_fn(t: float, raw_params: np.ndarray) -> float:
        if t <= 0 and dist in ("weibull", "lognormal", "exponential", "loglogistic"):
            return 1e-12
        if dist == "weibull":
            beta = math.exp(raw_params[0])
            alpha = math.exp(raw_params[1])
            z = t / alpha
            return float((beta / alpha) * (z ** (beta - 1.0)) * math.exp(-(z ** beta)))
        elif dist == "lognormal":
            mu = raw_params[0]
            sigma = math.exp(raw_params[1])
            return float(stats.norm.pdf((math.log(t) - mu) / sigma) / (t * sigma))
        elif dist == "exponential":
            theta = math.exp(raw_params[0])
            return float((1.0 / theta) * math.exp(-t / theta))
        elif dist == "normal":
            mu = raw_params[0]
            sigma = math.exp(raw_params[1])
            return float(stats.norm.pdf((t - mu) / sigma) / sigma)
        elif dist == "loglogistic":
            mu = raw_params[0]
            sigma = math.exp(raw_params[1])
            z = (math.log(t) - mu) / sigma
            ez = math.exp(np.clip(z, -30.0, 30.0))
            return float((ez / (sigma * t * ((1.0 + ez) ** 2))))
        return 1e-12

    def neg_log_lik(raw_params: np.ndarray) -> float:
        total_ll = 0.0
        for r in records:
            w = r["weight"]
            tt = r["type"]
            if tt == "exact":
                val = pdf_fn(r["start"], raw_params)
            elif tt == "left":
                val = cdf_fn(r["end"], raw_params)
            elif tt == "right":
                val = max(1e-12, 1.0 - cdf_fn(r["start"], raw_params))
            elif tt == "interval":
                val = max(1e-12, cdf_fn(r["end"], raw_params) - cdf_fn(r["start"], raw_params))
            else:
                val = 1e-12
            total_ll += w * math.log(max(1e-15, val))
        return -total_ll

    opt = optimize.minimize(
        neg_log_lik,
        x0=np.asarray(init_params, dtype=float),
        method="L-BFGS-B",
        options={"maxiter": 200, "ftol": 1e-10},
    )

    opt_raw = opt.x
    final_ll = -opt.fun

    # Numerical Hessian for covariance matrix
    p_len = len(opt_raw)
    eps = 1e-5
    hess = np.zeros((p_len, p_len), dtype=float)
    for i in range(p_len):
        for j in range(p_len):
            p_ij = opt_raw.copy(); p_ij[i] += eps; p_ij[j] += eps
            p_i = opt_raw.copy(); p_i[i] += eps; p_i[j] -= eps
            p_j = opt_raw.copy(); p_j[i] -= eps; p_j[j] += eps
            p_0 = opt_raw.copy(); p_0[i] -= eps; p_0[j] -= eps
            hess[i, j] = (neg_log_lik(p_ij) - neg_log_lik(p_i) - neg_log_lik(p_j) + neg_log_lik(p_0)) / (4.0 * eps * eps)

    hess = 0.5 * (hess + hess.T)
    try:
        cov_raw = np.linalg.inv(hess)
    except np.linalg.LinAlgError:
        cov_raw = np.linalg.pinv(hess)

    se_raw = np.sqrt(np.maximum(0.0, np.diag(cov_raw)))
    z_crit = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))

    # Transform parameters to original natural scale
    params_table = []
    if dist == "weibull":
        beta = math.exp(opt_raw[0])
        alpha = math.exp(opt_raw[1])
        se_beta = beta * se_raw[0]
        se_alpha = alpha * se_raw[1]
        params_table.append({
            "parameter": "Shape",
            "estimate": beta,
            "se": se_beta,
            "ci_lower": beta * math.exp(-z_crit * se_raw[0]),
            "ci_upper": beta * math.exp(z_crit * se_raw[0]),
        })
        params_table.append({
            "parameter": "Scale",
            "estimate": alpha,
            "se": se_alpha,
            "ci_lower": alpha * math.exp(-z_crit * se_raw[1]),
            "ci_upper": alpha * math.exp(z_crit * se_raw[1]),
        })
    elif dist == "lognormal":
        mu = opt_raw[0]
        sigma = math.exp(opt_raw[1])
        se_mu = se_raw[0]
        se_sigma = sigma * se_raw[1]
        params_table.append({
            "parameter": "Location",
            "estimate": mu,
            "se": se_mu,
            "ci_lower": mu - z_crit * se_mu,
            "ci_upper": mu + z_crit * se_mu,
        })
        params_table.append({
            "parameter": "Scale",
            "estimate": sigma,
            "se": se_sigma,
            "ci_lower": sigma * math.exp(-z_crit * se_raw[1]),
            "ci_upper": sigma * math.exp(z_crit * se_raw[1]),
        })
    elif dist == "exponential":
        theta = math.exp(opt_raw[0])
        se_theta = theta * se_raw[0]
        params_table.append({
            "parameter": "Scale",
            "estimate": theta,
            "se": se_theta,
            "ci_lower": theta * math.exp(-z_crit * se_raw[0]),
            "ci_upper": theta * math.exp(z_crit * se_raw[0]),
        })
    elif dist == "normal":
        mu = opt_raw[0]
        sigma = math.exp(opt_raw[1])
        se_mu = se_raw[0]
        se_sigma = sigma * se_raw[1]
        params_table.append({
            "parameter": "Mean",
            "estimate": mu,
            "se": se_mu,
            "ci_lower": mu - z_crit * se_mu,
            "ci_upper": mu + z_crit * se_mu,
        })
        params_table.append({
            "parameter": "StDev",
            "estimate": sigma,
            "se": se_sigma,
            "ci_lower": sigma * math.exp(-z_crit * se_raw[1]),
            "ci_upper": sigma * math.exp(z_crit * se_raw[1]),
        })
    elif dist == "loglogistic":
        mu = opt_raw[0]
        sigma = math.exp(opt_raw[1])
        se_mu = se_raw[0]
        se_sigma = sigma * se_raw[1]
        params_table.append({
            "parameter": "Location",
            "estimate": mu,
            "se": se_mu,
            "ci_lower": mu - z_crit * se_mu,
            "ci_upper": mu + z_crit * se_mu,
        })
        params_table.append({
            "parameter": "Scale",
            "estimate": sigma,
            "se": se_sigma,
            "ci_lower": sigma * math.exp(-z_crit * se_raw[1]),
            "ci_upper": sigma * math.exp(z_crit * se_raw[1]),
        })

    # Table of percentiles
    percentiles_target = [1, 5, 10, 50, 90, 95, 99]
    percentile_table = []

    def quantile_fn(p_val: float) -> float:
        if dist == "weibull":
            beta = math.exp(opt_raw[0])
            alpha = math.exp(opt_raw[1])
            return float(alpha * ((-math.log(1.0 - p_val)) ** (1.0 / beta)))
        elif dist == "lognormal":
            mu = opt_raw[0]
            sigma = math.exp(opt_raw[1])
            return float(math.exp(mu + sigma * stats.norm.ppf(p_val)))
        elif dist == "exponential":
            theta = math.exp(opt_raw[0])
            return float(-theta * math.log(1.0 - p_val))
        elif dist == "normal":
            mu = opt_raw[0]
            sigma = math.exp(opt_raw[1])
            return float(mu + sigma * stats.norm.ppf(p_val))
        elif dist == "loglogistic":
            mu = opt_raw[0]
            sigma = math.exp(opt_raw[1])
            return float(math.exp(mu + sigma * math.log(p_val / (1.0 - p_val))))
        return 0.0

    for pct in percentiles_target:
        p_val = pct / 100.0
        q_est = quantile_fn(p_val)
        # Delta method SE
        q_grad = np.zeros(p_len, dtype=float)
        for i_p in range(p_len):
            p_step = opt_raw.copy(); p_step[i_p] += eps
            # re-eval
            if dist == "weibull":
                b_s = math.exp(p_step[0]); a_s = math.exp(p_step[1])
                q_s = float(a_s * ((-math.log(1.0 - p_val)) ** (1.0 / b_s)))
            elif dist == "lognormal":
                mu_s = p_step[0]; sig_s = math.exp(p_step[1])
                q_s = float(math.exp(mu_s + sig_s * stats.norm.ppf(p_val)))
            elif dist == "exponential":
                th_s = math.exp(p_step[0])
                q_s = float(-th_s * math.log(1.0 - p_val))
            elif dist == "normal":
                mu_s = p_step[0]; sig_s = math.exp(p_step[1])
                q_s = float(mu_s + sig_s * stats.norm.ppf(p_val))
            elif dist == "loglogistic":
                mu_s = p_step[0]; sig_s = math.exp(p_step[1])
                q_s = float(math.exp(mu_s + sig_s * math.log(p_val / (1.0 - p_val))))
            else:
                q_s = q_est
            q_grad[i_p] = (q_s - q_est) / eps

        se_q = math.sqrt(max(0.0, float(q_grad @ cov_raw @ q_grad)))
        ci_l = max(0.0, q_est - z_crit * se_q) if dist != "normal" else q_est - z_crit * se_q
        ci_u = q_est + z_crit * se_q

        percentile_table.append({
            "percent": pct,
            "percentile": q_est,
            "se": se_q,
            "ci_lower": ci_l,
            "ci_upper": ci_u,
        })

    return {
        "analysis": "reliability_arbitrary",
        "distribution": dist.capitalize(),
        "confidence": confidence,
        "log_likelihood": final_ll,
        "counts": counts,
        "parameters": params_table,
        "percentiles": percentile_table,
        "title": f"Distribution Analysis (Arbitrary Censoring) - {dist.capitalize()}",
    }
