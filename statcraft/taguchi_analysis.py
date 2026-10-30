"""Original static Taguchi row-response summaries and optional fixed main effects.

Noise/trial responses occupy separate columns of the same worksheet row. Rows
are omitted jointly across selected factors and responses. Repeated worksheet
rows are not silently pooled; dynamic Taguchi designs are outside this scope.
"""
import copy
import math
from scipy.special import logsumexp
from .model import Column, Worksheet
from .value_order import ordered_values


SOURCES = [
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/',
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/how-to-calculate-the-signal-to-noise-ratios-and-the-standard-deviations/',
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/what-is-the-signal-to-noise-ratio/',
]
DEFAULTS = {'sn_type': 'larger', 'nominal_formula': 'classic', 'log_stdev': False,
            'show_graphs': True, 'fit_models': True, 'confidence': .95}


def settings(options=None):
    if options is not None and (not isinstance(options, dict) or set(options) - set(DEFAULTS)):
        raise ValueError('Unsupported static Taguchi options.')
    result = dict(DEFAULTS, **(options or {}))
    if result['sn_type'] not in ('larger', 'smaller', 'nominal'):
        raise ValueError('Choose larger, smaller or nominal signal-to-noise ratio.')
    if result['nominal_formula'] != 'classic':
        raise ValueError('Only the classic nominal formula 10*log10(mean^2/sample_SD^2) is implemented.')
    for name in ('log_stdev', 'show_graphs', 'fit_models'):
        if type(result[name]) is not bool:
            raise ValueError(name + ' must be true or false.')
    confidence = result['confidence']
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError('Model confidence must be strictly between zero and one.')
    return result


def _selectors(worksheet, values, minimum, maximum, role, kinds):
    if not isinstance(values, (list, tuple)) or not minimum <= len(values) <= maximum:
        raise ValueError(f'Select {minimum} to {maximum} {role} columns.')
    if any(type(index) is not int or not 0 <= index < len(worksheet.columns) for index in values) or len(set(values)) != len(values):
        raise ValueError('Select distinct existing ' + role + ' columns.')
    if any(worksheet.columns[index].kind not in kinds for index in values):
        raise ValueError('Unsupported data type in ' + role + ' columns.')
    return list(values)


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value, row):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'Response must be numeric at worksheet row {row + 1}.')
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f'Response exceeds supported numeric range at worksheet row {row + 1}.') from error
    if not math.isfinite(number):
        raise ValueError(f'Response must be finite at worksheet row {row + 1}.')
    return number


def row_statistics(values, sn_type='larger'):
    """Stable finite formulas; unbounded/undefined ratios are unavailable, not fake."""
    n = len(values)
    scale = max(abs(value) for value in values)
    normalized = [value / scale for value in values] if scale else [0.] * n
    mean_normalized = math.fsum(value / n for value in normalized)
    mean = scale * mean_normalized
    deviations = [value - mean for value in values]
    deviation_scale = max(abs(value) for value in deviations)
    if n < 2:
        stdev = None
    elif deviation_scale == 0:
        stdev = 0.
    else:
        stdev = deviation_scale * math.sqrt(math.fsum((value / deviation_scale) ** 2 for value in deviations) / (n - 1))
    if sn_type == 'larger':
        if any(value <= 0 for value in values):
            raise ValueError('Larger-is-better requires strictly positive responses.')
        sn = float(-10 / math.log(10) * (logsumexp([-2 * math.log(value) for value in values]) - math.log(n)))
        note = ''
    elif sn_type == 'smaller':
        if any(value < 0 for value in values):
            raise ValueError('Smaller-is-better requires nonnegative responses with target zero.')
        positive = [2 * math.log(value) for value in values if value > 0]
        sn = float(-10 / math.log(10) * (logsumexp(positive) - math.log(n))) if positive else None
        note = '' if positive else 'All-zero squared loss gives unbounded S/N; no finite ratio is reported.'
    elif sn_type == 'nominal':
        if any(value < 0 for value in values):
            raise ValueError('Classic nominal-is-best requires nonnegative responses with a meaningful absolute zero.')
        if stdev is None:
            sn, note = None, 'Nominal S/N requires at least two response measurements in the row.'
        elif stdev == 0:
            sn, note = None, 'Zero sample variation gives an undefined or unbounded nominal S/N; no finite ratio is reported.'
        elif mean <= 0:
            sn, note = None, 'Classic nominal S/N requires a positive row mean.'
        else:
            sn = 20 * (math.log10(mean) - math.log10(stdev))
            note = ''
    else:
        raise ValueError('Unsupported signal-to-noise formula.')
    if not math.isfinite(mean) or (stdev is not None and not math.isfinite(stdev)) or (sn is not None and not math.isfinite(sn)):
        raise ValueError('Taguchi response arithmetic exceeds supported finite range.')
    return {'n': n, 'mean': mean, 'stdev': stdev, 'sn': sn, 'sn_note': note}


