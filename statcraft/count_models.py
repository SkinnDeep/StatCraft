"""Poisson Goodness-of-Fit Test and Negative Binomial (NB2) Regression."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
from scipy import optimize, special, stats


def goodness_of_fit_poisson(values: Sequence[Any], variable_name: str = "Counts") -> Dict[str, Any]:
    """Perform Minitab-style Chi-Square Goodness-of-Fit Test for Poisson distribution."""
    cleaned: List[int] = []
    for v in values:
        if v is None or isinstance(v, bool):
            continue
        try:
            fv = float(v)
        except (ValueError, TypeError):
            continue
        if not math.isfinite(fv) or fv < 0 or abs(fv - round(fv)) > 1e-9:
            raise ValueError("Poisson count data must contain nonnegative integers.")
        cleaned.append(int(round(fv)))

    n = len(cleaned)
    if n < 5:
        raise ValueError("Goodness-of-Fit Test for Poisson requires at least 5 observations.")

    mean_lambda = float(np.mean(cleaned))
    var_val = float(np.var(cleaned, ddof=1))
    if mean_lambda <= 0:
        raise ValueError("Sample mean count must be positive.")

    freq = Counter(cleaned)
    max_k = max(freq.keys())

    # Build category bins: 0, 1, ..., max_k and group right/left tail bins if E < 5
    bins = []
    cum_p = 0.0
    for k in range(max_k + 1):
        pk = float(stats.poisson.pmf(k, mean_lambda))
        cum_p += pk
        bins.append({"label": str(k), "k_low": k, "k_high": k, "obs": freq.get(k, 0), "exp": n * pk})

    # Include > max_k remaining tail probability into last bin
    rem_p = max(0.0, 1.0 - cum_p)
    bins[-1]["exp"] += n * rem_p
    bins[-1]["label"] = f">={max_k}" if rem_p * n > 0.01 else str(max_k)

    # Pool tail bins backward while last bin expected < 5.0 and len(bins) > 3
    while len(bins) > 3 and bins[-1]["exp"] < 5.0:
        tail = bins.pop()
        bins[-1]["obs"] += tail["obs"]
        bins[-1]["exp"] += tail["exp"]
        bins[-1]["label"] = f">={bins[-1]['k_low']}"

    # Pool leading bins forward while first bin expected < 5.0 and len(bins) > 3
    while len(bins) > 3 and bins[0]["exp"] < 5.0:
        head = bins.pop(0)
        bins[0]["obs"] += head["obs"]
        bins[0]["exp"] += head["exp"]
        bins[0]["label"] = f"<={bins[0]['k_high']}"

    chi_sq = sum(((b["obs"] - b["exp"]) ** 2) / max(b["exp"], 1e-12) for b in bins)
    df = max(1, len(bins) - 2)
    p_value = float(1.0 - stats.chi2.cdf(chi_sq, df))

    return {
        "analysis": "poisson_gof",
        "variable": variable_name,
        "n": n,
        "mean": mean_lambda,
        "variance": var_val,
        "dispersion_ratio": var_val / mean_lambda,
        "bins": bins,
        "chi_square": float(chi_sq),
        "df": int(df),
        "p_value": p_value,
    }


def _negbin_loglik(y: np.ndarray, mu: np.ndarray, alpha: float) -> float:
    r = 1.0 / max(alpha, 1e-10)
    ll = np.sum(
        special.gammaln(y + r)
        - special.gammaln(r)
        - special.gammaln(y + 1.0)
        + r * np.log(r / (r + mu))
        + y * np.log(np.maximum(mu, 1e-15) / (r + mu))
    )
    return float(ll)


def _poisson_loglik(y: np.ndarray, mu: np.ndarray) -> float:
    return float(np.sum(y * np.log(np.maximum(mu, 1e-15)) - mu - special.gammaln(y + 1.0)))


def negative_binomial_regression(
    worksheet,
    response_index: int,
    predictor_indices: Sequence[int],
    exposure_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Fit Negative Binomial (NB2) GLM with log link via Maximum Likelihood."""
    if not predictor_indices:
        raise ValueError("Select at least one continuous predictor.")
    if response_index in predictor_indices or (exposure_index is not None and (exposure_index == response_index or exposure_index in predictor_indices)):
        raise ValueError("Response, predictors, and exposure column must be distinct.")

    resp_col = worksheet.columns[response_index]
    pred_cols = [worksheet.columns[i] for i in predictor_indices]
    exp_col = worksheet.columns[exposure_index] if exposure_index is not None else None

    rows_y, rows_x, rows_off = [], [], []
    n_rows = worksheet.row_count
    for r in range(n_rows):
        yv = resp_col.values[r] if r < len(resp_col.values) else None
        xvs = [c.values[r] if r < len(c.values) else None for c in pred_cols]
        ov = exp_col.values[r] if (exp_col is not None and r < len(exp_col.values)) else 1.0
        if yv is None or any(v is None for v in xvs) or ov is None:
            continue
        try:
            yf = float(yv)
            xf = [float(v) for v in xvs]
            of = float(ov)
        except (ValueError, TypeError):
            continue
        if yf < 0 or of <= 0 or not (math.isfinite(yf) and math.isfinite(of) and all(math.isfinite(x) for x in xf)):
            continue
        rows_y.append(yf)
        rows_x.append(xf)
        rows_off.append(math.log(of))

    n = len(rows_y)
    p = len(predictor_indices) + 1
    if n <= p + 1:
        raise ValueError("Insufficient complete observations for Negative Binomial Regression.")

    y = np.asarray(rows_y, dtype=float)
    X = np.column_stack([np.ones(n), np.asarray(rows_x, dtype=float)])
    offset = np.asarray(rows_off, dtype=float)

    # 1. Fit Poisson baseline first for starting values & LR dispersion test
    def pois_nll(beta):
        eta = np.clip(X @ beta + offset, -20.0, 20.0)
        mu = np.exp(eta)
        return -_poisson_loglik(y, mu)

    beta0 = np.zeros(p)
    beta0[0] = math.log(max(float(np.mean(y)) / math.exp(float(np.mean(offset))), 1e-4))
    res_pois = optimize.minimize(pois_nll, beta0, method="BFGS")
    beta_pois = res_pois.x
    ll_pois = -float(res_pois.fun)

    # 2. Maximize NB2 Log-Likelihood jointly over (beta, log_alpha)
    def nb_nll(theta):
        beta = theta[:-1]
        log_alpha = float(np.clip(theta[-1], -12.0, 6.0))
        alpha = math.exp(log_alpha)
        eta = np.clip(X @ beta + offset, -20.0, 20.0)
        mu = np.exp(eta)
        return -_negbin_loglik(y, mu, alpha)

    init_theta = np.append(beta_pois, -1.0)
    bounds = [(-50.0, 50.0)] * p + [(-12.0, 6.0)]
    res_nb = optimize.minimize(nb_nll, init_theta, method="L-BFGS-B", bounds=bounds)
    theta_hat = res_nb.x
    beta_hat = theta_hat[:-1]
    alpha_hat = math.exp(float(theta_hat[-1]))
    ll_nb = -float(res_nb.fun)

    eta_hat = np.clip(X @ beta_hat + offset, -20.0, 20.0)
    mu_hat = np.exp(eta_hat)
    # Fisher information matrix I(beta) = X^T W X where W_i = mu_i / (1 + alpha * mu_i)
    w = mu_hat / (1.0 + alpha_hat * mu_hat)
    info_mat = (X * w[:, None]).T @ X
    try:
        cov_beta = np.linalg.inv(info_mat)
        se_beta = np.sqrt(np.maximum(np.diag(cov_beta), 1e-18))
    except np.linalg.LinAlgError:
        cov_beta = np.linalg.pinv(info_mat)
        se_beta = np.sqrt(np.maximum(np.diag(cov_beta), 1e-18))

    terms = ["Constant"] + [c.name for c in pred_cols]
    coeffs = []
    for name, b, se in zip(terms, beta_hat, se_beta):
        z = float(b / se) if se > 0 else 0.0
        pv = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))
        coeffs.append({
            "term": name,
            "coef": float(b),
            "se_coef": float(se),
            "z_value": z,
            "p_value": pv,
            "irr": float(math.exp(min(b, 50.0))),
        })

    lr_stat = max(0.0, 2.0 * (ll_nb - ll_pois))
    lr_p = float(0.5 * (1.0 - stats.chi2.cdf(lr_stat, 1))) if lr_stat > 0 else 1.0
    k_params = p + 1
    aic = 2.0 * k_params - 2.0 * ll_nb
    bic = k_params * math.log(n) - 2.0 * ll_nb

    return {
        "analysis": "negative_binomial_regression",
        "response": resp_col.name,
        "predictors": [c.name for c in pred_cols],
        "exposure": exp_col.name if exp_col is not None else None,
        "n": int(n),
        "alpha": float(alpha_hat),
        "log_likelihood": float(ll_nb),
        "poisson_log_likelihood": float(ll_pois),
        "lr_dispersion_stat": float(lr_stat),
        "lr_dispersion_p": lr_p,
        "aic": float(aic),
        "bic": float(bic),
        "coefficients": coeffs,
    }


