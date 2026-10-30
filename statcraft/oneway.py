"""Native One-Way ANOVA with Stacked/Unstacked data, Multiple Comparisons, and Diagnostics.

Form evidence:
- ONEWAYANOVA.MDF: Main dialog with Stacked ("Response data are in one column for all factor levels")
  vs Unstacked ("Response data are in a separate column for each factor level") modes.
- ONEWAYCOMPARISONS.MDF: Tukey, Fisher, Dunnett (with Control group), Hsu MCB (with Best), Games-Howell,
  Grouping info, Tests, Differences of means interval plot.
- ONEWAYOPTIONS.MDF: Confidence level, Interval type (Two-sided / Lower / Upper), Assume equal variances.
- ONEWAYGRAPHS.MDF: Data plots (Interval plot, Individual value plot, Boxplot),
  Residual plots (Four-in-one / Individual: Histogram, Normal plot, Versus fits, Versus order).
- ONEWAYRESULTS.MDF: Method, Factor info, Analysis of variance, Model summary, Means.
- ONEWAYSTORAGE.MDF: Fits, Residuals.
"""
from __future__ import annotations

import copy
import math
from typing import Any
import numpy as np
from scipy import stats
from scipy.stats import studentized_range

from .engine import normalize_numeric
from .model import Worksheet


def oneway_settings(options: dict | None = None) -> dict[str, Any]:
    opts = copy.deepcopy(options or {})
    res: dict[str, Any] = {
        'stacked': bool(opts.get('stacked', True)),
        'confidence': float(opts.get('confidence', 0.95)),
        'interval_type': str(opts.get('interval_type', 'two_sided')),
        'assume_equal_variances': bool(opts.get('assume_equal_variances', True)),
    }
    if not (0.01 <= res['confidence'] <= 0.999):
        raise ValueError('Confidence level must lie between 0.01 and 0.999.')
    if res['interval_type'] not in ('two_sided', 'lower', 'upper'):
        raise ValueError("Interval type must be 'two_sided', 'lower', or 'upper'.")

    comp_in = opts.get('comparisons') or {}
    err_rate = float(comp_in.get('error_rate', 0.05))
    if err_rate > 1.0:
        err_rate /= 100.0
    if not (0.001 <= err_rate <= 0.5):
        raise ValueError('Error rate for comparisons must lie between 0.001 and 0.5.')

    res['comparisons'] = {
        'error_rate': err_rate,
        'tukey': bool(comp_in.get('tukey', False)),
        'fisher': bool(comp_in.get('fisher', False)),
        'dunnett': bool(comp_in.get('dunnett', False)),
        'control_group': comp_in.get('control_group'),
        'hsu_mcb': bool(comp_in.get('hsu_mcb', False)),
        'hsu_best': str(comp_in.get('hsu_best', 'largest')),
        'games_howell': bool(comp_in.get('games_howell', False)),
        'grouping_info': bool(comp_in.get('grouping_info', True)),
        'tests': bool(comp_in.get('tests', False)),
        'interval_plot': bool(comp_in.get('interval_plot', True)),
    }
    if res['comparisons']['hsu_best'] not in ('largest', 'smallest'):
        res['comparisons']['hsu_best'] = 'largest'

    graphs_in = opts.get('graphs') or {}
    res['graphs'] = {
        'interval_plot': bool(graphs_in.get('interval_plot', True)),
        'individual_value_plot': bool(graphs_in.get('individual_value_plot', False)),
        'boxplot': bool(graphs_in.get('boxplot', False)),
        'residual_mode': str(graphs_in.get('residual_mode', 'none')),
        'res_histogram': bool(graphs_in.get('res_histogram', False)),
        'res_normal': bool(graphs_in.get('res_normal', False)),
        'res_fits': bool(graphs_in.get('res_fits', False)),
        'res_order': bool(graphs_in.get('res_order', False)),
    }
    if res['graphs']['residual_mode'] not in ('none', 'four_in_one', 'individual'):
        res['graphs']['residual_mode'] = 'none'

    results_in = opts.get('results') or {}
    res['results'] = {
        'display': str(results_in.get('display', 'simple')),
        'method': bool(results_in.get('method', True)),
        'factor_info': bool(results_in.get('factor_info', True)),
        'anova': bool(results_in.get('anova', True)),
        'model_summary': bool(results_in.get('model_summary', True)),
        'means': bool(results_in.get('means', True)),
    }

    storage_in = opts.get('storage') or {}
    res['storage'] = {
        'fits': bool(storage_in.get('fits', False)),
        'residuals': bool(storage_in.get('residuals', False)),
    }
    return res


