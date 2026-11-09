"""Computational engine for Probit Analysis (Bioassay, LD50/EC50 determination).

Provides 1:1 parity with Minitab Probit Analysis:
- Supports event/trials data or binary response.
- Link functions / distributions:
  * Probit (Normal distribution)
  * Logit (Logistic distribution)
  * Weibull (Extreme Value distribution)
  * Gompertz (Gompertz distribution)
- Dose transformations:
  * None
  * Natural logarithm (ln)
  * Base 10 logarithm (log10)
- Maximum Likelihood Estimation via IRLS with analytical Fisher information.
- Regression table: Coef, SE Coef, Z, P-value.
- Goodness-of-fit tests: Pearson Chi-Square and Deviance Chi-Square.
- Table of percentiles (LD1, LD5, LD10, LD20, LD30, LD40, LD50, LD60, LD70, LD80, LD90, LD95, LD99)
  with estimates, SE, and 95% fiducial confidence limits (Fieller's theorem).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy import stats


def _link_functions(dist_name: str):
    """Return CDF F(eta), PDF f(eta), and quantile finv(p) for the chosen distribution."""
    dist = dist_name.lower()
    if dist in ("probit", "normal"):
        F = lambda eta: stats.norm.cdf(eta)
        f = lambda eta: stats.norm.pdf(eta)
        finv = lambda p: stats.norm.ppf(p)
    elif dist in ("logit", "logistic"):
        F = lambda eta: 1.0 / (1.0 + np.exp(-np.clip(eta, -35.0, 35.0)))
        f = lambda eta: (np.exp(-np.clip(eta, -35.0, 35.0))) / ((1.0 + np.exp(-np.clip(eta, -35.0, 35.0))) ** 2)
        finv = lambda p: np.log(p / (1.0 - p))
    elif dist in ("weibull", "extreme_value", "cloglog"):
        # Complementary log-log
        F = lambda eta: 1.0 - np.exp(-np.exp(np.clip(eta, -35.0, 35.0)))
        f = lambda eta: np.exp(eta - np.exp(np.clip(eta, -35.0, 35.0)))
        finv = lambda p: np.log(-np.log(1.0 - p))
    elif dist in ("gompertz",):
        # Log-log
        F = lambda eta: np.exp(-np.exp(-np.clip(eta, -35.0, 35.0)))
        f = lambda eta: np.exp(-eta - np.exp(-np.clip(eta, -35.0, 35.0)))
        finv = lambda p: -np.log(-np.log(p))
    else:
        raise ValueError(f"Unsupported distribution '{dist_name}'. Choose probit, logit, weibull, or gompertz.")
    return F, f, finv


def clean_probit_data(
    events: Sequence[Any],
    trials: Optional[Sequence[Any]],
    dose: Sequence[Any],
    dose_transform: str = "none",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Clean and aggregate probit data into (unique_dose, events, trials, transformed_dose)."""
    n_raw = len(dose)
    clean_ev: List[float] = []
    clean_tr: List[float] = []
    clean_d: List[float] = []

    for i in range(n_raw):
        d_val = dose[i]
        ev_val = events[i]
        tr_val = trials[i] if trials is not None and i < len(trials) else 1.0

        if d_val is None or ev_val is None or tr_val is None:
            continue
        try:
            fd = float(d_val)
            fev = float(ev_val)
            ftr = float(tr_val)
            if math.isnan(fd) or math.isnan(fev) or math.isnan(ftr):
                continue
            if ftr <= 0 or fev < 0 or fev > ftr:
                continue
            clean_d.append(fd)
            clean_ev.append(fev)
            clean_tr.append(ftr)
        except (ValueError, TypeError):
            continue

    if not clean_d:
        raise ValueError("No valid data available for probit analysis.")

    # Aggregate by dose level
    grouped: Dict[float, List[float]] = {}
    for d, ev, tr in zip(clean_d, clean_ev, clean_tr):
        if d not in grouped:
            grouped[d] = [0.0, 0.0]
        grouped[d][0] += ev
        grouped[d][1] += tr

    sorted_doses = sorted(grouped.keys())
    arr_d = np.array(sorted_doses, dtype=float)
    arr_ev = np.array([grouped[d][0] for d in sorted_doses], dtype=float)
    arr_tr = np.array([grouped[d][1] for d in sorted_doses], dtype=float)

    # Dose transformation
    t = dose_transform.lower()
    if t == "ln":
        if np.any(arr_d <= 0):
            raise ValueError("All dose values must be > 0 for natural log transformation.")
        arr_x = np.log(arr_d)
    elif t in ("log10", "log"):
        if np.any(arr_d <= 0):
            raise ValueError("All dose values must be > 0 for log10 transformation.")
        arr_x = np.log10(arr_d)
    else:
        arr_x = arr_d.copy()

    return arr_d, arr_ev, arr_tr, arr_x