def _average(values):
    if not values or any(value is None for value in values):
        return None
    return math.fsum(value / len(values) for value in values)


def _display(value):
    return format(value, '.7g') if isinstance(value, (int, float)) else str(value)


def _table(worksheet, rows, factor_indices, metric, label):
    factors = []
    for position, index in enumerate(factor_indices):
        column = worksheet.columns[index]
        levels = ordered_values(column, [row['factor_values'][position] for row in rows])
        entries = []
        for level in levels:
            included = [row for row in rows if row['factor_values'][position] == level]
            values = [row[metric] for row in included]
            entries.append({'level': level, 'label': _display(level), 'count': len(values),
                            'available': sum(value is not None for value in values), 'value': _average(values),
                            'row_indices': [row['row'] for row in included]})
        values = [entry['value'] for entry in entries]
        delta = max(values) - min(values) if values and all(value is not None for value in values) else None
        factors.append({'index': index, 'name': column.name or 'C' + str(index + 1),
                        'levels': entries, 'delta': delta, 'rank': None})
    for factor in factors:
        if factor['delta'] is not None:
            factor['rank'] = 1 + sum(other['delta'] is not None and other['delta'] > factor['delta']
                and not math.isclose(other['delta'], factor['delta'], rel_tol=1e-10, abs_tol=1e-12) for other in factors)
    return {'metric': metric, 'label': label, 'factors': factors, 'grand_mean': _average([row[metric] for row in rows]),
            'ranking': 'Descending delta, competition ranks with equal ranks for numerical ties'}


def _fit_models(worksheet, rows, factor_indices, options, input_length):
    from .glm import fit, DEFAULTS as GLM_DEFAULTS
    models = {}
    unavailable = {}
    for metric, name in [('mean', 'Run Mean'), ('sn', 'Signal-to-Noise Ratio'), ('stdev', 'Ln(StDev)' if options['log_stdev'] else 'StDev')]:
        used = [row for row in rows if row[metric] is not None]
        if not options['fit_models']:
            models[metric] = None;unavailable[metric] = 'Main-effects model fitting was not selected.'
            continue
        if not used:
            models[metric] = None;unavailable[metric] = 'No estimable row statistics are available for this response characteristic.'
            continue
        values = [row[metric] for row in used]
        response_scale = max(abs(value) for value in values)
        if max(values) - min(values) <= 32 * math.ulp(response_scale):
            models[metric] = None
            unavailable[metric] = 'Model inference requires a varying response beyond floating-point resolution.'
            continue
        derived = [Column(worksheet.columns[index].name, worksheet.columns[index].kind,
                          [row['factor_values'][position] for row in rows], copy.deepcopy(worksheet.columns[index].metadata))
                   for position, index in enumerate(factor_indices)]
        derived.append(Column(name, 'number', [row[metric] for row in rows]))
        model_options = dict(GLM_DEFAULTS, confidence=options['confidence'], graphs='none', diagnostics='none')
        try:
            result = fit(Worksheet('Static Taguchi derived responses', derived), len(factor_indices), list(range(len(factor_indices))), [], options=model_options)
            result['source_row_indices'] = [rows[index]['row'] for index in result['row_indices']]
            for diagnostic in result.get('diagnostics', []):
                diagnostic['row'] = rows[diagnostic['row'] - 1]['row'] + 1
            result['row_indices'] = list(result['source_row_indices'])
            result['source_metric'] = metric
            result['missing'] = input_length - len(result['row_indices'])
            models[metric] = result
        except (ValueError, ArithmeticError) as error:
            models[metric] = None
            unavailable[metric] = str(error)
    return models, unavailable


