"""Advanced ANOVA Engines: Balanced ANOVA, Fully Nested ANOVA, and One-Way MANOVA."""
from __future__ import annotations

import itertools
import math
from typing import Any, Dict, List, Sequence
import numpy as np
from scipy import stats


def _extract_complete_rows(worksheet, response_indices: Sequence[int], factor_indices: Sequence[int]):
    resp_cols = [worksheet.columns[i] for i in response_indices]
    fac_cols = [worksheet.columns[i] for i in factor_indices]
    ys_all = []
    fs_all = []
    for r in range(worksheet.row_count):
        yvs = [c.values[r] if r < len(c.values) else None for c in resp_cols]
        fvs = [c.values[r] if r < len(c.values) else None for c in fac_cols]
        if any(v is None for v in yvs) or any(v is None or (isinstance(v, str) and not v.strip()) for v in fvs):
            continue
        try:
            yf = [float(v) for v in yvs]
        except (ValueError, TypeError):
            continue
        if not all(math.isfinite(x) for x in yf):
            continue
        ff = [str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip() for v in fvs]
        ys_all.append(yf)
        fs_all.append(ff)
    return np.asarray(ys_all, dtype=float), fs_all


def _effect_coded_columns(labels: List[str]) -> tuple[np.ndarray, List[str]]:
    levels = sorted(set(labels))
    if len(levels) < 2:
        raise ValueError("Each ANOVA factor must have at least 2 distinct levels.")
    # Sum-to-zero effect coding (or standard dummy coding dropping last level)
    k = len(levels)
    n = len(labels)
    mat = np.zeros((n, k - 1), dtype=float)
    last = levels[-1]
    lvl_idx = {lv: i for i, lv in enumerate(levels[:-1])}
    for r, val in enumerate(labels):
        if val == last:
            mat[r, :] = -1.0
        else:
            mat[r, lvl_idx[val]] = 1.0
    return mat, levels