def _dunnett_critical_value(k_trt: int, df_err: float, alpha: float, two_sided: bool = True) -> float:
    """Compute Dunnett critical value using fast vectorized Gauss-Legendre quadrature."""
    if k_trt <= 0 or df_err <= 0:
        return 2.0
    from scipy.optimize import brentq

    z_nodes, z_weights = np.polynomial.legendre.leggauss(32)
    z = z_nodes * 5.0
    w_z = z_weights * 5.0 * stats.norm.pdf(z)

    s_nodes, s_weights = np.polynomial.legendre.leggauss(32)
    s = 1.0 + s_nodes * 0.95
    w_s = s_weights * 0.95 * stats.chi.pdf(s * math.sqrt(df_err), df_err) * math.sqrt(df_err)

    s_col = s[:, None]
    z_row = z[None, :]

    def cdf_d(d: float) -> float:
        arg = math.sqrt(2.0) * d * s_col
        if two_sided:
            p_z = stats.norm.cdf(z_row + arg) - stats.norm.cdf(z_row - arg)
        else:
            p_z = stats.norm.cdf(z_row + arg)
        p_z = np.maximum(0.0, p_z) ** k_trt
        int_z = np.sum(p_z * w_z[None, :], axis=1)
        return float(np.sum(int_z * w_s))

    target = 1.0 - alpha
    try:
        return float(brentq(lambda d: cdf_d(d) - target, 0.5, 8.0, xtol=1e-4))
    except Exception:
        # Fallback to Bonferroni t-critical value
        adj_alpha = alpha / (2.0 * k_trt if two_sided else k_trt)
        return float(stats.t.ppf(1.0 - adj_alpha, df_err))


def _grouping_letters(levels: list[Any], diffs: dict[tuple[Any, Any], dict]) -> dict[Any, str]:
    """Compute StatCraft grouping letters (A, B, C...) for multiple comparisons."""
    k = len(levels)
    if k == 0:
        return {}
    if k == 1:
        return {levels[0]: 'A'}

    # Build adjacency: adjacent if NOT significantly different (i.e. interval contains 0 or p >= alpha)
    sig_pairs = set()
    for (i, j), info in diffs.items():
        if info.get('significant', False):
            sig_pairs.add((i, j))
            sig_pairs.add((j, i))

    # Find maximal cliques of levels that are all mutually non-significant
    cliques: list[set] = []

    def bron_kerbosch(r, p, x):
        if not p and not x:
            if r:
                cliques.append(set(r))
            return
        u = next(iter(p | x))
        for v in list(p):
            if (u, v) not in sig_pairs and u != v:
                continue
            # neighbors of v are all nodes NOT in sig_pairs with v
            neighbors = {w for w in levels if w != v and (v, w) not in sig_pairs}
            bron_kerbosch(r | {v}, p & neighbors, x & neighbors)
            p.remove(v)
            x.add(v)

    all_nodes = set(levels)
    bron_kerbosch(set(), all_nodes, set())

    # Sort cliques by average rank/mean of levels in them
    # Filter out subsets
    maximal_cliques = []
    for c in cliques:
        if not any(c < other for other in cliques):
            if c not in maximal_cliques:
                maximal_cliques.append(c)

    # Sort cliques by the highest-ranking (lowest index in levels) level in the clique
    maximal_cliques.sort(key=lambda clq: min(levels.index(lv) for lv in clq if lv in levels))
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    groups_out: dict[Any, list[str]] = {lv: [] for lv in levels}

    for idx, clq in enumerate(maximal_cliques):
        let = letters[idx % len(letters)]
        for lv in clq:
            groups_out[lv].append(let)

    return {lv: ' '.join(sorted(groups_out[lv])) if groups_out[lv] else 'A' for lv in levels}


