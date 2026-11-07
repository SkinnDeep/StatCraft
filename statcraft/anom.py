"""Analysis of Means (ANOM) computational engine matching Minitab 22 specifications.

Supports:
- Normal distribution (One-Way and Two-Way with Main Effects & Interactions)
- Binomial distribution (Proportions / Defectives)
- Poisson distribution (Rates / Counts per unit)

References:
- Nelson, P. R., Wludyka, P. S., & Copeland, K. A. (2005). The Analysis of Means: A Graphical Method
  for Comparing Means, Rates, and Proportions. SIAM.
- Minitab 22 Statistical Methods Reference: Analysis of Means.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

try:
    from scipy import stats
except ImportError:
    stats = None


def _get_t_critical(p: float, df: float) -> float:
    """Accurate Student's t critical value."""
    if df <= 0:
        return 1.96
    if stats is not None:
        return float(stats.t.ppf(p, df))
    # High-precision approximation for t-quantile
    # Hill (1970) / Abramowitz & Stegun
    z = _get_norm_critical(p)
    return z + (z**3 + z) / (4.0 * df)


def _get_norm_critical(p: float) -> float:
    """High-precision standard normal quantile."""
    if stats is not None:
        return float(stats.norm.ppf(p))
    # Beasley-Springer-Moro or rational approximation
    # For common alphas:
    if abs(p - 0.975) < 1e-4:
        return 1.95996
    if abs(p - 0.995) < 1e-4:
        return 2.57583
    if abs(p - 0.95) < 1e-4:
        return 1.64485
    # Rational approximation by Hastings
    t = math.sqrt(-2.0 * math.log(1.0 - p if p > 0.5 else p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    val = t - ((c2 * t + c1) * t + c0) / (((d3 * t + d2) * t + d1) * t + 1.0)
    return val if p > 0.5 else -val


def calculate_anom_normal_1way(
    response: Sequence[Any],
    factor: Sequence[Any],
    alpha: float = 0.05,
    response_name: str = "Response",
    factor_name: str = "Factor",
    title: str = "",
) -> Dict[str, Any]:
    """Compute One-Way Analysis of Means for Normal data."""
    # Group cleaning
    groups: Dict[str, List[float]] = {}
    for y_val, f_val in zip(response, factor):
        if y_val is None or f_val is None:
            continue
        try:
            val_f = float(y_val)
            if math.isnan(val_f) or math.isinf(val_f):
                continue
            groups.setdefault(str(f_val).strip(), []).append(val_f)
        except (ValueError, TypeError):
            continue

    levels = list(groups.keys())
    k = len(levels)
    if k < 2:
        raise ValueError("Analysis of Means requires at least two factor levels.")

    n_i = [len(groups[lvl]) for lvl in levels]
    mean_i = [sum(groups[lvl]) / len(groups[lvl]) for lvl in levels]
    total_n = sum(n_i)
    grand_mean = sum(sum(groups[lvl]) for lvl in levels) / total_n

    # Pooled standard deviation
    ss_within = sum(sum((y - mean_i[i]) ** 2 for y in groups[lvl]) for i, lvl in enumerate(levels))
    df_within = total_n - k
    if df_within <= 0:
        raise ValueError("Insufficient degrees of freedom for pooled variance estimation.")
    s_p = math.sqrt(ss_within / df_within)

    # Bonferroni-Nelson t critical value
    # Under H0, test stat: (Ybar_i - Ybar_grand) / (s_p * sqrt((N - n_i) / (N * n_i)))
    p_crit = 1.0 - alpha / (2.0 * k)
    h_crit = _get_t_critical(p_crit, df_within)

    levels_data = []
    outliers_detected = False
    for i, lvl in enumerate(levels):
        ni = n_i[i]
        mi = mean_i[i]
        se_i = s_p * math.sqrt((total_n - ni) / (total_n * ni))
        udl = grand_mean + h_crit * se_i
        ldl = grand_mean - h_crit * se_i
        diff = mi - grand_mean
        is_sig = mi > udl or mi < ldl
        if is_sig:
            outliers_detected = True
        levels_data.append({
            "level": lvl,
            "n": ni,
            "mean": mi,
            "se": se_i,
            "udl": udl,
            "ldl": ldl,
            "diff": diff,
            "significant": is_sig,
        })

    return {
        "analysis": "anom",
        "distribution": "normal",
        "type": "one_way",
        "title": title or f"Analysis of Means for {response_name} by {factor_name}",
        "response_name": response_name,
        "factor_name": factor_name,
        "alpha": alpha,
        "grand_mean": grand_mean,
        "pooled_sd": s_p,
        "df": df_within,
        "k": k,
        "total_n": total_n,
        "critical_value": h_crit,
        "levels": levels_data,
        "outliers_detected": outliers_detected,
    }


def calculate_anom_binomial(
    response: Sequence[Any],
    factor: Sequence[Any],
    sample_size: Union[int, Sequence[Any]] = 100,
    alpha: float = 0.05,
    response_name: str = "Defectives",
    factor_name: str = "Factor",
    title: str = "",
) -> Dict[str, Any]:
    """Compute Analysis of Means for Binomial (Proportions) data."""
    # Group cleaning
    groups_events: Dict[str, float] = {}
    groups_n: Dict[str, float] = {}

    is_const_n = isinstance(sample_size, (int, float))

    for i, (y_val, f_val) in enumerate(zip(response, factor)):
        if y_val is None or f_val is None:
            continue
        try:
            ev = float(y_val)
            if math.isnan(ev):
                continue
            lvl = str(f_val).strip()
            if is_const_n:
                n_val = float(sample_size)
            else:
                n_val = float(sample_size[i]) if i < len(sample_size) and sample_size[i] is not None else float(sample_size[0])
            if n_val <= 0 or ev < 0:
                continue

            groups_events[lvl] = groups_events.get(lvl, 0.0) + ev
            groups_n[lvl] = groups_n.get(lvl, 0.0) + n_val
        except (ValueError, TypeError, IndexError):
            continue

    levels = list(groups_events.keys())
    k = len(levels)
    if k < 2:
        raise ValueError("Analysis of Means for Binomial data requires at least two factor levels.")

    tot_events = sum(groups_events.values())
    tot_n = sum(groups_n.values())
    if tot_n <= 0:
        raise ValueError("Total sample size must be greater than zero.")
    grand_p = tot_events / tot_n

    p_crit = 1.0 - alpha / (2.0 * k)
    z_crit = _get_norm_critical(p_crit)

    levels_data = []
    outliers_detected = False
    for lvl in levels:
        ev = groups_events[lvl]
        ni = groups_n[lvl]
        pi = ev / ni
        se_i = math.sqrt((grand_p * (1.0 - grand_p) / ni) * ((tot_n - ni) / tot_n)) if tot_n > ni else 0.0
        udl = min(1.0, grand_p + z_crit * se_i)
        ldl = max(0.0, grand_p - z_crit * se_i)
        diff = pi - grand_p
        is_sig = pi > udl or pi < ldl
        if is_sig:
            outliers_detected = True
        levels_data.append({
            "level": lvl,
            "events": ev,
            "n": ni,
            "rate": pi,
            "mean": pi,
            "se": se_i,
            "udl": udl,
            "ldl": ldl,
            "diff": diff,
            "significant": is_sig,
        })

    return {
        "analysis": "anom",
        "distribution": "binomial",
        "type": "one_way",
        "title": title or f"Analysis of Means for {response_name} Proportions by {factor_name}",
        "response_name": response_name,
        "factor_name": factor_name,
        "alpha": alpha,
        "grand_mean": grand_p,
        "total_events": tot_events,
        "total_n": tot_n,
        "k": k,
        "critical_value": z_crit,
        "levels": levels_data,
        "outliers_detected": outliers_detected,
    }


def calculate_anom_poisson(
    response: Sequence[Any],
    factor: Sequence[Any],
    sample_size: Union[int, float, Sequence[Any]] = 1.0,
    alpha: float = 0.05,
    response_name: str = "Count",
    factor_name: str = "Factor",
    title: str = "",
) -> Dict[str, Any]:
    """Compute Analysis of Means for Poisson (Rate / Counts per Unit) data."""
    groups_counts: Dict[str, float] = {}
    groups_units: Dict[str, float] = {}

    is_const_u = isinstance(sample_size, (int, float))

    for i, (y_val, f_val) in enumerate(zip(response, factor)):
        if y_val is None or f_val is None:
            continue
        try:
            cnt = float(y_val)
            if math.isnan(cnt):
                continue
            lvl = str(f_val).strip()
            if is_const_u:
                u_val = float(sample_size)
            else:
                u_val = float(sample_size[i]) if i < len(sample_size) and sample_size[i] is not None else 1.0
            if u_val <= 0 or cnt < 0:
                continue

            groups_counts[lvl] = groups_counts.get(lvl, 0.0) + cnt
            groups_units[lvl] = groups_units.get(lvl, 0.0) + u_val
        except (ValueError, TypeError, IndexError):
            continue

    levels = list(groups_counts.keys())
    k = len(levels)
    if k < 2:
        raise ValueError("Analysis of Means for Poisson data requires at least two factor levels.")

    tot_counts = sum(groups_counts.values())
    tot_units = sum(groups_units.values())
    if tot_units <= 0:
        raise ValueError("Total unit exposure must be greater than zero.")
    grand_lambda = tot_counts / tot_units

    p_crit = 1.0 - alpha / (2.0 * k)
    z_crit = _get_norm_critical(p_crit)

    levels_data = []
    outliers_detected = False
    for lvl in levels:
        cnt = groups_counts[lvl]
        ui = groups_units[lvl]
        ci = cnt / ui
        se_i = math.sqrt((grand_lambda / ui) * ((tot_units - ui) / tot_units)) if tot_units > ui else 0.0
        udl = grand_lambda + z_crit * se_i
        ldl = max(0.0, grand_lambda - z_crit * se_i)
        diff = ci - grand_lambda
        is_sig = ci > udl or ci < ldl
        if is_sig:
            outliers_detected = True
        levels_data.append({
            "level": lvl,
            "count": cnt,
            "units": ui,
            "rate": ci,
            "mean": ci,
            "se": se_i,
            "udl": udl,
            "ldl": ldl,
            "diff": diff,
            "significant": is_sig,
        })

    return {
        "analysis": "anom",
        "distribution": "poisson",
        "type": "one_way",
        "title": title or f"Analysis of Means for {response_name} Rates by {factor_name}",
        "response_name": response_name,
        "factor_name": factor_name,
        "alpha": alpha,
        "grand_mean": grand_lambda,
        "total_counts": tot_counts,
        "total_units": tot_units,
        "k": k,
        "critical_value": z_crit,
        "levels": levels_data,
        "outliers_detected": outliers_detected,
    }


def calculate_anom_normal_2way(
    response: Sequence[Any],
    factor1: Sequence[Any],
    factor2: Sequence[Any],
    alpha: float = 0.05,
    response_name: str = "Response",
    factor1_name: str = "Factor 1",
    factor2_name: str = "Factor 2",
    title: str = "",
) -> Dict[str, Any]:
    """Compute Two-Way Analysis of Means for Normal data (Main Effects and Interaction)."""
    # 1. Clean data rows
    rows: List[Tuple[float, str, str]] = []
    for y, f1, f2 in zip(response, factor1, factor2):
        if y is None or f1 is None or f2 is None:
            continue
        try:
            yf = float(y)
            if math.isnan(yf) or math.isinf(yf):
                continue
            rows.append((yf, str(f1).strip(), str(f2).strip()))
        except (ValueError, TypeError):
            continue

    if len(rows) < 4:
        raise ValueError("Two-Way Analysis of Means requires at least 4 valid observations.")

    f1_lvls = sorted(list({r[1] for r in rows}))
    f2_lvls = sorted(list({r[2] for r in rows}))
    k1, k2 = len(f1_lvls), len(f2_lvls)
    if k1 < 2 or k2 < 2:
        raise ValueError("Two-Way ANOM requires at least two levels for both factors.")

    total_n = len(rows)
    grand_mean = sum(r[0] for r in rows) / total_n

    # Cell means
    cells: Dict[Tuple[str, str], List[float]] = {}
    for yf, s1, s2 in rows:
        cells.setdefault((s1, s2), []).append(yf)

    # Within cell SS
    ss_within = 0.0
    for cell_vals in cells.values():
        c_mean = sum(cell_vals) / len(cell_vals)
        ss_within += sum((v - c_mean) ** 2 for v in cell_vals)

    df_within = total_n - len(cells)
    if df_within <= 0:
        # Fallback to additive model residual df
        df_within = max(1, total_n - (k1 + k2 - 1))
    s_p = math.sqrt(ss_within / df_within)

    # 1. Factor 1 Main Effects
    f1_res = calculate_anom_normal_1way(
        response=[r[0] for r in rows],
        factor=[r[1] for r in rows],
        alpha=alpha,
        response_name=response_name,
        factor_name=factor1_name,
        title=f"One-Way ANOM for {response_name} by {factor1_name}",
    )
    # Re-apply 2-way pooled MSE
    h_f1 = _get_t_critical(1.0 - alpha / (2.0 * k1), df_within)
    for row_item in f1_res["levels"]:
        ni = row_item["n"]
        se_i = s_p * math.sqrt((total_n - ni) / (total_n * ni))
        row_item["udl"] = grand_mean + h_f1 * se_i
        row_item["ldl"] = grand_mean - h_f1 * se_i
        row_item["significant"] = row_item["mean"] > row_item["udl"] or row_item["mean"] < row_item["ldl"]
    f1_res["pooled_sd"] = s_p
    f1_res["df"] = df_within
    f1_res["critical_value"] = h_f1

    # 2. Factor 2 Main Effects
    f2_res = calculate_anom_normal_1way(
        response=[r[0] for r in rows],
        factor=[r[2] for r in rows],
        alpha=alpha,
        response_name=response_name,
        factor_name=factor2_name,
        title=f"One-Way ANOM for {response_name} by {factor2_name}",
    )
    h_f2 = _get_t_critical(1.0 - alpha / (2.0 * k2), df_within)
    for row_item in f2_res["levels"]:
        ni = row_item["n"]
        se_i = s_p * math.sqrt((total_n - ni) / (total_n * ni))
        row_item["udl"] = grand_mean + h_f2 * se_i
        row_item["ldl"] = grand_mean - h_f2 * se_i
        row_item["significant"] = row_item["mean"] > row_item["udl"] or row_item["mean"] < row_item["ldl"]
    f2_res["pooled_sd"] = s_p
    f2_res["df"] = df_within
    f2_res["critical_value"] = h_f2

    # 3. Two-Way Interaction Effects:
    # Interaction effect for cell (i, j): alpha_beta_ij = Ybar_ij - Ybar_i - Ybar_j + Ybar_grand
    k_int = k1 * k2
    h_int = _get_t_critical(1.0 - alpha / (2.0 * k_int), df_within)
    int_levels = []
    int_outliers = False
    for s1 in f1_lvls:
        for s2 in f2_lvls:
            cell_vals = cells.get((s1, s2), [])
            if not cell_vals:
                continue
            y_ij = sum(cell_vals) / len(cell_vals)
            y_i = next(item["mean"] for item in f1_res["levels"] if item["level"] == s1)
            y_j = next(item["mean"] for item in f2_res["levels"] if item["level"] == s2)
            int_effect = y_ij - y_i - y_j + grand_mean
            nij = len(cell_vals)
            # SE for interaction effect
            se_ij = s_p * math.sqrt(((k1 - 1) * (k2 - 1)) / (k1 * k2 * nij)) if nij > 0 else 0.0
            udl_int = h_int * se_ij
            ldl_int = -h_int * se_ij
            is_sig = int_effect > udl_int or int_effect < ldl_int
            if is_sig:
                int_outliers = True
            int_levels.append({
                "level": f"{s1} * {s2}",
                "factor1_level": s1,
                "factor2_level": s2,
                "n": nij,
                "mean": int_effect,
                "udl": udl_int,
                "ldl": ldl_int,
                "diff": int_effect,
                "significant": is_sig,
            })

    int_res = {
        "analysis": "anom",
        "distribution": "normal",
        "type": "interaction",
        "title": f"ANOM for {response_name} Interaction ({factor1_name} * {factor2_name})",
        "response_name": response_name,
        "factor_name": f"{factor1_name} * {factor2_name}",
        "alpha": alpha,
        "grand_mean": 0.0,
        "pooled_sd": s_p,
        "df": df_within,
        "k": k_int,
        "critical_value": h_int,
        "levels": int_levels,
        "outliers_detected": int_outliers,
    }

    return {
        "analysis": "anom",
        "distribution": "normal",
        "type": "two_way",
        "title": title or f"Two-Way Analysis of Means for {response_name} by {factor1_name}, {factor2_name}",
        "response_name": response_name,
        "factor1_name": factor1_name,
        "factor2_name": factor2_name,
        "alpha": alpha,
        "grand_mean": grand_mean,
        "pooled_sd": s_p,
        "df": df_within,
        "factor1": f1_res,
        "factor2": f2_res,
        "interaction": int_res,
    }