def balanced_anova(
    worksheet,
    response_index: int,
    factor_indices: Sequence[int],
    include_interactions: bool = True,
) -> Dict[str, Any]:
    """Fit multi-factor Balanced ANOVA via hierarchical sequential projection."""
    if not factor_indices or len(factor_indices) > 4:
        raise ValueError("Balanced ANOVA supports 1 to 4 factors.")
    if response_index in factor_indices:
        raise ValueError("Response column cannot also be a factor.")

    Y_mat, factor_rows = _extract_complete_rows(worksheet, [response_index], factor_indices)
    if len(Y_mat) < 3:
        raise ValueError("Balanced ANOVA requires at least 3 complete observations.")

    y = Y_mat[:, 0]
    n = len(y)
    factor_names = [worksheet.columns[i].name for i in factor_indices]

    # Verify balanced cell counts
    cell_counts: Dict[tuple, int] = {}
    for row in factor_rows:
        t = tuple(row)
        cell_counts[t] = cell_counts.get(t, 0) + 1
    expected_cells = 1
    factor_mats = []
    for f_i in range(len(factor_indices)):
        col_labels = [row[f_i] for row in factor_rows]
        mat, lvls = _effect_coded_columns(col_labels)
        factor_mats.append(mat)
        expected_cells *= len(lvls)

    if len(cell_counts) != expected_cells or len(set(cell_counts.values())) != 1:
        raise ValueError("Design is unbalanced; use General Linear Model (GLM) for unbalanced factor counts.")

    y_mean = float(np.mean(y))
    ss_total = float(np.sum((y - y_mean) ** 2))

    # Build design blocks: main effects + optional 2-way interactions
    blocks: List[tuple[str, np.ndarray]] = []
    for f_i, fname in enumerate(factor_names):
        blocks.append((fname, factor_mats[f_i]))

    if include_interactions and len(factor_indices) >= 2:
        for i, j in itertools.combinations(range(len(factor_indices)), 2):
            m1, m2 = factor_mats[i], factor_mats[j]
            cols_int = [m1[:, a] * m2[:, b] for a in range(m1.shape[1]) for b in range(m2.shape[1])]
            blocks.append((f"{factor_names[i]}*{factor_names[j]}", np.column_stack(cols_int)))

    X_curr = np.ones((n, 1), dtype=float)
    prev_ss_reg = 0.0
    rows_table = []
    for term_name, block_mat in blocks:
        X_next = np.hstack([X_curr, block_mat])
        beta, *_ = np.linalg.lstsq(X_next, y, rcond=None)
        ss_reg = float(np.sum((X_next @ beta - y_mean) ** 2))
        ss_term = max(0.0, ss_reg - prev_ss_reg)
        df_term = block_mat.shape[1]
        ms_term = ss_term / df_term if df_term > 0 else 0.0
        rows_table.append({
            "source": term_name,
            "df": int(df_term),
            "ss": ss_term,
            "ms": ms_term,
        })
        X_curr = X_next
        prev_ss_reg = ss_reg

    df_model = sum(r["df"] for r in rows_table)
    ss_error = max(0.0, ss_total - prev_ss_reg)
    df_error = n - 1 - df_model
    if df_error <= 0:
        raise ValueError("No residual error degrees of freedom remain (add replicates or omit interactions).")
    ms_error = ss_error / df_error

    for r in rows_table:
        f_val = r["ms"] / ms_error if ms_error > 0 else 0.0
        p_val = float(1.0 - stats.f.cdf(f_val, r["df"], df_error)) if f_val > 0 else 1.0
        r["f_value"] = float(f_val)
        r["p_value"] = p_val

    s_val = math.sqrt(ms_error)
    r_sq = (ss_total - ss_error) / ss_total if ss_total > 0 else 0.0
    r_sq_adj = 1.0 - (ms_error / (ss_total / (n - 1))) if ss_total > 0 and n > 1 else 0.0

    return {
        "analysis": "balanced_anova",
        "response": worksheet.columns[response_index].name,
        "factors": factor_names,
        "n": int(n),
        "rows": rows_table,
        "error": {"df": int(df_error), "ss": ss_error, "ms": ms_error},
        "total": {"df": int(n - 1), "ss": ss_total},
        "s": s_val,
        "r_sq": float(r_sq),
        "r_sq_adj": float(max(0.0, r_sq_adj)),
    }


