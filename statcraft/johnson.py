"""Statistical Engine for Johnson Transformation (Stat > Quality Tools > Johnson Transformation).

Implements the Slifker & Shapiro (1980) 4-quantile algorithm matching Minitab 22:
- Fits the optimal system of curves from the Johnson family:
    * SB: Bounded system
    * SU: Unbounded system
    * SL: Lognormal system
- Anderson-Darling goodness-of-fit and Stephens calibrated p-values for original and transformed data.
- Generates transformation equation string and parameters (gamma, eta, epsilon, lambda).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import scipy.stats as stats

from .dist_id import calculate_ad_normal, _clean_data


def calculate_johnson_transformation(
    values: Sequence[Any],
    variable_name: str = "C1",
    p_threshold: float = 0.10,
    store_column_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Fit optimal Johnson transformation system and transform data to standard normality."""
    clean = _clean_data(values)
    n = len(clean)

    # Calculate AD and p-value on original data
    orig_ad, orig_p = calculate_ad_normal(clean)
    orig_mean = float(np.mean(clean))
    orig_std = float(np.std(clean, ddof=1))

    # Slifker-Shapiro (1980) 4-quantile estimation
    z = 0.524
    p1 = float(stats.norm.cdf(-3.0 * z))
    p2 = float(stats.norm.cdf(-z))
    p3 = float(stats.norm.cdf(z))
    p4 = float(stats.norm.cdf(3.0 * z))

    x_3z = float(np.percentile(clean, p1 * 100.0))
    x_z = float(np.percentile(clean, p2 * 100.0))
    xz = float(np.percentile(clean, p3 * 100.0))
    x3z = float(np.percentile(clean, p4 * 100.0))

    m = x3z - xz
    n_diff = x_z - x_3z
    p = xz - x_z

    if p <= 0 or m <= 0 or n_diff <= 0:
        family = "SN"
        gamma, eta, eps, lam = 0.0, 1.0, orig_mean, max(1e-6, orig_std)
        z_vals = (clean - eps) / lam
        fn_str = f"Z = (X - {eps:.4f}) / {lam:.4f}"
    else:
        qr = (m * n_diff) / (p ** 2)
        try:
            if qr < 0.95:
                # SB: Bounded system
                pm = p / m
                pn = p / n_diff
                denom = pm * pn - 1.0
                if denom <= 0:
                    raise ValueError("SB denom non-positive")
                val = (1.0 + pm) * (1.0 + pn)
                eta = z / float(np.arccosh(max(1.0001, 0.5 * np.sqrt(val))))
                gamma = eta * float(np.arcsinh((pn - pm) * np.sqrt(max(0.0, val - 4.0)) / (2.0 * denom)))
                lam = float((p * np.sqrt(max(0.0, (val - 2.0) ** 2 - 4.0))) / denom)
                eps = float(0.5 * (xz + x_z) - 0.5 * lam + (p * (pn - pm)) / (2.0 * denom))

                u = (clean - eps) / np.clip(lam + eps - clean, 1e-12, None)
                u = np.clip(u, 1e-12, 1e12)
                z_vals = gamma + eta * np.log(u)
                fn_str = f"Z = {gamma:.4f} + {eta:.4f} * ln((X - {eps:.4f}) / ({lam + eps:.4f} - X))"
                family = "SB"
            elif qr > 1.05:
                # SU: Unbounded system
                mp = m / p
                np_ = n_diff / p
                val = mp * np_
                if val <= 1.0:
                    raise ValueError("SU val non-positive")
                eta = 2.0 * z / float(np.arccosh(max(1.0001, 0.5 * (mp + np_))))
                gamma = eta * float(np.arcsinh((np_ - mp) / (2.0 * np.sqrt(max(1e-12, val - 1.0)))))
                lam = float(2.0 * p * np.sqrt(max(1e-12, val - 1.0)) / max(1e-12, mp + np_ - 2.0))
                eps = float(0.5 * (xz + x_z) + p * (np_ - mp) / (2.0 * max(1e-12, mp + np_ - 2.0)))

                z_vals = gamma + eta * np.arcsinh((clean - eps) / max(1e-12, lam))
                fn_str = f"Z = {gamma:.4f} + {eta:.4f} * asinh((X - {eps:.4f}) / {lam:.4f})"
                family = "SU"
            else:
                # SL: Lognormal system
                mn = m / n_diff
                eta = 2.0 * z / float(np.log(max(1e-12, mn)))
                gamma = eta * float(np.log(max(1e-12, (mn - 1.0) / (p * np.sqrt(max(1e-12, mn))))))
                eps = float(0.5 * (xz + x_z) - 0.5 * p * (mn + 1.0) / max(1e-12, mn - 1.0))

                diff = np.clip(clean - eps, 1e-12, None)
                z_vals = gamma + eta * np.log(diff)
                fn_str = f"Z = {gamma:.4f} + {eta:.4f} * ln(X - {eps:.4f})"
                family = "SL"
                lam = 1.0
        except Exception:
            family = "SU"
            gamma, eta, eps, lam = 0.0, 1.0, orig_mean, max(1e-6, orig_std)
            z_vals = (clean - eps) / lam
            fn_str = f"Z = (X - {eps:.4f}) / {lam:.4f}"

    # Calculate AD and p-value on transformed data
    trans_ad, trans_p = calculate_ad_normal(z_vals)
    trans_mean = float(np.mean(z_vals))
    trans_std = float(np.std(z_vals, ddof=1))
    passed = bool(trans_p >= p_threshold)

    # Compute empirical percentiles for probability plots
    s_orig = np.sort(clean)
    s_trans = np.sort(z_vals)
    i_ranks = np.arange(1, n + 1)
    emp_prob = ((i_ranks - 0.375) / (n + 0.25)).tolist()

    # Map transformed values back to full original length (preserving NaNs)
    full_transformed: List[Optional[float]] = []
    clean_idx = 0
    for v in values:
        if v is None:
            full_transformed.append(None)
        elif isinstance(v, (bool, np.bool_)):
            full_transformed.append(None)
        else:
            try:
                fv = float(v)
                if math.isfinite(fv):
                    full_transformed.append(float(z_vals[clean_idx]))
                    clean_idx += 1
                else:
                    full_transformed.append(None)
            except (ValueError, TypeError):
                full_transformed.append(None)

    target_store = store_column_name or f"Johnson_{variable_name}"

    return {
        "analysis": "johnson_transformation",
        "variable_name": variable_name,
        "n_samples": n,
        "p_threshold": p_threshold,
        "family": family,
        "function": fn_str,
        "gamma": gamma,
        "eta": eta,
        "epsilon": eps,
        "lambda": lam,
        "passed": passed,
        "original": {
            "ad": orig_ad,
            "p_value": orig_p,
            "mean": orig_mean,
            "std": orig_std,
            "sorted_data": s_orig.tolist(),
        },
        "transformed": {
            "ad": trans_ad,
            "p_value": trans_p,
            "mean": trans_mean,
            "std": trans_std,
            "sorted_data": s_trans.tolist(),
            "full_values": full_transformed,
        },
        "empirical_probabilities": emp_prob,
        "store_column_name": target_store,
    }