def fit(
    worksheet: Worksheet,
    response_index: int,
    factor_index: int,
    options: dict | None = None,
) -> dict[str, Any]:
    """Compute One-Way ANOVA for stacked response and factor columns."""
    opts = oneway_settings(options)
    opts['stacked'] = True

    resp_col = worksheet.columns[response_index]
    factor_col = worksheet.columns[factor_index]

    resp_name = resp_col.name or f'C{response_index + 1}'
    factor_name = factor_col.name or f'C{factor_index + 1}'

    raw_pairs: list[tuple[float, Any, int]] = []
    for row_idx in range(worksheet.row_count):
        y_val = normalize_numeric(resp_col.values[row_idx] if row_idx < len(resp_col.values) else None)
        x_val = factor_col.values[row_idx] if row_idx < len(factor_col.values) else None
        if y_val is not None and x_val is not None and str(x_val).strip() != '':
            raw_pairs.append((y_val, str(x_val).strip(), row_idx))

    if not raw_pairs:
        raise ValueError('One-Way ANOVA requires nonmissing response values with factor levels.')

    # Collect factor levels in order of appearance
    level_order: list[str] = []
    level_data: dict[str, list[float]] = {}
    level_rows: dict[str, list[int]] = {}
    for y, x, r in raw_pairs:
        if x not in level_data:
            level_order.append(x)
            level_data[x] = []
            level_rows[x] = []
        level_data[x].append(y)
        level_rows[x].append(r)

    if len(level_order) < 2:
        raise ValueError('One-Way ANOVA requires at least two factor levels.')

    return _compute_oneway(
        resp_name=resp_name,
        factor_name=factor_name,
        level_order=level_order,
        level_data=level_data,
        raw_pairs=raw_pairs,
        options=opts,
        source_info={
            'stacked': True,
            'response_index': response_index,
            'factor_index': factor_index,
        },
    )


def fit_unstacked(
    worksheet: Worksheet,
    response_indices: list[int],
    options: dict | None = None,
) -> dict[str, Any]:
    """Compute One-Way ANOVA for unstacked separate response columns."""
    opts = oneway_settings(options)
    opts['stacked'] = False

    if len(response_indices) < 2:
        raise ValueError('One-Way ANOVA in unstacked mode requires at least two response columns.')

    resp_cols = [worksheet.columns[i] for i in response_indices]
    level_order: list[str] = []
    level_data: dict[str, list[float]] = {}
    level_rows: dict[str, list[int]] = {}
    raw_pairs: list[tuple[float, Any, int]] = []

    for idx, col in zip(response_indices, resp_cols):
        name = col.name or f'C{idx + 1}'
        level_order.append(name)
        level_data[name] = []
        level_rows[name] = []
        for r, v in enumerate(col.values):
            nv = normalize_numeric(v)
            if nv is not None:
                level_data[name].append(nv)
                level_rows[name].append(r)
                raw_pairs.append((nv, name, r))

    if any(len(level_data[name]) == 0 for name in level_order):
        raise ValueError('Each response column in unstacked ANOVA must contain nonmissing observations.')

    return _compute_oneway(
        resp_name='Responses',
        factor_name='Factor',
        level_order=level_order,
        level_data=level_data,
        raw_pairs=raw_pairs,
        options=opts,
        source_info={
            'stacked': False,
            'response_indices': list(response_indices),
        },
    )


