"""Readable model predictions for desktop, text, print and Office output.

Intervals are supplied by the prediction engine. Reports do not calculate bounds
or turn undefined bounds into apparent infinite intervals.
"""

import math
import textwrap


def _options(result):
    return dict(confidence=.95, intervals='both', side='two_sided',
                show_equation=True, show_table=True) | result.get('options', {})


def _display(value):
    if value is None:
        return '*'
    if isinstance(value, float):
        if math.isnan(value):
            return '*'
        if math.isinf(value):
            return '-Infinity' if value < 0 else 'Infinity'
        return format(value, '.7g')
    return str(value)


def _equation_lines(response, coefficients):
    """Wrap an equation for narrow report panes while retaining every term."""
    pieces = [str(response) + ' =']
    for index, term in enumerate(coefficients):
        value = term.get('estimate')
        negative = isinstance(value, (int, float)) and value < 0
        magnitude = _display(-value if negative else value)
        name = str(term.get('name', ''))
        constant = name.casefold() in ('constant', 'intercept', '(intercept)')
        signed = ('- ' if negative else '+ ' if index else '') + magnitude
        pieces.append(signed + ('' if constant else ' ' + name))
    return textwrap.wrap(' '.join(pieces), width=78, subsequent_indent='    ',
                         break_long_words=True, break_on_hyphens=False)


def sections(result):
    """Return (title, headers, rows) tuples containing scalar display cells."""
    o = _options(result)
    side = o['side']
    level = format(100 * o['confidence'], '.7g') + '%'
    intervals = o['intervals']
    bounds = {'two_sided': 'Two-sided', 'lower': 'Lower bound',
              'upper': 'Upper bound'}[side]
    method = [
        ['Source model', result.get('model_title', result.get('title', result.get('model_action', '')))],
        ['Response', result.get('response_name', '')],
        ['Model data', 'Refit the source model using the current worksheet data'],
        ['Confidence level', level], ['Bounds', bounds],
        ['Intervals', {'both': 'Confidence and prediction', 'confidence': 'Confidence',
                       'prediction': 'Prediction', 'none': 'None'}[intervals]],
        ['Usable prediction rows', result.get('used')],
        ['Prediction rows with missing settings', result.get('missing')],
        ['Error degrees of freedom', result.get('df_error')],
        ['Residual standard deviation', result.get('residual_stdev')],
    ]
    tables = [('Method', ['Setting', 'Value'], method)]
    coefficients = result.get('coefficients') or result.get('equation_terms') or []
    if o['show_equation'] and coefficients:
        method.append(['Coefficient scale', 'Source model coding and standardization'])
        tables.append(('Regression Equation', ['Equation (source model scale)'], [
            [line] for line in _equation_lines(result.get('response_name', 'Response'), coefficients)]))
        tables.append(('Coefficients', ['Term', 'Coef'], [
            [term.get('name', ''), term.get('estimate')] for term in coefficients]))
    if not o['show_table']:
        return [table for table in tables if table[0] != 'Method'] + [tables[0]]
    names = result.get('predictor_names', [])
    rows = result.get('rows', [])
    tables.append(('New Predictor Values', ['Row'] + list(names), [
        [row['row']] + list(row.get('inputs', []))[:len(names)]
        + [None] * max(0, len(names) - len(row.get('inputs', []))) for row in rows]))
    headers = ['Row', 'Fit', 'SE Fit']
    bound_keys = []
    for kind, short in [('confidence', 'CI'), ('prediction', 'PI')]:
        if intervals not in ('both', kind):
            continue
        prefix = 'ci' if kind == 'confidence' else 'pi'
        if side in ('two_sided', 'lower'):
            headers.append(level + ' ' + short + ' Lower')
            bound_keys.append(prefix + '_low')
        if side in ('two_sided', 'upper'):
            headers.append(level + ' ' + short + ' Upper')
            bound_keys.append(prefix + '_high')
    headers += ['X', 'Status']
    tables.append(('Predictions', headers, [
        [row['row'], row.get('fit'), row.get('se_fit')]
        + [row.get(key) for key in bound_keys]
        + ['X' if row.get('extrapolated') else '',
           {'missing': 'Missing predictor settings', 'exact_fit': 'Exact fit; uncertainty undefined',
            'ok': '', 'estimated': ''}.get(row.get('status', ''), row.get('status', ''))]
        for row in rows]))
    # Keep the answer visible in the short desktop output pane. Supporting
    # settings belong after the prediction, predictor values and equation.
    order = {'Predictions': 0, 'New Predictor Values': 1,
             'Regression Equation': 2, 'Coefficients': 3, 'Method': 4}
    return sorted(tables, key=lambda table: order[table[0]])


def text_report(result):
    lines = []
    for title, headers, rows in sections(result):
        data = [[_display(value) for value in row] for row in rows]
        widths = [max(len(header), max((len(row[i]) for row in data), default=0))
                  for i, header in enumerate(headers)]
        lines += [title, '  '.join(h.ljust(w) for h, w in zip(headers, widths))]
        lines += ['  '.join(v.ljust(w) for v, w in zip(row, widths)) for row in data]
        lines.append('')
    if _options(result)['show_table']:
        lines.append('*: missing or undefined value. X: prediction outside the observed predictor ranges; extrapolation may be unreliable.')
    if result.get('methodnotes'):
        lines.append(result['methodnotes'])
    lines.extend(str(warning) for warning in result.get('warnings', []))
    return '\n'.join(lines)