def fully_nested_anova(
    worksheet,
    response_index: int,
    factor_indices: Sequence[int],
) -> Dict[str, Any]:
    """Fit hierarchical Fully Nested ANOVA (A -> B(A) -> C(A, B)) with Variance Components."""
    if len(factor_indices) < 2 or len(factor_indices) > 5:
        raise ValueError("Fully Nested ANOVA requires 2 to 5 hierarchical factor levels.")
    if response_index in factor_indices:
        raise ValueError("Response column cannot be a nested factor.")

    Y_mat, factor_rows = _extract_complete_rows(worksheet, [response_index], factor_indices)
    n = len(Y_mat)
    if n < len(factor_indices) + 2:
        raise ValueError("Insufficient observations for nested hierarchy.")

    y = Y_mat[:, 0]
    y_mean = float(np.mean(y))
    ss_total = float(np.sum((y - y_mean) ** 2))
    factor_names = [worksheet.columns[i].name for i in factor_indices]

    # Cumulative hierarchical group keys: lvl 0 -> (A,), lvl 1 -> (A, B), ...
    cum_ss = []
    cum_k = []
    for depth in range(len(factor_indices)):
        groups: Dict[tuple, List[float]] = {}
        for r_i, row in enumerate(factor_rows):
            key = tuple(row[:depth + 1])
            groups.setdefault(key, []).append(float(y[r_i]))
        ss_between = sum(len(vals) * ((sum(vals) / len(vals)) - y_mean) ** 2 for vals in groups.values())
        cum_ss.append(float(ss_between))
        cum_k.append(len(groups))

    # Sequential difference gives nested SS at each depth
    rows_table = []
    prev_ss = 0.0
    prev_k = 1
    for depth, fname in enumerate(factor_names):
        src_name = fname if depth == 0 else f"{fname}({', '.join(factor_names[:depth])})"
        ss_lvl = max(0.0, cum_ss[depth] - prev_ss)
        df_lvl = cum_k[depth] - prev_k
        if df_lvl <= 0:
            raise ValueError(f"Nested level '{src_name}' has zero degrees of freedom (no sub-levels within parent).")
        ms_lvl = ss_lvl / df_lvl
        # Effective replicate size n_0 per node at this depth
        avg_group_size = n / cum_k[depth]
        rows_table.append({
            "source": src_name,
            "df": int(df_lvl),
            "ss": ss_lvl,
            "ms": ms_lvl,
            "n_per_node": avg_group_size,
        })
        prev_ss = cum_ss[depth]
        prev_k = cum_k[depth]

    ss_error = max(0.0, ss_total - prev_ss)
    df_error = n - prev_k
    if df_error <= 0:
        raise ValueError("No residual degrees of freedom at the lowest nested level.")
    ms_error = ss_error / df_error

    # Compute F-tests against immediate child nested level, and sequential variance components
    var_comps = [0.0] * len(rows_table)
    for idx in range(len(rows_table) - 1, -1, -1):
        child_ms = rows_table[idx + 1]["ms"] if idx + 1 < len(rows_table) else ms_error
        child_df = rows_table[idx + 1]["df"] if idx + 1 < len(rows_table) else df_error
        f_val = rows_table[idx]["ms"] / child_ms if child_ms > 0 else 0.0
        p_val = float(1.0 - stats.f.cdf(f_val, rows_table[idx]["df"], child_df)) if f_val > 0 else 1.0
        rows_table[idx]["f_value"] = float(f_val)
        rows_table[idx]["p_value"] = p_val
        vc = max(0.0, (rows_table[idx]["ms"] - child_ms) / max(rows_table[idx]["n_per_node"], 1.0))
        var_comps[idx] = vc
        rows_table[idx]["var_comp"] = float(vc)

    total_var = sum(var_comps) + ms_error
    for row in rows_table:
        row["pct_total"] = 100.0 * row["var_comp"] / total_var if total_var > 0 else 0.0

    return {
        "analysis": "fully_nested_anova",
        "response": worksheet.columns[response_index].name,
        "factors": factor_names,
        "n": int(n),
        "rows": rows_table,
        "error": {"df": int(df_error), "ss": ss_error, "ms": ms_error, "var_comp": ms_error, "pct_total": 100.0 * ms_error / total_var if total_var > 0 else 0.0},
        "total": {"df": int(n - 1), "ss": ss_total, "var_comp": total_var},
    }