def _compute_oneway(
    resp_name: str,
    factor_name: str,
    level_order: list[str],
    level_data: dict[str, list[float]],
    raw_pairs: list[tuple[float, Any, int]],
    options: dict,
    source_info: dict,
) -> dict[str, Any]:
    k = len(level_order)
    n_counts = [len(level_data[lv]) for lv in level_order]
    N = sum(n_counts)
    if N <= k:
        raise ValueError('One-Way ANOVA requires residual degrees of freedom (total observations > factor levels).')

    conf = options['confidence']
    alpha = 1.0 - conf
    equal_var = options['assume_equal_variances']
    interval_type = options['interval_type']

    # Group statistics
    means = [float(np.mean(level_data[lv])) for lv in level_order]
    stdevs = [float(np.std(level_data[lv], ddof=1)) if len(level_data[lv]) > 1 else 0.0 for lv in level_order]
    variances = [s ** 2 for s in stdevs]

    grand_mean = sum(n * m for n, m in zip(n_counts, means)) / N

    # Equal variances ANOVA sums of squares
    ss_factor = sum(n * (m - grand_mean) ** 2 for n, m in zip(n_counts, means))
    ss_error = sum((n - 1) * v for n, v in zip(n_counts, variances))
    ss_total = ss_factor + ss_error

    df_factor = k - 1
    df_error = N - k
    df_total = N - 1

    ms_factor = ss_factor / df_factor if df_factor > 0 else 0.0
    ms_error = ss_error / df_error if df_error > 0 else 0.0

    f_stat = ms_factor / ms_error if ms_error > 0 else float('inf')
    p_val = float(stats.f.sf(f_stat, df_factor, df_error)) if ms_error > 0 else 1.0

    s_pooled = math.sqrt(max(0.0, ms_error))
    r_sq = (ss_factor / ss_total) * 100.0 if ss_total > 0 else 0.0
    r_sq_adj = (1.0 - (ms_error / (ss_total / df_total))) * 100.0 if ss_total > 0 and df_total > 0 else 0.0

    # PRESS and R-sq(pred)
    press = sum(
        (n / (n - 1)) ** 2 * (n - 1) * v for n, v in zip(n_counts, variances) if n > 1
    ) if all(n > 1 for n in n_counts) else 0.0
    r_sq_pred = (1.0 - (press / ss_total)) * 100.0 if ss_total > 0 and press > 0 else 0.0

    # Welch's ANOVA (when equal variances not assumed)
    welch: dict[str, Any] | None = None
    if any(v <= 0 for v in variances):
        welch = None
    else:
        w_weights = [n / v for n, v in zip(n_counts, variances)]
        sum_w = sum(w_weights)
        y_prime = sum(w * m for w, m in zip(w_weights, means)) / sum_w
        term_u = sum((1.0 - w / sum_w) ** 2 / (n - 1) for w, n in zip(w_weights, n_counts))
        numerator = sum(w * (m - y_prime) ** 2 for w, m in zip(w_weights, means)) / (k - 1)
        denom_adjust = 1.0 + (2.0 * (k - 2) / (k ** 2 - 1)) * term_u
        welch_f = numerator / denom_adjust if denom_adjust > 0 else float('nan')
        welch_df1 = k - 1
        welch_df2 = (k ** 2 - 1) / (3.0 * term_u) if term_u > 0 else float('nan')
        welch_p = float(stats.f.sf(welch_f, welch_df1, welch_df2)) if not math.isnan(welch_f) and not math.isnan(welch_df2) else float('nan')
        welch = {
            'f': welch_f,
            'df_num': welch_df1,
            'df_den': welch_df2,
            'p_value': welch_p,
        }

    # Means table confidence intervals
    means_rows = []
    t_crit_pooled = stats.t.ppf(1.0 - alpha / 2.0 if interval_type == 'two_sided' else 1.0 - alpha, df_error)
    for idx, lv in enumerate(level_order):
        n = n_counts[idx]
        m = means[idx]
        s = stdevs[idx]
        if equal_var:
            se_mean = s_pooled / math.sqrt(n)
            crit = t_crit_pooled
        else:
            se_mean = s / math.sqrt(n) if n > 0 else 0.0
            crit = stats.t.ppf(1.0 - alpha / 2.0 if interval_type == 'two_sided' else 1.0 - alpha, max(1, n - 1))

        if interval_type == 'two_sided':
            ci_low = m - crit * se_mean
            ci_high = m + crit * se_mean
        elif interval_type == 'lower':
            ci_low = m - crit * se_mean
            ci_high = None
        else:
            ci_low = None
            ci_high = m + crit * se_mean

        means_rows.append({
            'level': lv,
            'n': n,
            'mean': m,
            'stdev': s,
            'se_mean': se_mean,
            'ci_low': ci_low,
            'ci_high': ci_high,
        })

    # Fits and Residuals
    level_mean_map = {lv: m for lv, m in zip(level_order, means)}
    fits = [level_mean_map[x] for _, x, _ in raw_pairs]
    residuals = [y - f for (y, _, _), f in zip(raw_pairs, fits)]
    obs_order = [r + 1 for _, _, r in raw_pairs]

    # Multiple Comparisons
    comp_opts = options['comparisons']
    comp_err_rate = comp_opts['error_rate']
    comparisons_results: dict[str, Any] = {}

    all_pairs: list[tuple[str, str]] = []
    for i in range(k):
        for j in range(i + 1, k):
            all_pairs.append((level_order[i], level_order[j]))

    # Helper for pairwise difference tests
    def compute_pairwise(method_name: str) -> dict[str, Any]:
        tests_list = []
        diff_dict: dict[tuple[Any, Any], dict] = {}
        for l1, l2 in all_pairs:
            idx1 = level_order.index(l1)
            idx2 = level_order.index(l2)
            n1, n2 = n_counts[idx1], n_counts[idx2]
            m1, m2 = means[idx1], means[idx2]
            diff = m1 - m2

            if method_name in ('tukey', 'fisher'):
                se_diff = s_pooled * math.sqrt(1.0 / n1 + 1.0 / n2)
                t_val = diff / se_diff if se_diff > 0 else 0.0
                if method_name == 'fisher':
                    df = df_error
                    crit = stats.t.ppf(1.0 - comp_err_rate / 2.0, df)
                    adj_p = float(2.0 * stats.t.sf(abs(t_val), df))
                else:  # tukey
                    q_val = abs(diff) * math.sqrt(2.0) / se_diff if se_diff > 0 else 0.0
                    q_crit = float(studentized_range.ppf(1.0 - comp_err_rate, k, df_error))
                    crit = q_crit / math.sqrt(2.0)
                    adj_p = float(studentized_range.sf(q_val, k, df_error))
            else:  # games_howell
                s1_sq = variances[idx1]
                s2_sq = variances[idx2]
                se_diff = math.sqrt(s1_sq / n1 + s2_sq / n2)
                t_val = diff / se_diff if se_diff > 0 else 0.0
                v1 = s1_sq / n1
                v2 = s2_sq / n2
                df_gh = (v1 + v2) ** 2 / ((v1 ** 2) / (n1 - 1) + (v2 ** 2) / (n2 - 1)) if (v1 + v2) > 0 else 1.0
                q_val = abs(diff) * math.sqrt(2.0) / se_diff if se_diff > 0 else 0.0
                q_crit = float(studentized_range.ppf(1.0 - comp_err_rate, k, max(1.0, df_gh)))
                crit = q_crit / math.sqrt(2.0)
                adj_p = float(studentized_range.sf(q_val, k, max(1.0, df_gh)))

            margin = crit * se_diff
            ci_l = diff - margin
            ci_h = diff + margin
            sig = bool(ci_l > 0 or ci_h < 0)

            item = {
                'level_i': l1,
                'level_j': l2,
                'pair_label': f'{l1} - {l2}',
                'difference': diff,
                'se_difference': se_diff,
                'ci_low': ci_l,
                'ci_high': ci_h,
                't_value': t_val,
                'adjusted_p': adj_p,
                'significant': sig,
            }
            tests_list.append(item)
            diff_dict[(l1, l2)] = item
            diff_dict[(l2, l1)] = item

        # Grouping letters sorted by mean descending
        sorted_by_mean = sorted(level_order, key=lambda lv: level_mean_map[lv], reverse=True)
        groupings = _grouping_letters(sorted_by_mean, diff_dict)
        grouping_rows = [
            {'level': lv, 'n': n_counts[level_order.index(lv)], 'mean': level_mean_map[lv], 'grouping': groupings.get(lv, 'A')}
            for lv in sorted_by_mean
        ]

        return {
            'tests': tests_list,
            'grouping': grouping_rows,
            'individual_confidence': (1.0 - comp_err_rate) * 100.0,
            'simultaneous_confidence': (1.0 - comp_err_rate) * 100.0,
        }

    # 1. Tukey
    if comp_opts['tukey']:
        comparisons_results['tukey'] = compute_pairwise('tukey')

    # 2. Fisher
    if comp_opts['fisher']:
        comparisons_results['fisher'] = compute_pairwise('fisher')

    # 3. Dunnett
    if comp_opts['dunnett']:
        ctrl = comp_opts.get('control_group')
        if ctrl is None or ctrl not in level_order:
            ctrl = level_order[0]
        ctrl_idx = level_order.index(ctrl)
        n_ctrl = n_counts[ctrl_idx]
        m_ctrl = means[ctrl_idx]

        d_crit = _dunnett_critical_value(k - 1, df_error, comp_err_rate, two_sided=True)
        dunnett_tests = []
        for idx, lv in enumerate(level_order):
            if lv == ctrl:
                continue
            n_t = n_counts[idx]
            m_t = means[idx]
            diff = m_t - m_ctrl
            se_diff = s_pooled * math.sqrt(1.0 / n_t + 1.0 / n_ctrl)
            t_val = diff / se_diff if se_diff > 0 else 0.0
            margin = d_crit * se_diff
            ci_l = diff - margin
            ci_h = diff + margin
            dunnett_tests.append({
                'level_i': lv,
                'level_j': str(ctrl),
                'pair_label': f'{lv} - {ctrl}',
                'difference': diff,
                'se_difference': se_diff,
                'ci_low': ci_l,
                'ci_high': ci_h,
                't_value': t_val,
                'adjusted_p': float(min(1.0, (k - 1) * 2.0 * stats.t.sf(abs(t_val), df_error))),
                'significant': bool(ci_l > 0 or ci_h < 0),
            })
        comparisons_results['dunnett'] = {
            'control': str(ctrl),
            'tests': dunnett_tests,
            'd_crit': d_crit,
        }

    # 4. Hsu's MCB
    if comp_opts['hsu_mcb']:
        d_crit = _dunnett_critical_value(k - 1, df_error, comp_err_rate, two_sided=False)
        best_mode = comp_opts['hsu_best']
        hsu_tests = []
        for i, lv in enumerate(level_order):
            m_i = means[i]
            n_i = n_counts[i]
            other_means = [means[j] for j in range(k) if j != i]
            other_indices = [j for j in range(k) if j != i]
            if best_mode == 'largest':
                best_idx = other_indices[int(np.argmax(other_means))]
                diff = m_i - means[best_idx]
            else:
                best_idx = other_indices[int(np.argmin(other_means))]
                diff = m_i - means[best_idx]

            se_diff = s_pooled * math.sqrt(1.0 / n_i + 1.0 / n_counts[best_idx])
            margin = d_crit * se_diff

            if best_mode == 'largest':
                ci_l = min(0.0, diff - margin)
                ci_h = max(0.0, diff + margin)
            else:
                ci_l = min(0.0, diff - margin)
                ci_h = max(0.0, diff + margin)

            hsu_tests.append({
                'level': lv,
                'difference': diff,
                'se_difference': se_diff,
                'ci_low': ci_l,
                'ci_high': ci_h,
            })
        comparisons_results['hsu_mcb'] = {
            'best_mode': best_mode,
            'tests': hsu_tests,
        }

    # 5. Games-Howell
    if comp_opts['games_howell']:
        comparisons_results['games_howell'] = compute_pairwise('games_howell')

    result: dict[str, Any] = {
        'analysis': 'oneway_anova',
        'response_name': resp_name,
        'factor_name': factor_name,
        'options': options,
        'source_info': source_info,
        'factor_info': {
            'name': factor_name,
            'levels_count': k,
            'values': level_order,
        },
        'anova_table': {
            'ss_factor': ss_factor,
            'df_factor': df_factor,
            'ms_factor': ms_factor,
            'f_value': f_stat,
            'p_value': p_val,
            'ss_error': ss_error,
            'df_error': df_error,
            'ms_error': ms_error,
            'ss_total': ss_total,
            'df_total': df_total,
        },
        'model_summary': {
            's': s_pooled,
            'r_sq': r_sq,
            'r_sq_adj': r_sq_adj,
            'r_sq_pred': r_sq_pred,
        },
        'means': means_rows,
        'grand_mean': grand_mean,
        's_pooled': s_pooled,
        'welch_anova': welch,
        'comparisons': comparisons_results,
        'fits': fits,
        'residuals': residuals,
        'observation_order': obs_order,
        'raw_pairs': raw_pairs,
    }
    return result
