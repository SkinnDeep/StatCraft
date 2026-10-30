"""Original row-wise dynamic Taguchi line fits and robustness summaries.

One worksheet row represents one experimental run. Response columns are matched
explicitly to signal constants, including repeated signals for noise trials.
No grouping or pooling of repeated control-factor rows occurs implicitly.
"""
import copy
import math
from .model import Column, Worksheet
from .taguchi_analysis import _selectors, _missing, _number, _table

SOURCES = [
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/',
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/perform-the-analysis/select-the-options-dynamic-design/',
]
DEFAULTS = dict(reference_method='none', reference_signal=0., reference_response=0., adjusted=False,
                log_stdev=False, fit_models=True, show_graphs=True, show_signal_plots=False, confidence=.95)


def settings(options=None):
    if options is not None and (not isinstance(options, dict) or set(options) - set(DEFAULTS)):
        raise ValueError('Unsupported dynamic Taguchi options.')
    result = dict(DEFAULTS, **(options or {}))
    if result['reference_method'] not in ('none', 'fixed'):
        raise ValueError('Choose no reference point or a fixed reference point.')
    for name in ('reference_signal', 'reference_response', 'confidence'):
        value = result[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(name + ' must be a finite number.')
        try:
            result[name] = float(value)
        except OverflowError as error:
            raise ValueError(name + ' must be a finite number.') from error
        if not math.isfinite(result[name]):
            raise ValueError(name + ' must be a finite number.')
    if not 0 < result['confidence'] < 1:
        raise ValueError('Model confidence must be strictly between zero and one.')
    for name in ('adjusted', 'log_stdev', 'fit_models', 'show_graphs', 'show_signal_plots'):
        if type(result[name]) is not bool:
            raise ValueError(name + ' must be true or false.')
    return result


def _finite_exp(value):
    """Unavailable finite-square values do not discard valid SD or log S/N."""
    if value > math.log(float.fromhex('0x1.fffffffffffffp+1023')) or value < math.log(float.fromhex('0x0.0000000000001p-1022')):
        return None
    return math.exp(value)


def row_statistics(signals, responses, options=None):
    """Fit in scaled coordinates; error df is n-2 (free) or n-1 (fixed)."""
    options = settings(options)
    if not isinstance(signals, (list, tuple)) or not isinstance(responses, (list, tuple)) or len(signals) != len(responses):
        raise ValueError('Match one signal value to every response measurement.')
    if not 2 <= len(signals) <= 40:
        raise ValueError('Dynamic Taguchi requires 2 to 40 signal/response measurements per run.')
    signals = [_number(value, 0) for value in signals]
    responses = [_number(value, 0) for value in responses]
    if len(set(signals)) < 2:
        raise ValueError('Provide at least two distinct signal values.')
    fixed = options['reference_method'] == 'fixed'
    n = len(signals)
    df = n - (1 if fixed else 2)
    if df <= 0:
        raise ValueError('A line with no reference point needs at least three response measurements to estimate residual variation.')
    xs = max([abs(value) for value in signals] + ([abs(options['reference_signal'])] if fixed else []))
    ys = max([abs(value) for value in responses] + ([abs(options['reference_response'])] if fixed else [])) or 1.
    x = [value / xs for value in signals]
    y = [value / ys for value in responses]
    xr = options['reference_signal'] / xs if fixed else math.fsum(value / n for value in x)
    yr = options['reference_response'] / ys if fixed else math.fsum(value / n for value in y)
    dx = [value - xr for value in x]
    dy = [value - yr for value in y]
    # Rescale signal deviations separately so a large location does not square
    # tiny centered values down to zero.
    ds = max(abs(value) for value in dx)
    if ds == 0:
        raise ValueError('Signal variation is below floating-point resolution.')
    d = [value / ds for value in dx]
    r_norm = math.fsum(value * value for value in d)
    b = math.fsum(a * value for a, value in zip(d, dy)) / r_norm
    fitted_norm = [yr + b * value for value in d]
    residual_norm = [observed - fit for observed, fit in zip(y, fitted_norm)]
    tolerance = 16 * math.ulp(max(abs(value) for value in y) or 1.)
    if max(abs(value) for value in residual_norm) <= tolerance:
        residual_norm = [0.] * n
    residual_scale = max(abs(value) for value in residual_norm)
    if residual_scale:
        mse_norm_root = residual_scale * math.sqrt(math.fsum((value / residual_scale) ** 2 for value in residual_norm) / df)
    else:
        mse_norm_root = 0.
    # Log scaling avoids under/overflow in products and quotients such as y/x.
    slope = math.copysign(_finite_exp(math.log(abs(b)) + math.log(ys) - math.log(xs) - math.log(ds)) or 0., b) if b else 0.
    if b and (slope == 0 or not math.isfinite(slope)):
        raise ValueError('Dynamic slope exceeds supported finite range.')
    residual_sd = ys * mse_norm_root
    if not math.isfinite(residual_sd) or (mse_norm_root and residual_sd == 0):
        raise ValueError('Dynamic residual variation exceeds supported finite range.')
    fitted = [ys * value for value in fitted_norm]
    residuals = [ys * value for value in residual_norm]
    if any(not math.isfinite(value) for value in fitted + residuals):
        raise ValueError('Dynamic fitted responses exceed supported finite range.')
    # An extrapolated intercept can be outside the supported finite range even
    # when every observed fitted value and the slope is representable.
    intercept_norm = yr - b * (xr / ds)
    intercept = ys * intercept_norm
    if not math.isfinite(intercept):
        intercept = None
    log_r = 2 * (math.log(xs) + math.log(ds)) + math.log(r_norm)
    r = _finite_exp(log_r)
    log_mse = 2 * (math.log(ys) + math.log(mse_norm_root)) if mse_norm_root else None
    mse = _finite_exp(log_mse) if log_mse is not None else 0.
    sse = _finite_exp(log_mse + math.log(df)) if log_mse is not None else 0.
    note = ''
    if mse_norm_root == 0:
        sn = None
        note = 'Zero residual variation to floating-point resolution gives an undefined or unbounded S/N; no finite ratio is reported.'
    elif b == 0:
        sn = None
        note = 'Zero slope gives no finite dynamic signal-to-noise ratio.'
    else:
        log_ratio = 2 * (math.log(abs(b)) - math.log(xs) - math.log(ds) - math.log(mse_norm_root))
        if options['adjusted']:
            log_correction = -log_r - log_ratio
            if log_correction >= 0:
                sn = None
                note = 'The adjusted signal-to-noise argument is nonpositive; no finite ratio is reported.'
            else:
                # log(-expm1(delta)) remains accurate for nearly equal terms.
                sn = 10 / math.log(10) * (log_ratio + math.log(-math.expm1(log_correction)))
        else:
            sn = 10 / math.log(10) * log_ratio
    if sn is not None and not math.isfinite(sn):
        raise ValueError('Dynamic signal-to-noise arithmetic exceeds supported range.')
    return dict(n=n, signal_values=signals, responses=responses, fitted=fitted, residuals=residuals,
                slope=slope, intercept=intercept, residual_sd=residual_sd, stdev=residual_sd,
                mse=mse, sse=sse, df_error=df, r=r, log_r=log_r, sn=sn, sn_note=note,
                reference_signal=options['reference_signal'] if fixed else None,
                reference_response=options['reference_response'] if fixed else None)


def _fit_models(worksheet, rows, factors, options, length):
    from .glm import fit, DEFAULTS as GLM_DEFAULTS
    models, unavailable = {}, {}
    for metric, label in [('slope', 'Slope'), ('sn', 'Signal-to-Noise Ratio'), ('stdev', 'Ln(StDev)' if options['log_stdev'] else 'StDev')]:
        used = [row for row in rows if row[metric] is not None]
        reason = None
        if not options['fit_models']:
            reason = 'Main-effects model fitting was not selected.'
        elif not used:
            reason = 'No estimable row statistics are available for this response characteristic.'
        elif len(used) != len(rows):
            reason = 'Some runs have an unavailable response characteristic; a partial-run model is not fitted.'
        else:
            values = [row[metric] for row in used]
            if max(values) - min(values) <= 32 * math.ulp(max(abs(value) for value in values)):
                reason = 'Model inference requires a varying response beyond floating-point resolution.'
        if reason:
            models[metric] = None
            unavailable[metric] = reason
            continue
        columns = [Column(worksheet.columns[index].name, worksheet.columns[index].kind,
                          [row['factor_values'][position] for row in rows], copy.deepcopy(worksheet.columns[index].metadata))
                   for position, index in enumerate(factors)]
        columns.append(Column(label, 'number', [row[metric] for row in rows]))
        model_options = dict(GLM_DEFAULTS, confidence=options['confidence'], graphs='none', diagnostics='none')
        try:
            result = fit(Worksheet('Dynamic Taguchi derived characteristics', columns), len(factors), list(range(len(factors))), [], options=model_options)
            result['source_row_indices'] = [rows[index]['row'] for index in result['row_indices']]
            for diagnostic in result.get('diagnostics', []):
                diagnostic['row'] = rows[diagnostic['row'] - 1]['row'] + 1
            result['row_indices'] = list(result['source_row_indices'])
            result['source_metric'] = metric
            result['missing'] = length - len(result['row_indices'])
            models[metric] = result
        except (ValueError, ArithmeticError) as error:
            models[metric] = None
            unavailable[metric] = str(error)
    return models, unavailable


def analyze(worksheet, response_indices, signal_values, factor_indices, options=None):
    if not isinstance(worksheet, Worksheet):
        raise ValueError('Select a worksheet for dynamic Taguchi analysis.')
    options = settings(options)
    responses = _selectors(worksheet, response_indices, 2, 40, 'response', ('number',))
    factors = _selectors(worksheet, factor_indices, 1, 8, 'factor', ('number', 'text'))
    if set(responses) & set(factors):
        raise ValueError('Response and control-factor columns must be separate.')
    if not isinstance(signal_values, (list, tuple)) or len(signal_values) != len(responses):
        raise ValueError('Match one signal value to every selected response column.')
    signals = [_number(value, 0) for value in signal_values]
    # Validate signal geometry and degrees of freedom independently of row data.
    row_statistics(signals, [options['reference_response'] if options['reference_method'] == 'fixed' else 0.] * len(signals), options)
    selected = [worksheet.columns[index] for index in responses + factors]
    length = max(len(column.values) for column in selected)
    if length > 20000:
        raise ValueError('Dynamic Taguchi analysis supports at most 20,000 worksheet rows.')
    rows, omitted = [], []
    for row in range(length):
        if any(row >= len(column.values) or _missing(column.values[row]) for column in selected):
            omitted.append(row)
            continue
        values = [_number(worksheet.columns[index].values[row], row) for index in responses]
        factor_values = [worksheet.columns[index].values[row] for index in factors]
        for index, value in zip(factors, factor_values):
            if worksheet.columns[index].kind == 'number':
                _number(value, row)
        try:
            summary = row_statistics(signals, values, options)
        except ValueError as error:
            raise ValueError(str(error) + f' Worksheet row {row + 1}.') from error
        summary['raw_stdev'] = summary['residual_sd']
        if options['log_stdev']:
            summary['stdev'] = math.log(summary['residual_sd']) if summary['residual_sd'] > 0 else None
        rows.append(dict(row=row, factor_values=factor_values, **summary))
    if not rows:
        raise ValueError('No complete response/control-factor rows remain.')
    if any(len(set(row['factor_values'][position] for row in rows)) < 2 for position in range(len(factors))):
        raise ValueError('Each control factor needs at least two observed levels after missing-row omission.')
    tables = {metric: _table(worksheet, rows, factors, metric, label) for metric, label in
              [('slope', 'Slopes'), ('sn', 'Signal-to-Noise Ratios'), ('stdev', 'Ln(Standard Deviations)' if options['log_stdev'] else 'Standard Deviations')]}
    if any(factor['delta'] is not None and not math.isfinite(factor['delta'])
           for table in tables.values() for factor in table['factors']):
        raise ValueError('Dynamic factor response ranges exceed supported finite arithmetic.')
    optimum = []
    for factor in tables['sn']['factors']:
        values = [entry['value'] for entry in factor['levels']]
        best = max(values) if values and all(value is not None for value in values) else None
        levels = [entry['level'] for entry in factor['levels'] if best is not None and math.isclose(entry['value'], best, rel_tol=1e-10, abs_tol=1e-12)]
        optimum.append(dict(factor_index=factor['index'], factor_name=factor['name'], levels=levels,
                            sn=best, rule='Maximize mean S/N', estimable=best is not None))
    panels = []
    if options['show_graphs']:
        for metric, table in tables.items():
            for factor in table['factors']:
                values = [level['value'] for level in factor['levels']]
                if any(value is not None for value in values):
                    panels.append(dict(kind='taguchi_main_effects', metric=metric, title='Main Effects for ' + table['label'],
                                       factor_index=factor['index'], factor_name=factor['name'], levels=[level['level'] for level in factor['levels']],
                                       x_labels=[level['label'] for level in factor['levels']], x=list(range(len(values))), y=values,
                                       grand_mean=table['grand_mean'], xlabel=factor['name'], ylabel=table['label'],
                                       row_indices_by_level=[level['row_indices'] for level in factor['levels']]))
    models, model_unavailable = _fit_models(worksheet, rows, factors, options, length)
    notes = [
        'Dynamic row-wise analysis: each response column is paired with its explicitly entered signal value; repeated signal values represent noise/trial measurements.',
        'Incomplete selected response/control-factor rows are omitted jointly. Repeated control-factor rows are not implicitly pooled.',
        'Residual standard deviation is sqrt(SSE/df): df=n-2 for a fitted intercept and df=n-1 for a fixed reference point.',
        'S/N settings maximize marginal mean S/N; they do not establish a joint interaction-aware optimum or meet a slope target.',
        'Unavailable S/N remains missing. Affected level averages/deltas/recommendations and partial-run characteristic models are unavailable rather than silently omitting those runs.',
        'Optional fixed-factor models contain main effects only. Saturated, aliased and constant-characteristic models do not provide inferential results.',
        'Mean-response-at-signal reference fits, interactions, separate noise-factor effects and predicted optimum performance are not implemented. Native numerical and UI parity remain unverified.',
    ]
    if any(row['mse'] is None or row['r'] is None for row in rows):
        notes.append('Some squared quantities are outside finite floating-point range and are unavailable; residual SD and S/N use scaled/logarithmic arithmetic.')
    if any(row['intercept'] is None for row in rows):
        notes.append('An extrapolated intercept is outside finite range; observed fitted responses are still retained.')
    formula = '10*log10(slope^2/MSE - 1/r)' if options['adjusted'] else '10*log10(slope^2/MSE)'
    return dict(analysis='dynamic_taguchi_analysis', method='Dynamic Taguchi response summaries and fixed main effects',
                response_indices=responses, response_names=[worksheet.columns[index].name or 'C' + str(index + 1) for index in responses],
                signal_values=signals, factor_indices=factors, factor_names=[worksheet.columns[index].name or 'C' + str(index + 1) for index in factors],
                options=options, show_graphs=options['show_graphs'], show_signal_plots=options['show_signal_plots'], sn_formula=formula,
                response_tables=tables, rows=rows, row_indices=[row['row'] for row in rows], omitted_rows=omitted,
                n_runs=len(rows), measurements_per_run=len(responses), optimum_settings=optimum, panels=panels,
                models=models, model_unavailable=model_unavailable, notes=notes, sources=SOURCES, native_full_parity=False)