def oneway_manova(
    worksheet,
    response_indices: Sequence[int],
    factor_index: int,
) -> Dict[str, Any]:
    """Perform One-Way MANOVA computing Wilks', Lawley-Hotelling, Pillai's, and Roy's criteria."""
    if len(response_indices) < 2:
        raise ValueError("MANOVA requires at least 2 continuous response variables.")
    if factor_index in response_indices:
        raise ValueError("Factor column must be separate from response columns.")

    Y_mat, factor_rows = _extract_complete_rows(worksheet, response_indices, [factor_index])
    n, p = Y_mat.shape
    fac_labels = [row[0] for row in factor_rows]
    groups = sorted(set(fac_labels))
    g = len(groups)
    if g < 2 or n - g <= p:
        raise ValueError("Insufficient groups or residual degrees of freedom for MANOVA.")

    grand_mean = np.mean(Y_mat, axis=0)
    H = np.zeros((p, p), dtype=float)
    E = np.zeros((p, p), dtype=float)
    for lvl in groups:
        mask = np.array([lbl == lvl for lbl in fac_labels])
        Y_g = Y_mat[mask]
        nk = len(Y_g)
        mean_g = np.mean(Y_g, axis=0)
        diff_g = mean_g - grand_mean
        H += nk * np.outer(diff_g, diff_g)
        centered = Y_g - mean_g
        E += centered.T @ centered

    try:
        E_inv_H = np.linalg.solve(E, H)
    except np.linalg.LinAlgError:
        E_inv_H = np.linalg.pinv(E) @ H

    eigvals = np.real(np.linalg.eigvals(E_inv_H))
    eigvals = np.maximum(eigvals, 0.0)
    s = min(p, g - 1)
    top_eigs = np.sort(eigvals)[::-1][:s]

    # 1. Wilks' Lambda
    wilks_lam = float(np.prod(1.0 / (1.0 + top_eigs)))
    # 2. Lawley-Hotelling Trace
    lh_trace = float(np.sum(top_eigs))
    # 3. Pillai's Trace
    pillai_trace = float(np.sum(top_eigs / (1.0 + top_eigs)))
    # 4. Roy's Largest Root
    roy_root = float(top_eigs[0])

    # Rao's F approximation for Wilks' Lambda
    df_h = g - 1
    df_e = n - g
    m_abs = abs(p - df_h)
    r_rao = df_e - (p - df_h + 1) / 2.0
    u_rao = (p * df_h - 2) / 4.0
    denom = p ** 2 + df_h ** 2 - 5
    t_rao = math.sqrt((p ** 2 * df_h ** 2 - 4) / denom) if denom > 0 else 1.0
    df1_w = p * df_h
    df2_w = max(1.0, r_rao * t_rao - 2.0 * u_rao)
    lam_t = wilks_lam ** (1.0 / t_rao)
    f_wilks = ((1.0 - lam_t) / max(lam_t, 1e-15)) * (df2_w / max(df1_w, 1.0))
    p_wilks = float(1.0 - stats.f.cdf(f_wilks, df1_w, df2_w))

    # Pillai's F approximation
    df1_p = s * (max(p, df_h) + 0)
    df1_p = p * df_h
    df2_p = s * (df_e - p + s)
    f_pillai = ((2.0 * ((df_e - p - 1) / 2.0) + s + 1) / max(2.0 * (abs(p - df_h) - 1) / 2.0 + s + 1, 1.0))
    n_p = 0.5 * (df_e - p - 1)
    m_p = 0.5 * (m_abs - 1)
    f_pillai = ((2.0 * n_p + s + 1.0) / max(2.0 * m_p + s + 1.0, 1.0)) * (pillai_trace / max(s - pillai_trace, 1e-12))
    df1_pillai = s * (2.0 * m_p + s + 1.0)
    df2_pillai = s * (2.0 * n_p + s + 1.0)
    p_pillai = float(1.0 - stats.f.cdf(max(0.0, f_pillai), max(1.0, df1_pillai), max(1.0, df2_pillai)))

    # Lawley-Hotelling F approx
    df1_lh = p * df_h
    b_lh = (df_e + df_h - df_h - p - 1) * (df_e - 1) / max((df_e - p - 3) * (df_e - p), 1.0)
    df2_lh = max(1.0, 4.0 + (p * df_h + 2.0) / max(b_lh - 1.0, 1e-9)) if df_e > p + 3 else max(1.0, df_e - p)
    f_lh = (lh_trace / max(s, 1)) * (df2_lh / max(df1_lh, 1.0))
    p_lh = float(1.0 - stats.f.cdf(max(0.0, f_lh), df1_lh, df2_lh))

    # Roy's Largest Root upper bound F
    r_roy = max(p, df_h)
    df2_roy = max(1, df_e - r_roy + df_h)
    f_roy = roy_root * (df2_roy / max(r_roy, 1))
    p_roy = float(1.0 - stats.f.cdf(max(0.0, f_roy), r_roy, df2_roy))

    criteria = [
        {"criterion": "Wilks'", "stat": wilks_lam, "f": float(f_wilks), "num_df": int(round(df1_w)), "den_df": int(round(df2_w)), "p_value": p_wilks},
        {"criterion": "Lawley-Hotelling", "stat": lh_trace, "f": float(f_lh), "num_df": int(round(df1_lh)), "den_df": int(round(df2_lh)), "p_value": p_lh},
        {"criterion": "Pillai's", "stat": pillai_trace, "f": float(f_pillai), "num_df": int(round(df1_pillai)), "den_df": int(round(df2_pillai)), "p_value": p_pillai},
        {"criterion": "Roy's", "stat": roy_root, "f": float(f_roy), "num_df": int(r_roy), "den_df": int(df2_roy), "p_value": p_roy},
    ]

    return {
        "analysis": "oneway_manova",
        "responses": [worksheet.columns[i].name for i in response_indices],
        "factor": worksheet.columns[factor_index].name,
        "groups": groups,
        "n": int(n),
        "criteria": criteria,
    }


