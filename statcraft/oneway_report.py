"""Text reports and section structures for Native One-Way ANOVA."""
from __future__ import annotations

import math
from typing import Any


def _fmt(val: Any, decimals: int = 4) -> str:
    if val is None:
        return '*'
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return '*'
        return f'{val:.{decimals}f}'
    return str(val)


def _fmt_pct(val: Any, decimals: int = 2) -> str:
    if val is None or not isinstance(val, (int, float)) or math.isnan(val):
        return '*'
    return f'{val:.{decimals}f}%'


def _format_table(headers: list[str], rows: list[list[Any]], alignments: list[str] | None = None) -> str:
    if not rows:
        return ''
    str_rows = [[_fmt(c) if isinstance(c, (int, float)) else str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    aligns = alignments or (['left'] + ['right'] * (len(headers) - 1))

    def pad(text, width, align):
        return text.ljust(width) if align == 'left' else text.rjust(width)

    lines = []
    lines.append('  '.join(pad(h, widths[i], aligns[i]) for i, h in enumerate(headers)))
    lines.append('  '.join('-' * widths[i] for i in range(len(headers))))
    for row in str_rows:
        lines.append('  '.join(pad(row[i], widths[i], aligns[i]) for i in range(len(headers))))
    return '\n'.join(lines)


def sections(result: dict[str, Any]) -> dict[str, Any]:
    opts = result.get('options', {})
    res_opts = opts.get('results', {})
    conf = opts.get('confidence', 0.95)
    conf_pct = round(conf * 100, 1)
    if conf_pct.is_integer():
        conf_pct = int(conf_pct)

    sec: dict[str, Any] = {}

    # 1. Method
    if res_opts.get('method', True):
        equal_var = opts.get('assume_equal_variances', True)
        sec['method'] = {
            'title': 'Method',
            'null_hypothesis': 'All means are equal',
            'alt_hypothesis': 'Not all means are equal',
            'alpha': round(1.0 - conf, 4),
            'equal_variances': equal_var,
        }

    # 2. Factor Information
    if res_opts.get('factor_info', True):
        fi = result['factor_info']
        sec['factor_info'] = {
            'title': 'Factor Information',
            'headers': ['Factor', 'Levels', 'Values'],
            'rows': [[fi['name'], fi['levels_count'], ', '.join(map(str, fi['values']))]],
        }

    # 3. Analysis of Variance
    if res_opts.get('anova', True):
        at = result['anova_table']
        rows = [
            [result['factor_name'], at['df_factor'], at['ss_factor'], at['ms_factor'], at['f_value'], at['p_value']],
            ['Error', at['df_error'], at['ss_error'], at['ms_error'], '', ''],
            ['Total', at['df_total'], at['ss_total'], '', '', ''],
        ]
        sec['anova'] = {
            'title': 'Analysis of Variance',
            'headers': ['Source', 'DF', 'Adj SS', 'Adj MS', 'F-Value', 'P-Value'],
            'rows': rows,
        }

    # 4. Model Summary
    if res_opts.get('model_summary', True):
        ms = result['model_summary']
        sec['model_summary'] = {
            'title': 'Model Summary',
            'headers': ['S', 'R-sq', 'R-sq(adj)', 'R-sq(pred)'],
            'rows': [[
                _fmt(ms['s'], 4),
                _fmt_pct(ms['r_sq']),
                _fmt_pct(ms['r_sq_adj']),
                _fmt_pct(ms['r_sq_pred']),
            ]],
        }

    # 5. Means
    if res_opts.get('means', True):
        means_rows = []
        for row in result['means']:
            ci_str = f"({_fmt(row['ci_low'])}, {_fmt(row['ci_high'])})"
            means_rows.append([row['level'], row['n'], _fmt(row['mean']), _fmt(row['stdev']), ci_str])
        sec['means'] = {
            'title': 'Means',
            'headers': [result['factor_name'], 'N', 'Mean', 'StDev', f'{conf_pct}% CI'],
            'rows': means_rows,
            'pooled_stdev': result.get('s_pooled') if opts.get('assume_equal_variances', True) else None,
        }

    # 6. Welch ANOVA (if unequal variances)
    if not opts.get('assume_equal_variances', True) and result.get('welch_anova'):
        wa = result['welch_anova']
        sec['welch'] = {
            'title': "Welch's Test",
            'headers': ['Source', 'DF Num', 'DF Den', 'F-Value', 'P-Value'],
            'rows': [[result['factor_name'], wa['df_num'], _fmt(wa['df_den'], 2), _fmt(wa['f'], 2), _fmt(wa['p_value'], 4)]],
        }

    # 7. Multiple Comparisons
    comp_results = result.get('comparisons', {})
    sec['comparisons'] = {}

    for comp_key, comp_title in [
        ('tukey', 'Tukey Pairwise Comparisons'),
        ('fisher', 'Fisher LSD Pairwise Comparisons'),
        ('games_howell', 'Games-Howell Pairwise Comparisons'),
    ]:
        if comp_key in comp_results:
            c_data = comp_results[comp_key]
            group_rows = [[r['level'], r['n'], _fmt(r['mean']), r['grouping']] for r in c_data['grouping']]
            test_rows = [
                [
                    t['pair_label'],
                    _fmt(t['difference']),
                    _fmt(t['se_difference']),
                    f"({_fmt(t['ci_low'])}, {_fmt(t['ci_high'])})",
                    _fmt(t['t_value'], 2),
                    _fmt(t['adjusted_p'], 4),
                ]
                for t in c_data['tests']
            ]
            sec['comparisons'][comp_key] = {
                'title': comp_title,
                'grouping_headers': [result['factor_name'], 'N', 'Mean', 'Grouping'],
                'grouping_rows': group_rows,
                'test_headers': ['Difference of Levels', 'Difference of Means', 'SE of Diff', f'{conf_pct}% CI', 'T-Value', 'Adj P-Value'],
                'test_rows': test_rows,
            }

    if 'dunnett' in comp_results:
        d_data = comp_results['dunnett']
        test_rows = [
            [
                t['pair_label'],
                _fmt(t['difference']),
                _fmt(t['se_difference']),
                f"({_fmt(t['ci_low'])}, {_fmt(t['ci_high'])})",
                _fmt(t['t_value'], 2),
                _fmt(t['adjusted_p'], 4),
            ]
            for t in d_data['tests']
        ]
        sec['comparisons']['dunnett'] = {
            'title': f"Dunnett Multiple Comparisons with Control ({d_data['control']})",
            'test_headers': ['Difference of Levels', 'Difference of Means', 'SE of Diff', f'{conf_pct}% CI', 'T-Value', 'Adj P-Value'],
            'test_rows': test_rows,
        }

    if 'hsu_mcb' in comp_results:
        h_data = comp_results['hsu_mcb']
        test_rows = [
            [
                t['level'],
                _fmt(t['difference']),
                _fmt(t['se_difference']),
                f"({_fmt(t['ci_low'])}, {_fmt(t['ci_high'])})",
            ]
            for t in h_data['tests']
        ]
        sec['comparisons']['hsu_mcb'] = {
            'title': f"Hsu's MCB ({h_data['best_mode'].title()} is Best)",
            'test_headers': [result['factor_name'], 'Difference of Means', 'SE of Diff', f'{conf_pct}% CI'],
            'test_rows': test_rows,
        }

    return sec


def text_report(result: dict[str, Any]) -> str:
    sec = sections(result)
    lines: list[str] = []

    # Title
    lines.append(f"One-way ANOVA: {result['response_name']} versus {result['factor_name']}")
    lines.append('')

    # Method
    if 'method' in sec:
        m = sec['method']
        lines.append(m['title'])
        lines.append(f"  Null hypothesis         H0: {m['null_hypothesis']}")
        lines.append(f"  Alternative hypothesis  H1: {m['alt_hypothesis']}")
        lines.append(f"  Significance level      alpha = {m['alpha']}")
        if m['equal_variances']:
            lines.append('  Equal variances were assumed for the analysis.')
        else:
            lines.append('  Equal variances were not assumed for the analysis.')
        lines.append('')

    # Factor Information
    if 'factor_info' in sec:
        fi = sec['factor_info']
        lines.append(fi['title'])
        lines.append(_format_table(fi['headers'], fi['rows']))
        lines.append('')

    # Analysis of Variance
    if 'anova' in sec:
        a = sec['anova']
        lines.append(a['title'])
        lines.append(_format_table(a['headers'], a['rows']))
        lines.append('')

    # Model Summary
    if 'model_summary' in sec:
        ms = sec['model_summary']
        lines.append(ms['title'])
        lines.append(_format_table(ms['headers'], ms['rows']))
        lines.append('')

    # Means
    if 'means' in sec:
        mn = sec['means']
        lines.append(mn['title'])
        lines.append(_format_table(mn['headers'], mn['rows']))
        if mn.get('pooled_stdev') is not None:
            lines.append(f"  Pooled StDev = {_fmt(mn['pooled_stdev'])}")
        lines.append('')

    # Welch Test
    if 'welch' in sec:
        w = sec['welch']
        lines.append(w['title'])
        lines.append(_format_table(w['headers'], w['rows']))
        lines.append('')

    # Comparisons
    comps = sec.get('comparisons', {})
    for comp_key in ('tukey', 'fisher', 'games_howell'):
        if comp_key in comps:
            c = comps[comp_key]
            lines.append(c['title'])
            lines.append('')
            lines.append(f"Grouping Information Using the {comp_key.title()} Method")
            lines.append(_format_table(c['grouping_headers'], c['grouping_rows']))
            lines.append('  Means that do not share a letter are significantly different.')
            lines.append('')
            lines.append(f"{comp_key.title()} Simultaneous Tests for Differences of Means")
            lines.append(_format_table(c['test_headers'], c['test_rows']))
            lines.append('')

    if 'dunnett' in comps:
        d = comps['dunnett']
        lines.append(d['title'])
        lines.append(_format_table(d['test_headers'], d['test_rows']))
        lines.append('')

    if 'hsu_mcb' in comps:
        h = comps['hsu_mcb']
        lines.append(h['title'])
        lines.append(_format_table(h['test_headers'], h['test_rows']))
        lines.append('')

    return '\n'.join(lines).strip()
