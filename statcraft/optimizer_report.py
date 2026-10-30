"""Structured report tables and plain-text formatting for Response Optimizer."""
import math
from .optimizer import DEFAULTS
from .prediction_report import _display


def _options(result):
    return dict(DEFAULTS) | result.get('options', {})


def _format_interval(low, high, side='two_sided'):
    if side == 'two_sided':
        if low is None or high is None:
            return '*'
        return f'({_display(low)}, {_display(high)})'
    if side == 'lower':
        return '*' if low is None else _display(low)
    return '*' if high is None else _display(high)


def sections(result):
    """Return (title, headers, rows) tuples for desktop, print and Office output."""
    r = result
    o = _options(r)
    tables = []
    if o['show_parameters']:
        rows = []
        for p in r.get('parameters', []):
            goal_label = {'minimize': 'Minimize', 'target': 'Target', 'maximize': 'Maximize'}.get(p.get('goal'), str(p.get('goal', '')))
            resp_label = str(p.get('response_name', ''))
            if p.get('is_probability') and p.get('event') is not None:
                resp_label += f" (P={p['event']})"
            rows.append([
                resp_label,
                goal_label,
                p.get('lower'),
                p.get('target'),
                p.get('upper'),
                p.get('weight'),
                p.get('importance'),
            ])
        tables.append(('Parameters', ['Response', 'Goal', 'Lower', 'Target', 'Upper', 'Weight', 'Importance'], rows))

    if o['show_variable_ranges']:
        range_rows = []
        for pred in r.get('predictors', []):
            if pred.get('constraint_mode') == 'hold':
                val_text = f"Held at {_display(pred.get('hold_value'))}"
            elif pred.get('role') == 'factor':
                val_text = ', '.join(_display(v) for v in pred.get('active_levels', pred.get('levels', [])))
            else:
                val_text = f"({_display(pred.get('lower'))}, {_display(pred.get('upper'))})"
            range_rows.append([pred.get('name', ''), val_text])
        tables.append(('Variable Ranges', ['Variable', 'Values'], range_rows))

    if o['show_starting_point'] and r.get('starting_point'):
        sp = r['starting_point']
        start_rows = [
            [pred.get('name', ''), val]
            for pred, val in zip(r.get('predictors', []), sp.get('settings', []))
        ]
        tables.append(('Starting Point', ['Variable', 'Setting'], start_rows))

    if o['show_solutions'] and r.get('solutions'):
        pred_names = list(r.get('predictor_names', []))
        resp_names = [f"{name} Fit" for name in r.get('response_names', [])]
        headers = ['Solution'] + pred_names + resp_names + ['Composite Desirability']
        sol_rows = []
        for sol in r['solutions']:
            sol_rows.append(
                [sol.get('rank')]
                + list(sol.get('settings', []))
                + list(sol.get('fits', []))
                + [sol.get('composite_desirability')]
            )
        tables.append(('Solutions', headers, sol_rows))

    if o['show_prediction'] and r.get('predictions'):
        opt_settings = [
            [pred.get('name', ''), val]
            for pred, val in zip(r.get('predictors', []), r.get('optimal_settings', []))
        ]
        tables.append(('Optimal Variable Settings', ['Variable', 'Setting'], opt_settings))
        level = format(100.0 * o['confidence'], '.7g') + '%'
        side = o['side']
        ci_header = f'{level} CI' if side == 'two_sided' else (f'{level} Lower Bound' if side == 'lower' else f'{level} Upper Bound')
        pi_header = f'{level} PI' if side == 'two_sided' else (f'{level} PI Lower' if side == 'lower' else f'{level} PI Upper')
        pred_rows = []
        for item in r['predictions']:
            resp_label = str(item.get('response_name', ''))
            if item.get('is_probability') and item.get('event') is not None:
                resp_label += f" (P={item['event']})"
            ci_str = _format_interval(item.get('ci_low'), item.get('ci_high'), side)
            pi_str = '*' if item.get('is_probability') else _format_interval(item.get('pi_low'), item.get('pi_high'), side)
            pred_rows.append([
                resp_label,
                item.get('fit'),
                item.get('se_fit'),
                ci_str,
                pi_str,
                item.get('desirability'),
            ])
        tables.append(('Multiple Response Prediction', ['Response', 'Fit', 'SE Fit', ci_header, pi_header, 'Individual Desirability'], pred_rows))

    method_rows = [
        ['Optimization method', 'Derringer-Suich composite desirability'],
        ['Models optimized', ', '.join(f"{p.get('response_name')} ({p.get('model_title')})" for p in r.get('parameters', []))],
        ['Optimal composite desirability', r.get('optimal_composite_desirability')],
        ['Confidence level', format(100.0 * o['confidence'], '.7g') + '%'],
        ['Interval type', {'two_sided': 'Two-sided', 'lower': 'Lower bound', 'upper': 'Upper bound'}[o['side']]],
    ]
    tables.append(('Method', ['Setting', 'Value'], method_rows))
    return tables


def text_report(result):
    lines = []
    for title, headers, rows in sections(result):
        data = [[_display(v) for v in row] for row in rows]
        widths = [max(len(h), max((len(row[i]) for row in data), default=0)) for i, h in enumerate(headers)]
        lines += [title, '  '.join(h.ljust(w) for h, w in zip(headers, widths))]
        lines += ['  '.join(v.ljust(w) for v, w in zip(row, widths)) for row in data]
        lines.append('')
    if result.get('methodnotes'):
        lines.append(str(result['methodnotes']))
    lines.extend(str(w) for w in result.get('warnings', []))
    return '\n'.join(lines)
