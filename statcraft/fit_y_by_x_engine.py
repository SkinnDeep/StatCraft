"""JMP Fit Y by X Engine (Bivariate, Oneway ANOVA with Means Diamonds, and Contingency Mosaic)."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats


def detect_platform(worksheet, y_index: int, x_index: int) -> str:
    """Determine the analysis platform from column types.

    Continuous Y by Continuous X  -> bivariate
    Continuous Y by Categorical X -> oneway
    Categorical Y by Categorical X -> contingency
    Categorical Y by Continuous X -> logistic
    """
    y_col = worksheet.columns[y_index]
    x_col = worksheet.columns[x_index]

    y_is_num = y_col.kind == "number"
    x_is_num = x_col.kind == "number"

    # Check distinct values if numeric to see if discrete factor
    if y_is_num and x_is_num:
        x_vals = [v for v in x_col.values if v is not None and isinstance(v, (int, float)) and not math.isnan(v)]
        distinct_x = len(set(x_vals))
        if distinct_x <= 6 and len(x_vals) >= distinct_x * 3:
            return "oneway"
        return "bivariate"
    elif y_is_num and not x_is_num:
        return "oneway"
    elif not y_is_num and not x_is_num:
        return "contingency"
    else:
        # Categorical Y, Continuous X
        return "logistic"


def compute_bivariate(
    x_raw: List[Any],
    y_raw: List[Any],
    x_name: str = "X",
    y_name: str = "Y",
    conf: float = 0.95
) -> Dict[str, Any]:
    """Compute Bivariate Fit (Continuous Y by Continuous X) matching JMP Bivariate platform."""
    pairs = []
    for x, y in zip(x_raw, y_raw):
        if x is not None and y is not None:
            try:
                xf, yf = float(x), float(y)
                if not (math.isnan(xf) or math.isnan(yf) or math.isinf(xf) or math.isinf(yf)):
                    pairs.append((xf, yf))
            except (ValueError, TypeError):
                continue

    if len(pairs) < 3:
        raise ValueError("At least 3 valid numeric pairs are required for Bivariate fit.")

    x = np.array([p[0] for p in pairs], dtype=float)
    y = np.array([p[1] for p in pairs], dtype=float)
    n = len(x)

    mean_x = float(np.mean(x))
    mean_y = float(np.mean(y))
    var_x = float(np.var(x, ddof=1))
    var_y = float(np.var(y, ddof=1))
    cov_xy = float(np.cov(x, y)[0, 1])
    r = float(np.corrcoef(x, y)[0, 1]) if var_x > 0 and var_y > 0 else 0.0

    # Linear Regression Y = b0 + b1 * X
    if var_x > 0:
        b1 = cov_xy / var_x
    else:
        b1 = 0.0
    b0 = mean_y - b1 * mean_x

    y_pred = b0 + b1 * x
    resid = y - y_pred

    ss_tot = float(np.sum((y - mean_y) ** 2))
    ss_reg = float(np.sum((y_pred - mean_y) ** 2))
    ss_err = float(np.sum(resid ** 2))

    df_model = 1
    df_err = n - 2
    df_tot = n - 1

    ms_reg = ss_reg / df_model if df_model > 0 else 0.0
    ms_err = ss_err / df_err if df_err > 0 else 0.0

    f_ratio = ms_reg / ms_err if ms_err > 0 else 0.0
    p_f = float(stats.f.sf(f_ratio, df_model, df_err)) if df_err > 0 else 1.0

    r_sq = ss_reg / ss_tot if ss_tot > 0 else 0.0
    r_sq_adj = 1.0 - (ss_err / df_err) / (ss_tot / df_tot) if (df_err > 0 and df_tot > 0 and ss_tot > 0) else 0.0
    rmse = math.sqrt(ms_err) if ms_err >= 0 else 0.0

    # Parameter Estimates
    ss_xx = float(np.sum((x - mean_x) ** 2))
    se_b1 = rmse / math.sqrt(ss_xx) if ss_xx > 0 else 0.0
    se_b0 = rmse * math.sqrt(1.0 / n + (mean_x ** 2) / ss_xx) if ss_xx > 0 else 0.0

    t_b0 = b0 / se_b0 if se_b0 > 0 else 0.0
    p_b0 = float(stats.t.sf(abs(t_b0), df_err) * 2) if df_err > 0 else 1.0

    t_b1 = b1 / se_b1 if se_b1 > 0 else 0.0
    p_b1 = float(stats.t.sf(abs(t_b1), df_err) * 2) if df_err > 0 else 1.0

    # Regression Equation String
    sign = "+" if b1 >= 0 else "-"
    eq_str = f"{y_name} = {b0:.4f} {sign} {abs(b1):.4f} * {x_name}"

    # Generate Prediction / Confidence Curves along X grid
    x_min, x_max = float(np.min(x)), float(np.max(x))
    dx = (x_max - x_min) if x_max > x_min else 1.0
    x_grid = np.linspace(x_min - 0.05 * dx, x_max + 0.05 * dx, 100)
    y_fit_grid = b0 + b1 * x_grid

    t_crit = float(stats.t.ppf(1.0 - (1.0 - conf) / 2.0, df_err)) if df_err > 0 else 2.0
    se_mean = rmse * np.sqrt(1.0 / n + ((x_grid - mean_x) ** 2) / (ss_xx if ss_xx > 0 else 1.0))
    ci_lower = y_fit_grid - t_crit * se_mean
    ci_upper = y_fit_grid + t_crit * se_mean

    # Bivariate Normal Density Ellipses (95% and 50%)
    # Ellipse equation: (X - mu)^T Sigma^-1 (X - mu) = c^2
    cov_mat = np.cov(x, y)
    vals, vecs = np.linalg.eigh(cov_mat)
    # Order eigenvalues descending
    order = vals.argsort()[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    theta_rot = math.atan2(vecs[1, 0], vecs[0, 0])

    t_angles = np.linspace(0, 2 * math.pi, 120)
    ellipses = {}
    for level, prob in [("ellipse_95", 0.95), ("ellipse_50", 0.50)]:
        # Chi2 with 2 df
        c2 = float(stats.chi2.ppf(prob, df=2))
        c = math.sqrt(c2)
        r_a = c * math.sqrt(max(vals[0], 1e-12))
        r_b = c * math.sqrt(max(vals[1], 1e-12))

        # Rotate and translate
        ex = mean_x + r_a * np.cos(t_angles) * math.cos(theta_rot) - r_b * np.sin(t_angles) * math.sin(theta_rot)
        ey = mean_y + r_a * np.cos(t_angles) * math.sin(theta_rot) + r_b * np.sin(t_angles) * math.cos(theta_rot)
        ellipses[level] = {"x": ex.tolist(), "y": ey.tolist(), "label": f"{int(prob*100)}% Density Ellipse"}

    # Kernel / Loess Smoother Points
    smoother_pts = []
    sort_idx = np.argsort(x)
    xs, ys = x[sort_idx], y[sort_idx]
    # Simple moving Gaussian kernel smoother
    bandwidth = (x_max - x_min) * 0.2 if x_max > x_min else 1.0
    for xg in x_grid:
        w = np.exp(-0.5 * ((xs - xg) / bandwidth) ** 2)
        sum_w = float(np.sum(w))
        if sum_w > 1e-9:
            smoother_pts.append(float(np.sum(w * ys) / sum_w))
        else:
            smoother_pts.append(float(b0 + b1 * xg))

    return {
        "platform": "bivariate",
        "title": f"Bivariate Fit of {y_name} By {x_name}",
        "x_name": x_name,
        "y_name": y_name,
        "n": n,
        "r": r,
        "r_sq": r_sq,
        "r_sq_adj": r_sq_adj,
        "rmse": rmse,
        "mean_y": mean_y,
        "mean_x": mean_x,
        "equation": eq_str,
        "b0": b0,
        "b1": b1,
        "anova": {
            "df_model": df_model, "ss_model": ss_reg, "ms_model": ms_reg, "f_ratio": f_ratio, "p_val": p_f,
            "df_error": df_err, "ss_error": ss_err, "ms_error": ms_err,
            "df_total": df_tot, "ss_total": ss_tot
        },
        "parameter_estimates": [
            {"term": "Intercept", "estimate": b0, "std_error": se_b0, "t_ratio": t_b0, "p_val": p_b0},
            {"term": x_name, "estimate": b1, "std_error": se_b1, "t_ratio": t_b1, "p_val": p_b1}
        ],
        "points": {"x": x.tolist(), "y": y.tolist()},
        "line_fit": {"x": x_grid.tolist(), "y": y_fit_grid.tolist()},
        "ci_band": {"x": x_grid.tolist(), "lower": ci_lower.tolist(), "upper": ci_upper.tolist()},
        "smoother": {"x": x_grid.tolist(), "y": smoother_pts},
        "ellipses": ellipses
    }


def compute_oneway(
    x_raw: List[Any],
    y_raw: List[Any],
    x_name: str = "X",
    y_name: str = "Y",
    conf: float = 0.95
) -> Dict[str, Any]:
    """Compute Oneway Analysis (Continuous Y by Categorical X) with JMP Means Diamonds and Tukey HSD."""
    groups_dict: Dict[str, List[float]] = {}
    all_y = []
    for x, y in zip(x_raw, y_raw):
        if x is not None and y is not None:
            try:
                yf = float(y)
                if not (math.isnan(yf) or math.isinf(yf)):
                    group_key = str(x).strip()
                    if group_key not in groups_dict:
                        groups_dict[group_key] = []
                    groups_dict[group_key].append(yf)
                    all_y.append(yf)
            except (ValueError, TypeError):
                continue

    # Require at least 2 groups with at least 1 observation
    valid_groups = {k: v for k, v in groups_dict.items() if len(v) >= 1}
    if len(valid_groups) < 2:
        raise ValueError("At least 2 distinct groups with valid numeric data are required for Oneway analysis.")

    k_groups = len(valid_groups)
    n_tot = len(all_y)
    grand_mean = float(np.mean(all_y))
    df_between = k_groups - 1
    df_within = n_tot - k_groups

    if df_within <= 0:
        raise ValueError("Insufficient degrees of freedom for error in Oneway analysis.")

    # Calculate within-group stats and pooled variance
    group_stats = []
    ss_within = 0.0
    ss_between = 0.0

    ordered_keys = sorted(valid_groups.keys())
    for key in ordered_keys:
        vals = np.array(valid_groups[key], dtype=float)
        nk = len(vals)
        mk = float(np.mean(vals))
        vk = float(np.var(vals, ddof=1)) if nk > 1 else 0.0
        sk = math.sqrt(vk)
        se_k = sk / math.sqrt(nk)
        ss_within += float(np.sum((vals - mk) ** 2))
        ss_between += nk * ((mk - grand_mean) ** 2)

        # Quantiles
        q_min = float(np.min(vals))
        q25 = float(np.percentile(vals, 25))
        q_med = float(np.median(vals))
        q75 = float(np.percentile(vals, 75))
        q_max = float(np.max(vals))

        group_stats.append({
            "level": key,
            "n": nk,
            "mean": mk,
            "std_dev": sk,
            "std_error": se_k,
            "min": q_min,
            "q25": q25,
            "median": q_med,
            "q75": q75,
            "max": q_max,
            "values": vals.tolist()
        })

    ss_tot = ss_between + ss_within
    df_tot = n_tot - 1
    ms_between = ss_between / df_between if df_between > 0 else 0.0
    ms_within = ss_within / df_within if df_within > 0 else 0.0
    s_pooled = math.sqrt(ms_within) if ms_within >= 0 else 0.0

    f_ratio = ms_between / ms_within if ms_within > 0 else 0.0
    p_f = float(stats.f.sf(f_ratio, df_between, df_within))

    # Welch's ANOVA (robust to unequal variances)
    w_weights = [g["n"] / (g["std_dev"]**2 if g["std_dev"] > 0 else 1e-9) for g in group_stats]
    sum_w = sum(w_weights)
    if sum_w > 0:
        x_w_mean = sum(w * g["mean"] for w, g in zip(w_weights, group_stats)) / sum_w
        ss_prime = sum(w * ((g["mean"] - x_w_mean) ** 2) for w, g in zip(w_weights, group_stats))
        term_denom = sum((1.0 - w / sum_w) ** 2 / (g["n"] - 1 if g["n"] > 1 else 1) for w, g in zip(w_weights, group_stats))
        f_welch = ss_prime / (df_between * (1.0 + (2.0 * (k_groups - 2) / (k_groups ** 2 - 1 if k_groups > 1 else 1)) * term_denom)) if term_denom > 0 else f_ratio
        df_welch_denom = (k_groups ** 2 - 1) / (3.0 * term_denom) if term_denom > 0 else float(df_within)
        p_welch = float(stats.f.sf(f_welch, df_between, max(1.0, df_welch_denom)))
    else:
        f_welch, df_welch_denom, p_welch = f_ratio, float(df_within), p_f

    # Signature JMP Means Diamonds:
    # Diamond center line = Group Mean
    # Top and Bottom vertices = Mean +/- t(df_within, alpha/2) * (s_pooled / sqrt(n_k))
    # Horizontal width = proportional to sqrt(n_k)
    t_diamond = float(stats.t.ppf(1.0 - (1.0 - conf) / 2.0, df_within))
    diamonds = []
    max_sqrt_n = max(math.sqrt(g["n"]) for g in group_stats)
    for idx, g in enumerate(group_stats):
        half_height = t_diamond * (s_pooled / math.sqrt(g["n"]))
        half_width = 0.42 * (math.sqrt(g["n"]) / max_sqrt_n if max_sqrt_n > 0 else 1.0)
        ci_low = g["mean"] - half_height
        ci_high = g["mean"] + half_height
        g["ci_lower"] = ci_low
        g["ci_upper"] = ci_high

        # Diamond polygon coordinates (center at x = idx)
        diamond_coords = [
            (idx - half_width, g["mean"]),  # left tip
            (idx, ci_high),                 # top vertex
            (idx + half_width, g["mean"]),  # right tip
            (idx, ci_low),                  # bottom vertex
        ]
        diamonds.append({
            "level": g["level"],
            "center_x": idx,
            "mean": g["mean"],
            "ci_lower": ci_low,
            "ci_upper": ci_high,
            "half_width": half_width,
            "polygon": diamond_coords
        })

    # All Pairs, Tukey-Kramer HSD
    # Studentized range q statistic
    tukey_pairs = []
    # Approximate studentized range critical value
    # q_crit / sqrt(2)
    # Using scipy studentized range if available, else accurate approximation
    try:
        q_crit = float(stats.studentized_range.ppf(conf, k_groups, df_within))
    except Exception:
        # Fallback approximation for q critical
        t_equiv = float(stats.t.ppf(1.0 - (1.0 - conf) / (2.0 * max(1, k_groups)), df_within))
        q_crit = t_equiv * math.sqrt(2.0)

    for i in range(len(group_stats)):
        for j in range(i + 1, len(group_stats)):
            g1 = group_stats[i]
            g2 = group_stats[j]
            diff = g1["mean"] - g2["mean"]
            se_diff = s_pooled * math.sqrt(0.5 * (1.0 / g1["n"] + 1.0 / g2["n"]))
            hsd_margin = (q_crit / math.sqrt(2.0)) * se_diff
            lower_ci = diff - hsd_margin
            upper_ci = diff + hsd_margin
            q_stat = abs(diff) / (s_pooled * math.sqrt(0.5 * (1.0 / g1["n"] + 1.0 / g2["n"]))) if se_diff > 0 else 0.0
            try:
                p_val = float(stats.studentized_range.sf(q_stat * math.sqrt(2.0), k_groups, df_within))
            except Exception:
                p_val = float(stats.t.sf(abs(diff) / (se_diff if se_diff > 0 else 1.0), df_within) * 2)

            is_sig = (lower_ci > 0 or upper_ci < 0)
            tukey_pairs.append({
                "level_1": g1["level"],
                "level_2": g2["level"],
                "difference": diff,
                "std_error": se_diff,
                "lower_cl": lower_ci,
                "upper_cl": upper_ci,
                "p_val": p_val,
                "significant": is_sig
            })

    return {
        "platform": "oneway",
        "title": f"Oneway Analysis of {y_name} By {x_name}",
        "x_name": x_name,
        "y_name": y_name,
        "n": n_tot,
        "grand_mean": grand_mean,
        "s_pooled": s_pooled,
        "r_sq": ss_between / ss_tot if ss_tot > 0 else 0.0,
        "anova": {
            "df_between": df_between, "ss_between": ss_between, "ms_between": ms_between, "f_ratio": f_ratio, "p_val": p_f,
            "df_within": df_within, "ss_within": ss_within, "ms_within": ms_within,
            "df_total": df_tot, "ss_total": ss_tot
        },
        "welch_anova": {
            "f_ratio": f_welch, "df_num": df_between, "df_denom": df_welch_denom, "p_val": p_welch
        },
        "group_stats": group_stats,
        "diamonds": diamonds,
        "tukey_hsd": tukey_pairs
    }


def compute_contingency(
    x_raw: List[Any],
    y_raw: List[Any],
    x_name: str = "X",
    y_name: str = "Y"
) -> Dict[str, Any]:
    """Compute Contingency Analysis (Categorical Y by Categorical X) with JMP Mosaic Plot & Chi-Square."""
    pairs = []
    for x, y in zip(x_raw, y_raw):
        if x is not None and y is not None:
            xs, ys = str(x).strip(), str(y).strip()
            if xs and ys:
                pairs.append((xs, ys))

    if len(pairs) < 4:
        raise ValueError("At least 4 valid observation pairs are required for Contingency analysis.")

    n_tot = len(pairs)
    x_levels = sorted(list(set(p[0] for p in pairs)))
    y_levels = sorted(list(set(p[1] for p in pairs)))

    r_rows = len(y_levels)
    c_cols = len(x_levels)

    # Contingency Counts
    obs_counts = np.zeros((r_rows, c_cols), dtype=int)
    for xs, ys in pairs:
        r_idx = y_levels.index(ys)
        c_idx = x_levels.index(xs)
        obs_counts[r_idx, c_idx] += 1

    col_totals = np.sum(obs_counts, axis=0)
    row_totals = np.sum(obs_counts, axis=1)

    # Expected frequencies
    exp_counts = np.outer(row_totals, col_totals) / float(n_tot)

    # Pearson Chi-Square
    chi2_val = 0.0
    lr_g2_val = 0.0
    for r in range(r_rows):
        for c in range(c_cols):
            o = obs_counts[r, c]
            e = exp_counts[r, c]
            if e > 0:
                chi2_val += ((o - e) ** 2) / e
            if o > 0 and e > 0:
                lr_g2_val += 2.0 * o * math.log(o / e)

    df = (r_rows - 1) * (c_cols - 1)
    p_chi2 = float(stats.chi2.sf(chi2_val, df)) if df > 0 else 1.0
    p_g2 = float(stats.chi2.sf(lr_g2_val, df)) if df > 0 else 1.0

    # Build Mosaic Plot Geometries
    # Columns along X: width proportional to column frequency col_totals[c] / N
    # Rows within Column: height proportional to conditional frequency obs_counts[r, c] / col_totals[c]
    mosaic_tiles = []
    current_x = 0.0
    gap_x = 0.015 if c_cols > 1 else 0.0
    avail_w = 1.0 - (c_cols - 1) * gap_x

    for c in range(c_cols):
        w_col = (col_totals[c] / n_tot) * avail_w
        current_y = 0.0
        gap_y = 0.01 if r_rows > 1 else 0.0
        avail_h = 1.0 - (r_rows - 1) * gap_y

        for r in range(r_rows):
            cnt = obs_counts[r, c]
            cond_prob = cnt / col_totals[c] if col_totals[c] > 0 else 0.0
            h_tile = cond_prob * avail_h
            mosaic_tiles.append({
                "x_level": x_levels[c],
                "y_level": y_levels[r],
                "x0": current_x,
                "y0": current_y,
                "width": w_col,
                "height": h_tile,
                "count": int(cnt),
                "col_total": int(col_totals[c]),
                "row_total": int(row_totals[r]),
                "total_pct": (cnt / n_tot) * 100.0,
                "col_pct": cond_prob * 100.0,
                "row_pct": (cnt / row_totals[r] * 100.0) if row_totals[r] > 0 else 0.0
            })
            current_y += h_tile + gap_y
        current_x += w_col + gap_x

    # Formatted Contingency Grid for Reporting
    grid_rows = []
    for r in range(r_rows):
        row_cells = []
        for c in range(c_cols):
            cnt = obs_counts[r, c]
            row_cells.append({
                "count": int(cnt),
                "total_pct": (cnt / n_tot) * 100.0,
                "col_pct": (cnt / col_totals[c] * 100.0) if col_totals[c] > 0 else 0.0,
                "row_pct": (cnt / row_totals[r] * 100.0) if row_totals[r] > 0 else 0.0,
                "expected": float(exp_counts[r, c])
            })
        grid_rows.append({
            "y_level": y_levels[r],
            "cells": row_cells,
            "row_total": int(row_totals[r]),
            "row_pct": (row_totals[r] / n_tot) * 100.0
        })

    return {
        "platform": "contingency",
        "title": f"Contingency Analysis of {y_name} By {x_name}",
        "x_name": x_name,
        "y_name": y_name,
        "n": n_tot,
        "x_levels": x_levels,
        "y_levels": y_levels,
        "chi2": chi2_val,
        "g2": lr_g2_val,
        "df": df,
        "p_chi2": p_chi2,
        "p_g2": p_g2,
        "col_totals": [int(v) for v in col_totals],
        "grid_rows": grid_rows,
        "mosaic_tiles": mosaic_tiles
    }


def compute_fit_y_by_x(
    worksheet,
    y_index: int,
    x_index: int,
    platform: Optional[str] = None,
    conf: float = 0.95
) -> Dict[str, Any]:
    """Execute Fit Y by X analysis."""
    plat = platform or detect_platform(worksheet, y_index, x_index)
    y_col = worksheet.columns[y_index]
    x_col = worksheet.columns[x_index]

    if plat == "bivariate":
        res = compute_bivariate(x_col.values, y_col.values, x_col.name, y_col.name, conf=conf)
    elif plat == "oneway":
        res = compute_oneway(x_col.values, y_col.values, x_col.name, y_col.name, conf=conf)
    elif plat == "contingency":
        res = compute_contingency(x_col.values, y_col.values, x_col.name, y_col.name)
    else:
        # Default fallback to oneway if Y is numeric else contingency
        if y_col.kind == "number":
            res = compute_oneway(x_col.values, y_col.values, x_col.name, y_col.name, conf=conf)
        else:
            res = compute_contingency(x_col.values, y_col.values, x_col.name, y_col.name)

    res["y_index"] = y_index
    res["x_index"] = x_index
    return res
