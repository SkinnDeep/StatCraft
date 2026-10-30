"""Tables and Chi-Square statistical engine for StatCraft.

Provides 1:1 statistical parity with StatCraft for:
- Cross Tabulation and Chi-Square (two-way and multi-way)
- Chi-Square Goodness-of-Fit Test (One Variable)
- Chi-Square Test for Association (Two-Way Table in Worksheet)
- Tally Individual Variables

Computes observed counts, expected counts, row/column/total percents,
Pearson Chi-Square, Likelihood Ratio Chi-Square, standardized and adjusted residuals.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


# ==============================================================================
# 1. CROSS TABULATION AND CHI-SQUARE
# ==============================================================================

def cross_tabulation(
    row_data: List[Any],
    col_data: List[Any],
    row_name: str = "Row",
    col_name: str = "Col",
    freq_data: Optional[List[Any]] = None,
    include_expected: bool = True,
    include_row_percents: bool = True,
    include_col_percents: bool = True,
    include_total_percents: bool = False,
    include_chi_square: bool = True,
) -> Dict[str, Any]:
    """Perform Cross Tabulation and Chi-Square Test matching StatCraft."""
    n_raw = min(len(row_data), len(col_data))
    if freq_data is not None:
        n_raw = min(n_raw, len(freq_data))

    rows_clean = []
    cols_clean = []
    weights = []

    for i in range(n_raw):
        r_val = _clean_str(row_data[i])
        c_val = _clean_str(col_data[i])
        if not r_val or not c_val:
            continue
        w = 1.0
        if freq_data is not None:
            f_val = freq_data[i]
            if f_val is None or f_val == "" or isinstance(f_val, bool):
                continue
            try:
                w = float(f_val)
                if w <= 0 or not math.isfinite(w):
                    continue
            except (ValueError, TypeError):
                continue
        rows_clean.append(r_val)
        cols_clean.append(c_val)
        weights.append(w)

    if not rows_clean:
        raise ValueError("Cross Tabulation requires at least one valid observation.")

    # Unique sorted categories
    row_labels = sorted(list(set(rows_clean)))
    col_labels = sorted(list(set(cols_clean)))
    r_dim = len(row_labels)
    c_dim = len(col_labels)

    r_map = {lbl: i for i, lbl in enumerate(row_labels)}
    c_map = {lbl: j for j, lbl in enumerate(col_labels)}

    # Contingency Table of Observed Counts
    observed = np.zeros((r_dim, c_dim), dtype=np.float64)
    for r_val, c_val, w in zip(rows_clean, cols_clean, weights):
        observed[r_map[r_val], c_map[c_val]] += w

    row_totals = observed.sum(axis=1)
    col_totals = observed.sum(axis=0)
    grand_total = float(observed.sum())

    if grand_total == 0:
        raise ValueError("Total frequency count must be greater than zero.")

    # Expected cell counts: E_ij = (R_i * C_j) / N
    expected = np.outer(row_totals, col_totals) / grand_total

    # Percents
    row_percents = np.zeros_like(observed)
    for i in range(r_dim):
        if row_totals[i] > 0:
            row_percents[i, :] = (observed[i, :] / row_totals[i]) * 100.0

    col_percents = np.zeros_like(observed)
    for j in range(c_dim):
        if col_totals[j] > 0:
            col_percents[:, j] = (observed[:, j] / col_totals[j]) * 100.0

    total_percents = (observed / grand_total) * 100.0

    # Chi-Square Tests
    pearson_chi = 0.0
    lr_chi = 0.0
    cell_contributions = np.zeros_like(observed)
    standardized_res = np.zeros_like(observed)
    adjusted_res = np.zeros_like(observed)
    cells_expected_less_than_5 = 0

    for i in range(r_dim):
        for j in range(c_dim):
            e = expected[i, j]
            o = observed[i, j]
            if e < 5.0:
                cells_expected_less_than_5 += 1
            if e > 0:
                contrib = ((o - e) ** 2) / e
                cell_contributions[i, j] = contrib
                pearson_chi += contrib
                if o > 0:
                    lr_chi += 2.0 * o * math.log(o / e)
                std_r = (o - e) / math.sqrt(e)
                standardized_res[i, j] = std_r
                # Adjusted residual: (O - E) / sqrt(E * (1 - r_i/N) * (1 - c_j/N))
                denom = math.sqrt(e * (1.0 - row_totals[i] / grand_total) * (1.0 - col_totals[j] / grand_total))
                if denom > 0:
                    adjusted_res[i, j] = (o - e) / denom

    df = (r_dim - 1) * (c_dim - 1)
    pearson_p = float(1.0 - stats.chi2.cdf(pearson_chi, df)) if df > 0 else 1.0
    lr_p = float(1.0 - stats.chi2.cdf(lr_chi, df)) if df > 0 else 1.0

    total_cells = r_dim * c_dim
    pct_less_than_5 = (cells_expected_less_than_5 / total_cells) * 100.0 if total_cells > 0 else 0.0

    return {
        "analysis": "cross_tabulation",
        "row_name": row_name,
        "col_name": col_name,
        "row_labels": row_labels,
        "col_labels": col_labels,
        "observed": observed.tolist(),
        "expected": expected.tolist(),
        "row_totals": row_totals.tolist(),
        "col_totals": col_totals.tolist(),
        "grand_total": grand_total,
        "row_percents": row_percents.tolist(),
        "col_percents": col_percents.tolist(),
        "total_percents": total_percents.tolist(),
        "cell_contributions": cell_contributions.tolist(),
        "standardized_residuals": standardized_res.tolist(),
        "adjusted_residuals": adjusted_res.tolist(),
        "df": df,
        "pearson_chi_square": float(pearson_chi),
        "pearson_p_value": pearson_p,
        "likelihood_ratio_chi_square": float(lr_chi),
        "likelihood_ratio_p_value": lr_p,
        "cells_expected_less_than_5": cells_expected_less_than_5,
        "pct_cells_expected_less_than_5": pct_less_than_5,
        "include_expected": include_expected,
        "include_row_percents": include_row_percents,
        "include_col_percents": include_col_percents,
        "include_total_percents": include_total_percents,
        "include_chi_square": include_chi_square,
    }


# ==============================================================================
# 2. CHI-SQUARE GOODNESS-OF-FIT TEST (ONE VARIABLE)
# ==============================================================================

def chi_square_goodness_of_fit(
    data: List[Any],
    var_name: str = "Category",
    freq_data: Optional[List[Any]] = None,
    test_proportions: Optional[Dict[str, float]] = None,  # category -> proportion
) -> Dict[str, Any]:
    """Perform Chi-Square Goodness-of-Fit Test for categorical variable matching StatCraft."""
    n_raw = len(data)
    if freq_data is not None:
        n_raw = min(n_raw, len(freq_data))

    cleaned_cats = []
    weights = []
    for i in range(n_raw):
        c_val = _clean_str(data[i])
        if not c_val:
            continue
        w = 1.0
        if freq_data is not None:
            f_val = freq_data[i]
            if f_val is None or f_val == "" or isinstance(f_val, bool):
                continue
            try:
                w = float(f_val)
                if w <= 0 or not math.isfinite(w):
                    continue
            except (ValueError, TypeError):
                continue
        cleaned_cats.append(c_val)
        weights.append(w)

    if not cleaned_cats:
        raise ValueError("Chi-Square Goodness-of-Fit requires at least one complete observation.")

    labels = sorted(list(set(cleaned_cats)))
    k = len(labels)
    if k < 2:
        raise ValueError("Goodness-of-fit test requires at least 2 distinct categories.")

    obs_map = {lbl: 0.0 for lbl in labels}
    for c_val, w in zip(cleaned_cats, weights):
        obs_map[c_val] += w

    n_total = sum(obs_map.values())
    if n_total <= 0:
        raise ValueError("Total observed count must be strictly positive.")

    # Test proportions (equal proportions by default)
    if test_proportions is None:
        p_hyp = {lbl: 1.0 / k for lbl in labels}
    else:
        p_hyp = {}
        for lbl in labels:
            p_hyp[lbl] = float(test_proportions.get(lbl, 1.0 / k))
        # Normalize if not summing to 1
        p_sum = sum(p_hyp.values())
        if p_sum > 0:
            for lbl in labels:
                p_hyp[lbl] /= p_sum

    rows = []
    chi_square = 0.0
    cells_expected_less_than_5 = 0

    for lbl in labels:
        o = obs_map[lbl]
        p = p_hyp[lbl]
        e = n_total * p
        if e < 5.0:
            cells_expected_less_than_5 += 1
        contrib = ((o - e) ** 2) / e if e > 0 else 0.0
        chi_square += contrib
        rows.append({
            "category": lbl,
            "observed": o,
            "test_proportion": p,
            "expected": e,
            "contribution": contrib,
        })

    df = k - 1
    p_val = float(1.0 - stats.chi2.cdf(chi_square, df)) if df > 0 else 1.0

    return {
        "analysis": "chi_square_goodness_of_fit",
        "var_name": var_name,
        "n_obs": n_total,
        "categories": labels,
        "rows": rows,
        "chi_square": float(chi_square),
        "df": df,
        "p_value": p_val,
        "cells_expected_less_than_5": cells_expected_less_than_5,
        "pct_cells_expected_less_than_5": (cells_expected_less_than_5 / k) * 100.0,
    }


# ==============================================================================
# 3. CHI-SQUARE TEST FOR ASSOCIATION (TWO-WAY TABLE IN WORKSHEET)
# ==============================================================================

def chi_square_association_table(
    table: List[List[float]],
    row_names: Optional[List[str]] = None,
    col_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Perform Chi-Square Test for Association given two-way contingency table in columns."""
    obs = np.array(table, dtype=np.float64)
    r_dim, c_dim = obs.shape
    if r_dim < 2 or c_dim < 2:
        raise ValueError("Contingency table must have at least 2 rows and 2 columns.")
    if np.any(obs < 0):
        raise ValueError("Contingency table counts cannot be negative.")

    r_names = row_names if row_names and len(row_names) == r_dim else [f"Row {i+1}" for i in range(r_dim)]
    c_names = col_names if col_names and len(col_names) == c_dim else [f"Col {j+1}" for j in range(c_dim)]

    row_totals = obs.sum(axis=1)
    col_totals = obs.sum(axis=0)
    grand_total = float(obs.sum())

    if grand_total <= 0:
        raise ValueError("Contingency table total count must be greater than zero.")

    expected = np.outer(row_totals, col_totals) / grand_total

    pearson_chi = 0.0
    lr_chi = 0.0
    cell_contributions = np.zeros_like(obs)
    cells_expected_less_than_5 = 0

    for i in range(r_dim):
        for j in range(c_dim):
            e = expected[i, j]
            o = obs[i, j]
            if e < 5.0:
                cells_expected_less_than_5 += 1
            if e > 0:
                contrib = ((o - e) ** 2) / e
                cell_contributions[i, j] = contrib
                pearson_chi += contrib
                if o > 0:
                    lr_chi += 2.0 * o * math.log(o / e)

    df = (r_dim - 1) * (c_dim - 1)
    pearson_p = float(1.0 - stats.chi2.cdf(pearson_chi, df)) if df > 0 else 1.0
    lr_p = float(1.0 - stats.chi2.cdf(lr_chi, df)) if df > 0 else 1.0

    total_cells = r_dim * c_dim
    pct_less_than_5 = (cells_expected_less_than_5 / total_cells) * 100.0 if total_cells > 0 else 0.0

    return {
        "analysis": "chi_square_association_table",
        "row_names": r_names,
        "col_names": c_names,
        "observed": obs.tolist(),
        "expected": expected.tolist(),
        "cell_contributions": cell_contributions.tolist(),
        "row_totals": row_totals.tolist(),
        "col_totals": col_totals.tolist(),
        "grand_total": grand_total,
        "df": df,
        "pearson_chi_square": float(pearson_chi),
        "pearson_p_value": pearson_p,
        "likelihood_ratio_chi_square": float(lr_chi),
        "likelihood_ratio_p_value": lr_p,
        "cells_expected_less_than_5": cells_expected_less_than_5,
        "pct_cells_expected_less_than_5": pct_less_than_5,
    }