def analyze(worksheet, response_indices, factor_indices, options=None):
    if not isinstance(worksheet, Worksheet):
        raise ValueError('Select a worksheet for static Taguchi analysis.')
    options = settings(options)
    responses = _selectors(worksheet, response_indices, 1, 20, 'response', ('number',))
    factors = _selectors(worksheet, factor_indices, 1, 8, 'factor', ('number', 'text'))
    if set(responses) & set(factors):
        raise ValueError('Response and factor columns must be separate.')
    selected = [worksheet.columns[index] for index in responses + factors]
    length = max(len(column.values) for column in selected)
    if length > 20000:
        raise ValueError('Static Taguchi analysis supports at most 20,000 worksheet rows.')
    rows, omitted = [], []
    for row in range(length):
        if any(row >= len(column.values) or _missing(column.values[row]) for column in selected):
            omitted.append(row)
            continue
        values = [_number(worksheet.columns[index].values[row], row) for index in responses]
        try:
            summary = row_statistics(values, options['sn_type'])
        except ValueError as error:
            raise ValueError(str(error) + f' Worksheet row {row + 1}.') from error
        factor_values = [worksheet.columns[index].values[row] for index in factors]
        for index, value in zip(factors, factor_values):
            if worksheet.columns[index].kind == 'number':
                _number(value, row)
        stdev = summary['stdev']
        if options['log_stdev']:
            summary['raw_stdev'] = stdev
            summary['stdev'] = math.log(stdev) if stdev is not None and stdev > 0 else None
        rows.append(dict(row=row, factor_values=factor_values, **summary))
    if not rows:
        raise ValueError('No complete response/factor rows remain.')
    if any(len(set(row['factor_values'][position] for row in rows)) < 2 for position in range(len(factors))):
        raise ValueError('Each control factor needs at least two observed levels after missing-row omission.')
    tables = {metric: _table(worksheet, rows, factors, metric, label) for metric, label in
              [('mean', 'Means'), ('sn', 'Signal-to-Noise Ratios'), ('stdev', 'Ln(Standard Deviations)' if options['log_stdev'] else 'Standard Deviations')]}
    optimum = []
    for factor in tables['sn']['factors']:
        values = [entry['value'] for entry in factor['levels']]
        best = max(values) if values and all(value is not None for value in values) else None
        levels = [entry['level'] for entry in factor['levels'] if best is not None and math.isclose(entry['value'], best, rel_tol=1e-10, abs_tol=1e-12)]
        optimum.append({'factor_index': factor['index'], 'factor_name': factor['name'], 'levels': levels,
                        'sn': best, 'rule': 'Maximize mean S/N', 'estimable': best is not None})
    panels = []
    if options['show_graphs']:
        for metric, table in tables.items():
            for factor in table['factors']:
                values = [level['value'] for level in factor['levels']]
                if any(value is not None for value in values):
                    panels.append({'kind': 'taguchi_main_effects', 'metric': metric, 'title': 'Main Effects for ' + table['label'],
                        'factor_index': factor['index'], 'factor_name': factor['name'], 'levels': [level['level'] for level in factor['levels']],
                        'x_labels': [level['label'] for level in factor['levels']], 'x': list(range(len(values))), 'y': values,
                        'grand_mean': table['grand_mean'], 'xlabel': factor['name'], 'ylabel': table['label'],
                        'row_indices_by_level': [level['row_indices'] for level in factor['levels']]})
    models, model_notes = _fit_models(worksheet, rows, factors, options, length)
    formula = {'larger': '-10*log10(mean(1/Y^2))', 'smaller': '-10*log10(mean(Y^2))',
               'nominal': '10*log10(row_mean^2/sample_standard_deviation^2)'}[options['sn_type']]
    notes = ['Static row-wise analysis: selected response columns represent repeated measurements/noise conditions for each control-factor row.',
             'Incomplete selected response/factor rows are omitted jointly. Repeated worksheet rows are not implicitly pooled.',
             'S/N is always maximized; recommended factor settings maximize marginal mean S/N and do not resolve interaction tradeoffs or target the mean.',
             'Unavailable S/N/standard deviations remain missing; affected level averages, deltas and recommendations are unavailable rather than silently dropping those runs.',
             'Optional fixed-factor models contain main effects only. Saturated, aliased and otherwise unestimable models are not reported as inferential results.',
             'Dynamic Taguchi, interactions, adjusted nominal formulas and predicted optimum performance are not implemented. Native numerical and UI parity remain unverified.']
    if len(responses) == 1:
        notes.append('One response column cannot estimate within-row sample standard deviation or nominal S/N. Larger/smaller row S/N remain available.')
    if len(factors) == 1:
        notes.append('Single-factor summaries are supported as an original bounded extension; the native designed-experiment workflow requires at least two control factors.')
    return {'analysis': 'taguchi_analysis', 'method': 'Static Taguchi response summaries and fixed main effects',
            'response_indices': responses, 'response_names': [worksheet.columns[index].name or 'C' + str(index + 1) for index in responses],
            'factor_indices': factors, 'factor_names': [worksheet.columns[index].name or 'C' + str(index + 1) for index in factors],
            'options': options, 'show_graphs': options['show_graphs'], 'sn_formula': formula, 'response_tables': tables, 'rows': rows,
            'row_indices': [row['row'] for row in rows], 'omitted_rows': omitted, 'n_runs': len(rows),
            'measurements_per_run': len(responses), 'optimum_settings': optimum, 'panels': panels,
            'models': models, 'model_unavailable': model_notes, 'notes': notes, 'sources': SOURCES, 'native_full_parity': False}