def format_advanced_anova_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    lines = []
    if kind == "balanced_anova":
        lines.extend([
            f"Balanced ANOVA: {result['response']} versus {', '.join(result['factors'])}",
            f"  N = {result['n']}   |   S = {result['s']:.5g}   |   R-sq = {result['r_sq']*100:.2f}%   |   R-sq(adj) = {result['r_sq_adj']*100:.2f}%",
            "",
            "  Source               DF       Seq SS       Adj MS     F-Value   P-Value",
            "  " + "-" * 72,
        ])
        for r in result["rows"]:
            lines.append(f"  {r['source']:<18}  {r['df']:>3d}  {r['ss']:>11.4f}  {r['ms']:>11.4f}  {r['f_value']:>10.3f}  {r['p_value']:>8.4f}")
        err = result["error"]
        tot = result["total"]
        lines.append(f"  {'Error':<18}  {err['df']:>3d}  {err['ss']:>11.4f}  {err['ms']:>11.4f}")
        lines.append(f"  {'Total':<18}  {tot['df']:>3d}  {tot['ss']:>11.4f}")
    elif kind == "fully_nested_anova":
        lines.extend([
            f"Fully Nested ANOVA: {result['response']} versus {', '.join(result['factors'])}",
            "",
            "  Source                DF       SS         MS     F-Value   P-Value   VarComp   % Total",
            "  " + "-" * 84,
        ])
        for r in result["rows"]:
            lines.append(f"  {r['source']:<20} {r['df']:>3d} {r['ss']:>9.4f}  {r['ms']:>9.4f}  {r['f_value']:>9.3f}  {r['p_value']:>8.4f}  {r['var_comp']:>8.4f}  {r['pct_total']:>7.2f}%")
        err = result["error"]
        tot = result["total"]
        lines.append(f"  {'Error':<20} {err['df']:>3d} {err['ss']:>9.4f}  {err['ms']:>9.4f}  {'':>9}  {'':>8}  {err['var_comp']:>8.4f}  {err['pct_total']:>7.2f}%")
        lines.append(f"  {'Total':<20} {tot['df']:>3d} {tot['ss']:>9.4f}  {'':>9}  {'':>9}  {'':>8}  {tot['var_comp']:>8.4f}   100.00%")
    elif kind == "oneway_manova":
        lines.extend([
            f"MANOVA Tests for {result['factor']} (Responses: {', '.join(result['responses'])})",
            f"  N = {result['n']}   |   Groups = {len(result['groups'])}",
            "",
            "  Criterion         Test Stat      F-Value   Num DF   Den DF   P-Value",
            "  " + "-" * 68,
        ])
        for c in result["criteria"]:
            lines.append(f"  {c['criterion']:<16}  {c['stat']:>9.5f}  {c['f']:>11.3f}  {c['num_df']:>7d}  {c['den_df']:>7d}  {c['p_value']:>8.4f}")
    return "\n".join(lines)
