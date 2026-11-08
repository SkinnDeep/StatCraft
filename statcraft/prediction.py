"""Independent current-worksheet OLS predictions, with centered SVD uncertainty.

Scope: existing continuous OLS, fixed GLM and coded response-surface recipes.
Reference: https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/predict/methods-and-formulas/methods-and-formulas/
Native-product numerical equivalence is unverified.
"""
import itertools
import math
import copy
import numpy as np
# scipy imported lazily
from .model import finite_number

DEFAULTS = dict(confidence=.95, intervals='both', side='two_sided', show_equation=True, show_table=True)
SUPPORTED = ('multiple_regression', 'general_linear_model', 'analyze_response_surface', 'fit_binary_logistic', 'analyze_factorial', 'analyze_factorial_terms')


def normalize_recipe(recipe):
    """Canonicalize a validated legacy simple-regression recipe, without mutation."""
    from .recipes import columns
    if not isinstance(recipe, dict):
        raise ValueError('Choose a supported fitted model recipe.')
    action = recipe.get('action')
    if action not in SUPPORTED and action != 'inference':
        raise ValueError('Choose a supported fitted regression, general linear or response surface model.')
    columns(recipe)
    if action in SUPPORTED:
        return copy.deepcopy(recipe)
    p = recipe['parameters']
    if p['method'] != 'linear_regression' or len(p['indices']) != 2 or len(set(p['indices'])) != 2:
        raise ValueError('Only a simple linear regression inference result can supply a prediction model.')
    return dict(action='multiple_regression', parameters=dict(response_index=p['indices'][1], predictor_indices=[p['indices'][0]], confidence=p['confidence']))


def settings(options=None):
    if options is None:
        return dict(DEFAULTS)
    if not isinstance(options, dict) or set(options) != set(DEFAULTS):
        raise ValueError('Unsupported prediction options.')
    o = dict(options)
    if type(o['confidence']) not in (int, float) or not math.isfinite(o['confidence']) or not 0 < o['confidence'] < 1:
        raise ValueError('Confidence level must be between 0 and 100 percent.')
    if o['intervals'] not in ('both', 'confidence', 'prediction', 'none'):
        raise ValueError('Choose confidence, prediction, both or no intervals.')
    if o['side'] not in ('two_sided', 'lower', 'upper'):
        raise ValueError('Choose a two-sided interval, lower bound or upper bound.')
    if any(type(o[k]) is not bool for k in ('show_equation', 'show_table')):
        raise ValueError('Choose valid prediction result display settings.')
    return o


def _source(worksheet, recipe):
    from .recipes import columns
    recipe = normalize_recipe(recipe)
    used = columns(recipe)
    if any(i >= len(worksheet.columns) for i in used):
        raise ValueError('A source model column no longer exists.')
    action, p = recipe['action'], recipe['parameters']
    if action == 'multiple_regression':
        from .regression import multiple_regression
        indices = p['predictor_indices']; response = p['response_index']
        if not 1 <= len(indices) <= 8 or len(set(indices + [response])) != len(indices)+1:
            raise ValueError('Choose a separate response and 1–8 distinct numeric predictors.')
        cols = [worksheet.columns[i] for i in indices + [response]]
        if any(c.kind != 'number' for c in cols):
            raise ValueError('Regression predictions require numeric source columns.')
        length = max(len(c.values) for c in cols)
        if length > 20000:
            raise ValueError('Prediction models support at most 20,000 source rows.')
        aligned = [[c.values[r] if r < len(c.values) else None for r in range(length)] for c in cols]
        result = multiple_regression(aligned[:-1], aligned[-1], p['confidence'], [c.name for c in cols[:-1]])
        factor_count = 0
    elif action == 'general_linear_model':
        from .glm import fit
        result = fit(worksheet, **p)
        indices = p['factor_indices'] + p['covariate_indices']; response = p['response_index']
        factor_count = len(p['factor_indices'])
    elif action in ('analyze_factorial', 'analyze_factorial_terms'):
        from .doe import analyze_factorial
        selected_terms = p.get('selected_terms') if action == 'analyze_factorial_terms' else None
        result = analyze_factorial(
            worksheet,
            p['response_index'],
            p['factor_indices'],
            p.get('max_order', 2),
            p.get('confidence', 0.95),
            selected_terms=selected_terms,
        )
        result['coding_information'] = [
            dict(name=c['name'], kind='covariate', center=c['center'], half_range=c['half_range'])
            for c in result['factor_coding']
        ]
        result['terms'] = result['selected_terms']
        indices = list(p['factor_indices']); response = p['response_index']; factor_count = 0
    else:
        from .response_surface import fit
        result = fit(worksheet, **p)
        block = p.get('block_index')
        indices = ([] if block is None else [block]) + p['factor_indices']; response = p['response_index']; factor_count = 0 if block is None else 1
    predictors = []
    for j, i in enumerate(indices):
        c = worksheet.columns[i]
        predictors.append(dict(name=c.name, index=i, kind=c.kind, role='factor' if j < factor_count else 'covariate',
                               levels=result['coding_information'][j]['levels'] if j < factor_count else []))
    title = dict(multiple_regression='Multiple Regression', general_linear_model='General Linear Model',
                 analyze_response_surface='Response Surface Regression',
                 analyze_factorial='Factorial Regression', analyze_factorial_terms='Factorial Regression')[action]
    spec = dict(model_action=action, model_title=title, response_name=worksheet.columns[response].name,
                predictor_names=[v['name'] for v in predictors], predictor_indices=list(indices), predictors=predictors)
    return spec, result