def fit_probit_analysis(
    events: Sequence[Any],
    dose: Sequence[Any],
    trials: Optional[Sequence[Any]] = None,
    distribution: str = "probit",
    dose_transform: str = "none",
    confidence: float = 0.95,
    dose_name: str = "Dose",
    events_name: str = "Events",
    trials_name: str = "Trials",
) -> Dict[str, Any]:
    """Fit Probit model using Maximum Likelihood Estimation with Fisher Information."""
    arr_d, arr_ev, arr_tr, arr_x = clean_probit_data(events, trials, dose, dose_transform)
    k = len(arr_x)
    if k < 2:
        raise ValueError("At least 2 distinct dose levels are required for probit analysis.")

    F, f, finv = _link_functions(distribution)

    # Initial estimates via unweighted OLS on empirical quantiles
    p_emp = np.clip((arr_ev + 0.5) / (arr_tr + 1.0), 1e-4, 1.0 - 1e-4)
    y_init = finv(p_emp)
    slope_init, intercept_init = np.polyfit(arr_x, y_init, 1)

    beta = np.array([intercept_init, slope_init], dtype=float)
    X = np.column_stack([np.ones(k), arr_x])

    # IRLS Iteration
    cov = np.eye(2)
    max_iter = 100
    tol = 1e-8
    converged = False

    for iteration in range(max_iter):
        eta = X @ beta
        pi = np.clip(F(eta), 1e-9, 1.0 - 1e-9)
        f_val = np.maximum(f(eta), 1e-9)

        # Variance and weights
        var_pi = pi * (1.0 - pi)
        W_diag = arr_tr * (f_val ** 2) / var_pi
        W = np.diag(W_diag)

        # Working response
        z = eta + (arr_ev / arr_tr - pi) / f_val

        XtW = X.T @ W
        XtWX = XtW @ X

        try:
            cov = np.linalg.inv(XtWX)
            beta_new = cov @ (XtW @ z)
        except np.linalg.LinAlgError:
            # Fallback with pseudo-inverse
            cov = np.linalg.pinv(XtWX)
            beta_new = cov @ (XtW @ z)

        diff = np.max(np.abs(beta_new - beta))
        beta = beta_new
        if diff < tol:
            converged = True
            break

    b0, b1 = float(beta[0]), float(beta[1])
    v00 = float(cov[0, 0])
    v11 = float(cov[1, 1])
    v01 = float(cov[0, 1])

    se_b0 = math.sqrt(max(0.0, v00))
    se_b1 = math.sqrt(max(0.0, v11))

    z_b0 = b0 / se_b0 if se_b0 > 0 else 0.0
    p_b0 = 2.0 * (1.0 - stats.norm.cdf(abs(z_b0)))

    z_b1 = b1 / se_b1 if se_b1 > 0 else 0.0
    p_b1 = 2.0 * (1.0 - stats.norm.cdf(abs(z_b1)))

    # Fitted values and residuals
    eta_fit = X @ beta
    pi_fit = F(eta_fit)
    mu_fit = arr_tr * pi_fit

    # Pearson Chi-Square
    pearson_res = (arr_ev - mu_fit) / np.sqrt(np.maximum(1e-9, arr_tr * pi_fit * (1.0 - pi_fit)))
    pearson_chi2 = float(np.sum(pearson_res ** 2))
    df_fit = max(1, k - 2)
    pearson_p = float(1.0 - stats.chi2.cdf(pearson_chi2, df_fit))

    # Deviance Chi-Square
    dev_terms = np.zeros(k, dtype=float)
    for i in range(k):
        r = arr_ev[i]
        n = arr_tr[i]
        m = mu_fit[i]
        term1 = r * math.log(r / m) if r > 0 else 0.0
        term2 = (n - r) * math.log((n - r) / (n - m)) if n > r else 0.0
        dev_terms[i] = 2.0 * (term1 + term2)
    deviance_chi2 = float(np.sum(dev_terms))
    deviance_p = float(1.0 - stats.chi2.cdf(deviance_chi2, df_fit))

    # Regression table
    coefficients = [
        {
            "term": "Intercept",
            "coef": b0,
            "se_coef": se_b0,
            "z_value": z_b0,
            "p_value": p_b0,
        },
        {
            "term": dose_name,
            "coef": b1,
            "se_coef": se_b1,
            "z_value": z_b1,
            "p_value": p_b1,
        },
    ]

    # Percentiles / Lethal Doses (LDp)
    z_crit = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    g = (z_crit ** 2) * v11 / (b1 ** 2) if abs(b1) > 1e-9 else 1.0

    percentiles_table = []
    target_probs = [0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99]

    for p in target_probs:
        eta_p = float(finv(p))
        if abs(b1) < 1e-9:
            continue
        m = (eta_p - b0) / b1  # estimate on transformed scale

        # Standard error on transformed scale via Delta method
        v_m = v00 + 2.0 * m * v01 + (m ** 2) * v11
        se_m = math.sqrt(max(0.0, v_m)) / abs(b1)

        # Fieller's theorem confidence limits
        if g < 1.0:
            term_c = (m + (v01 / v11)) * (g / (1.0 - g))
            radicand = v_m - g * (v00 - (v01 ** 2) / v11)
            disc = max(0.0, radicand)
            delta_fieller = (z_crit / (abs(b1) * (1.0 - g))) * math.sqrt(disc)
            m_lower = m + term_c - delta_fieller
            m_upper = m + term_c + delta_fieller
        else:
            # Fallback to Wald/Delta method if g >= 1 (weak slope precision)
            m_lower = m - z_crit * se_m
            m_upper = m + z_crit * se_m

        # Transform back to original dose scale
        t = dose_transform.lower()
        if t == "ln":
            dose_est = math.exp(m)
            ci_lower = math.exp(m_lower)
            ci_upper = math.exp(m_upper)
            se_dose = dose_est * se_m
        elif t in ("log10", "log"):
            dose_est = 10.0 ** m
            ci_lower = 10.0 ** m_lower
            ci_upper = 10.0 ** m_upper
            se_dose = dose_est * se_m * math.log(10.0)
        else:
            dose_est = m
            ci_lower = m_lower
            ci_upper = m_upper
            se_dose = se_m

        percentiles_table.append({
            "percent": p * 100.0,
            "estimate": dose_est,
            "se": se_dose,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
        })

    # Equation representation
    sign_str = "+ " if b1 >= 0 else "- "
    link_label = {
        "probit": "Probit(P)",
        "logit": "Logit(P)",
        "weibull": "ln(-ln(1-P))",
        "gompertz": "-ln(-ln(P))",
    }.get(distribution.lower(), "Link(P)")

    dose_expr = dose_name
    if dose_transform.lower() == "ln":
        dose_expr = f"ln({dose_name})"
    elif dose_transform.lower() in ("log10", "log"):
        dose_expr = f"log10({dose_name})"

    equation = f"{link_label} = {b0:.4f} {sign_str}{abs(b1):.4f} * {dose_expr}"

    return {
        "analysis": "probit_analysis",
        "title": f"Probit Analysis: {events_name} versus {dose_name}",
        "distribution": distribution.capitalize(),
        "dose_transform": dose_transform,
        "dose_name": dose_name,
        "events_name": events_name,
        "trials_name": trials_name,
        "n_obs": int(np.sum(arr_tr)),
        "n_events": int(np.sum(arr_ev)),
        "n_doses": k,
        "df": df_fit,
        "confidence": confidence,
        "equation": equation,
        "coefficients": coefficients,
        "goodness_of_fit": {
            "pearson_chi2": pearson_chi2,
            "pearson_p": pearson_p,
            "deviance_chi2": deviance_chi2,
            "deviance_p": deviance_p,
            "df": df_fit,
        },
        "percentiles": percentiles_table,
        "doses": arr_d.tolist(),
        "events": arr_ev.tolist(),
        "trials": arr_tr.tolist(),
        "fitted_prob": pi_fit.tolist(),
    }