# ==============================================================================
# 4. TALLY INDIVIDUAL VARIABLES
# ==============================================================================

def tally_variables(
    data: List[Any],
    var_name: str = "Variable",
    include_counts: bool = True,
    include_percents: bool = True,
    include_cumulative_counts: bool = True,
    include_cumulative_percents: bool = True,
) -> Dict[str, Any]:
    """Calculate frequency counts and percents for a categorical variable matching StatCraft."""
    cleaned = []
    missing_count = 0
    for v in data:
        s = _clean_str(v)
        if s == "" or s.lower() == "nan" or s.lower() == "none":
            missing_count += 1
        else:
            cleaned.append(s)

    n_valid = len(cleaned)
    labels = sorted(list(set(cleaned)))

    counts_map = {lbl: 0 for lbl in labels}
    for s in cleaned:
        counts_map[s] += 1

    rows = []
    cum_count = 0
    for lbl in labels:
        cnt = counts_map[lbl]
        cum_count += cnt
        pct = (cnt / n_valid * 100.0) if n_valid > 0 else 0.0
        cum_pct = (cum_count / n_valid * 100.0) if n_valid > 0 else 0.0
        rows.append({
            "value": lbl,
            "count": cnt,
            "percent": pct,
            "cumulative_count": cum_count,
            "cumulative_percent": cum_pct,
        })

    return {
        "analysis": "tally_variables",
        "var_name": var_name,
        "n_valid": n_valid,
        "n_missing": missing_count,
        "rows": rows,
        "include_counts": include_counts,
        "include_percents": include_percents,
        "include_cumulative_counts": include_cumulative_counts,
        "include_cumulative_percents": include_cumulative_percents,
    }