def model_spec(worksheet, model_recipe):
    """Validate/refit the source model and return ordered predictor UI metadata."""
    model_recipe=normalize_recipe(model_recipe)
    if model_recipe['action']=='fit_binary_logistic':
        from .logistic import model_spec as logistic_spec
        return logistic_spec(worksheet,model_recipe)
    return _source(worksheet, model_recipe)[0]


def _encode(rows, action, result):
    if action == 'multiple_regression':
        return np.asarray(rows, dtype=float)
    blocks = []
    for j, info in enumerate(result['coding_information']):
        values = [row[j] for row in rows]
        if info.get('kind') == 'factor':
            levels = info['levels']; reference = levels[-1]
            blocks.append([np.asarray([1. if v == level else -1. if result['coding'] == 'effect' and v == reference else 0. for v in values]) for level in levels[:-1]])
        elif action in ('analyze_response_surface', 'analyze_factorial', 'analyze_factorial_terms'):
            blocks.append([(np.asarray(values, dtype=float)-info['center'])/info['half_range']])
        else:
            blocks.append([(np.asarray(values, dtype=float)-info['shift'])/info['scale']])
    encoded = []
    for term in result['terms']:
        for combination in itertools.product(*(range(len(blocks[i])) for i in term)):
            product = np.ones(len(rows))
            for i, j in zip(term, combination):
                product *= blocks[i][j]
            encoded.append(product)
    return np.asarray(encoded).T


def _inputs(worksheet, spec, input_mode, values, new_indices):
    width = len(spec['predictors'])
    if input_mode == 'values':
        if new_indices is not None:
            raise ValueError('Manual predictions must not select worksheet input columns.')
        if not isinstance(values, list) or not 1 <= len(values) <= 20000 or any(not isinstance(r, list) or len(r) != width for r in values):
            raise ValueError('Enter 1–20,000 prediction rows with one value per predictor.')
        rows = [list(row) for row in values]
    elif input_mode == 'columns':
        if values is not None or not isinstance(new_indices, list) or len(new_indices) != width or any(type(i) is not int or not 0 <= i < len(worksheet.columns) for i in new_indices):
            raise ValueError('Select one valid new-data column for each predictor.')
        cols = [worksheet.columns[i] for i in new_indices]
        if any(c.kind != p['kind'] for c, p in zip(cols, spec['predictors'])):
            raise ValueError('New-data column types must match their source predictors.')
        length = max(len(c.values) for c in cols)
        if not 1 <= length <= 20000:
            raise ValueError('Select 1–20,000 new-data rows.')
        rows = [[c.values[r] if r < len(c.values) else None for c in cols] for r in range(length)]
    else:
        raise ValueError('Choose manual values or worksheet columns for predictions.')
    for r, row in enumerate(rows, 1):
        for j, (value, p) in enumerate(zip(row, spec['predictors'])):
            if value is None:
                continue
            if p['kind'] == 'number':
                row[j] = finite_number(value)
            elif not isinstance(value, str):
                raise ValueError('Enter text settings for '+p['name']+'.')
            if p['role'] == 'factor' and row[j] not in p['levels']:
                raise ValueError('Unknown factor level for '+p['name']+' in prediction row '+str(r)+': '+str(value))
    return rows