def format_count_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    lines = []
    if kind == "poisson_gof":
        lines.extend([
            f"Goodness-of-Fit Test for Poisson: {result['variable']}",
            f"  N = {result['n']}   |   Mean (Lambda) = {result['mean']:.5g}   |   Variance/Mean = {result['dispersion_ratio']:.4f}",
            "",
            "  Category     Observed     Expected   Contribution to Chi-Sq",
            "  " + "-" * 62,
        ])
        for b in result["bins"]:
            contrib = ((b["obs"] - b["exp"]) ** 2) / max(b["exp"], 1e-12)
            lines.append(f"  {b['label']:<10}  {b['obs']:>9d}  {b['exp']:>11.3f}   {contrib:>12.4f}")
        lines.extend([
            "",
            f"  Pearson Chi-Square = {result['chi_square']:.4f}, DF = {result['df']}, P-Value = {result['p_value']:.4f}",
        ])
    elif kind == "negative_binomial_regression":
        lines.extend([
            f"Negative Binomial Regression (NB2 Log-Link): {result['response']}",
            f"  N = {result['n']}   |   Dispersion (Alpha) = {result['alpha']:.5g}",
            f"  Log-Likelihood = {result['log_likelihood']:.3f}   |   AIC = {result['aic']:.3f}   |   BIC = {result['bic']:.3f}",
            f"  LR Test vs Poisson (Alpha = 0): Chi-Sq = {result['lr_dispersion_stat']:.4f}, P-Value = {result['lr_dispersion_p']:.4f}",
            "",
            "  Term             Coef      SE Coef       Z-Value   P-Value      IRR (e^B)",
            "  " + "-" * 74,
        ])
        for c in result["coefficients"]:
            lines.append(
                f"  {c['term']:<14} {c['coef']:>9.4f}  {c['se_coef']:>10.4f}  {c['z_value']:>11.3f}  {c['p_value']:>8.4f}  {c['irr']:>12.4f}"
            )
    return "\n".join(lines)