def predict(worksheet, model_recipe, input_mode='values', values=None, new_indices=None, options=None):
    """Refit current worksheet values; predict aligned settings without mutating it."""
    model_recipe=normalize_recipe(model_recipe)
    if model_recipe['action']=='fit_binary_logistic':
        from .logistic import predict as predict_logistic
        return predict_logistic(worksheet,model_recipe,input_mode,values,new_indices,dict(settings(),intervals='confidence') if options is None else options)
    o = settings(options); spec, result = _source(worksheet, model_recipe)
    inputs = _inputs(worksheet, spec, input_mode, values, new_indices)
    action = spec['model_action']; p = model_recipe['parameters']; indices = spec['predictor_indices']
    source_rows = result['row_indices']; n = len(source_rows)
    train = [[worksheet.columns[j].values[r] for j in indices] for r in source_rows]
    y = np.asarray([worksheet.columns[p['response_index']].values[r] for r in source_rows], dtype=float)
    valid = [i for i, row in enumerate(inputs) if all(v is not None for v in row)]
    ranges = [(min(row[j] for row in train), max(row[j] for row in train)) if v['role'] != 'factor' else None for j, v in enumerate(spec['predictors'])]
    out = [dict(row=i+1, inputs=row, fit=None, se_fit=None, ci_low=None, ci_high=None, pi_low=None, pi_high=None, extrapolated=False, status='missing') for i, row in enumerate(inputs)]
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            x = _encode(train, action, result)
            means = np.asarray([math.fsum(x[:, j]/n) for j in range(x.shape[1])])
            scales = np.max(np.abs(x-means), axis=0); z = (x-means)/scales
            u, singular, vh = np.linalg.svd(z, full_matrices=False)
            mean_y = math.fsum(y/n); unit = float(np.max(np.abs(y-mean_y)))
            gamma = vh.T @ ((u.T @ ((y-mean_y)/unit))/singular)
            if valid:
                new = _encode([inputs[i] for i in valid], action, result)
                coded = (new-means)/scales
                fits = mean_y + unit*(coded@gamma)
                transformed = (coded@vh.T)/singular
                leverages = 1/n + np.sum(transformed*transformed, axis=1)
                from scipy import stats
                quantile = float(stats.t.ppf((1+o['confidence'])/2 if o['side']=='two_sided' else o['confidence'], result['df_error']))
                for i, fit, h in zip(valid, fits, leverages):
                    row = out[i]; row.update(fit=float(fit), status=result['status'], extrapolated=any(bound and not bound[0] <= value <= bound[1] for value, bound in zip(inputs[i], ranges)))
                    if result['status'] != 'exact_fit':
                        se = result['residual_stdev']*math.sqrt(float(h)); row['se_fit'] = se
                        if o['intervals'] in ('confidence', 'both'):
                            delta = quantile*se; row.update(ci_low=float(fit-delta) if o['side']!='upper' else None, ci_high=float(fit+delta) if o['side']!='lower' else None)
                        if o['intervals'] in ('prediction', 'both'):
                            delta = quantile*result['residual_stdev']*math.sqrt(1+float(h)); row.update(pi_low=float(fit-delta) if o['side']!='upper' else None, pi_high=float(fit+delta) if o['side']!='lower' else None)
                    if any(v is not None and not math.isfinite(v) for v in (row[k] for k in ('fit','se_fit','ci_low','ci_high','pi_low','pi_high'))):
                        raise ValueError('Prediction arithmetic exceeds the supported finite numeric range.')
    except (FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
        raise ValueError('Prediction arithmetic exceeds the supported finite numeric range or the solve failed.') from exc
    warnings = list(result.get('warnings', []))
    if len(valid) != len(inputs):
        warnings.append('Rows missing predictor settings are retained with no prediction.')
    if any(row['extrapolated'] for row in out):
        warnings.append('Some settings exceed observed continuous predictor ranges; predictions are extrapolations. Within-range combinations can still be poorly supported.')
    return dict(analysis='model_prediction', **spec, options=o, rows=out, count=len(inputs), used=len(valid), missing=len(inputs)-len(valid),
                df_error=result['df_error'], residual_stdev=result['residual_stdev'], status=result['status'], warnings=warnings,
                coefficients=result['coefficients'], method='Current-worksheet model refit and prediction',
                methodnotes='The source recipe is refitted using current worksheet values; stored coefficients are not reused. Pointwise intervals or one-sided bounds assume independent normal errors of constant variance. Exact fits omit uncertainty. Native-product equivalence is unverified.')
