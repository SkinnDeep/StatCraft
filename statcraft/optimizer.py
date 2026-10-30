"""Independent Derringer-Suich response optimization across fitted worksheet models.

Scope: existing continuous OLS, fixed GLM, two-level factorial, response-surface
and binary-logistic recipes on the active worksheet.
Reference:
  Derringer, G. & Suich, R. (1980), Journal of Quality Technology 12(4), 214-219.
  https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/methods-and-formulas/methods-and-formulas/
Native-product numerical equivalence is unverified.
"""
import copy
import itertools
import math
import numpy as np
from scipy import optimize as sp_optimize, stats
from .model import finite_number
from .prediction import _encode as _encode_ols, normalize_recipe as _normalize_prediction_recipe

SUPPORTED_MODELS = (
    'multiple_regression',
    'general_linear_model',
    'analyze_response_surface',
    'fit_binary_logistic',
    'analyze_factorial',
    'analyze_factorial_terms',
)

MODEL_TITLES = {
    'multiple_regression': 'Multiple Regression',
    'general_linear_model': 'General Linear Model',
    'analyze_response_surface': 'Response Surface Regression',
    'fit_binary_logistic': 'Binary Logistic Regression',
    'analyze_factorial': 'Factorial Regression',
    'analyze_factorial_terms': 'Factorial Regression',
}

GOALS = ('none', 'minimize', 'target', 'maximize')
CONSTRAINT_MODES = ('none', 'hold', 'region')
MAX_CATEGORICAL_COMBINATIONS = 256
PROFILE_GRID_POINTS = 51

DEFAULTS = dict(
    confidence=0.95,
    side='two_sided',
    max_solutions=1,
    optimization_plot=True,
    show_parameters=True,
    show_variable_ranges=True,
    show_starting_point=True,
    show_solutions=True,
    show_prediction=True,
    constraints=[],
    starting_values=[],
)


def _finite_result(value):
    if isinstance(value, dict):
        for child in value.values():
            _finite_result(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _finite_result(child)
    elif isinstance(value, (float, np.floating)) and not math.isfinite(value):
        raise ValueError('Response optimization arithmetic exceeds supported finite precision.')
    return value


def normalize_model_recipe(recipe):
    """Canonicalize a supported fitted-model recipe without mutating the caller's object."""
    from .recipes import columns
    if not isinstance(recipe, dict):
        raise ValueError('Choose a supported fitted model recipe for response optimization.')
    action = recipe.get('action')
    if action in ('analyze_factorial', 'analyze_factorial_terms'):
        columns(recipe)
        return copy.deepcopy(recipe)
    if action in SUPPORTED_MODELS or action == 'inference':
        return _normalize_prediction_recipe(recipe)
    raise ValueError('Choose a supported regression, GLM, factorial, response surface or binary logistic model.')


def _normalize_constraint(item):
    if not isinstance(item, dict) or set(item) != {'index', 'mode', 'value', 'lower', 'upper'}:
        raise ValueError('Each predictor constraint must specify index, mode, value, lower and upper.')
    idx = item['index']
    mode = item['mode']
    if type(idx) is not int or idx < 0:
        raise ValueError('Constraint column index must be a nonnegative integer.')
    if mode not in CONSTRAINT_MODES:
        raise ValueError('Constraint mode must be none, hold or region.')
    val = item['value']
    lo = item['lower']
    hi = item['upper']
    if mode == 'none':
        return dict(index=idx, mode='none', value=None, lower=None, upper=None)
    if mode == 'hold':
        if val is None or isinstance(val, bool) or not isinstance(val, (str, int, float)):
            raise ValueError('Hold constraint requires a valid setting value.')
        if isinstance(val, (int, float)):
            val = finite_number(val)
        return dict(index=idx, mode='hold', value=val, lower=None, upper=None)
    if lo is None or hi is None or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (lo, hi)):
        raise ValueError('Region constraint requires finite numeric lower and upper bounds.')
    lo_f, hi_f = finite_number(lo), finite_number(hi)
    if lo_f >= hi_f:
        raise ValueError('Constraint lower bound must be strictly less than upper bound.')
    return dict(index=idx, mode='region', value=None, lower=lo_f, upper=hi_f)


def _normalize_starting_value(item):
    if not isinstance(item, dict) or set(item) != {'index', 'value'}:
        raise ValueError('Each starting value entry must specify index and value.')
    idx = item['index']
    val = item['value']
    if type(idx) is not int or idx < 0:
        raise ValueError('Starting value column index must be a nonnegative integer.')
    if val is None or isinstance(val, bool) or not isinstance(val, (str, int, float)):
        raise ValueError('Starting value must be a finite number or factor level.')
    if isinstance(val, (int, float)):
        val = finite_number(val)
    return dict(index=idx, value=val)


def settings(options=None):
    if options is None:
        return copy.deepcopy(DEFAULTS)
    if not isinstance(options, dict) or set(options) != set(DEFAULTS):
        raise ValueError('Unsupported response optimizer options.')
    o = copy.deepcopy(options)
    if type(o['confidence']) not in (int, float) or not math.isfinite(o['confidence']) or not 0 < o['confidence'] < 1:
        raise ValueError('Confidence level must be between 0 and 100 percent.')
    o['confidence'] = float(o['confidence'])
    if o['side'] not in ('two_sided', 'lower', 'upper'):
        raise ValueError('Choose a two-sided interval, lower bound or upper bound.')
    if type(o['max_solutions']) is not int or not 1 <= o['max_solutions'] <= 10:
        raise ValueError('Number of solutions to display must be an integer from 1 to 10.')
    for key in ('optimization_plot', 'show_parameters', 'show_variable_ranges',
                'show_starting_point', 'show_solutions', 'show_prediction'):
        if type(o[key]) is not bool:
            raise ValueError('Choose valid response optimizer display settings.')
    if not isinstance(o['constraints'], list):
        raise ValueError('Constraints must be a list of predictor constraint objects.')
    seen_c = set()
    norm_c = []
    for item in o['constraints']:
        c = _normalize_constraint(item)
        if c['index'] in seen_c:
            raise ValueError('Duplicate constraint for the same predictor column.')
        seen_c.add(c['index'])
        if c['mode'] != 'none':
            norm_c.append(c)
    o['constraints'] = norm_c
    if not isinstance(o['starting_values'], list):
        raise ValueError('Starting values must be a list of predictor starting settings.')
    seen_s = set()
    norm_s = []
    for item in o['starting_values']:
        s = _normalize_starting_value(item)
        if s['index'] in seen_s:
            raise ValueError('Duplicate starting value for the same predictor column.')
        seen_s.add(s['index'])
        norm_s.append(s)
    o['starting_values'] = norm_s
    return o


def individual_desirability(y, goal, lower, target, upper, weight=1.0):
    """Evaluate Derringer-Suich individual desirability d_i(y) in [0, 1]."""
    y = finite_number(y)
    if type(weight) not in (int, float) or not math.isfinite(weight) or not 0.1 <= weight <= 10.0:
        raise ValueError('Desirability weight must be between 0.1 and 10.')
    r = float(weight)
    if goal == 'minimize':
        if target is None or upper is None:
            raise ValueError('Minimize goal requires target and upper bound.')
        t, u = finite_number(target), finite_number(upper)
        if t >= u:
            raise ValueError('Minimize goal requires Target < Upper.')
        if y <= t:
            return 1.0
        if y >= u:
            return 0.0
        return float(((u - y) / (u - t)) ** r)
    if goal == 'maximize':
        if lower is None or target is None:
            raise ValueError('Maximize goal requires lower bound and target.')
        l, t = finite_number(lower), finite_number(target)
        if l >= t:
            raise ValueError('Maximize goal requires Lower < Target.')
        if y <= l:
            return 0.0
        if y >= t:
            return 1.0
        return float(((y - l) / (t - l)) ** r)
    if goal == 'target':
        if lower is None or target is None or upper is None:
            raise ValueError('Target goal requires lower bound, target and upper bound.')
        l, t, u = finite_number(lower), finite_number(target), finite_number(upper)
        if not l < t < u:
            raise ValueError('Target goal requires Lower < Target < Upper.')
        if y <= l or y >= u:
            return 0.0
        if y <= t:
            return float(((y - l) / (t - l)) ** r)
        return float(((u - y) / (u - t)) ** r)
    raise ValueError('Optimization goal must be minimize, target or maximize.')


def composite_desirability(desirabilities, importances=None):
    """Evaluate weighted geometric mean D = prod(d_i ** (w_i / sum(w)))."""
    if not desirabilities:
        raise ValueError('At least one response desirability is required.')
    d_vals = [finite_number(d) for d in desirabilities]
    if any(not 0.0 <= d <= 1.0 for d in d_vals):
        raise ValueError('Individual desirabilities must lie between 0 and 1.')
    if importances is None:
        w_vals = [1.0] * len(d_vals)
    else:
        if len(importances) != len(d_vals):
            raise ValueError('Importance count must match desirability count.')
        w_vals = [finite_number(w) for w in importances]
        if any(not 0.1 <= w <= 10.0 for w in w_vals):
            raise ValueError('Importance values must lie between 0.1 and 10.')
    total_w = math.fsum(w_vals)
    if any(d <= 0.0 for d in d_vals):
        return 0.0
    log_d = math.fsum((w / total_w) * math.log(d) for d, w in zip(d_vals, w_vals))
    return float(min(1.0, max(0.0, math.exp(log_d))))


def _fit_model_bundle(worksheet, recipe):
    """Validate and refit a supported source model on current worksheet data."""
    from .recipes import columns
    recipe = normalize_model_recipe(recipe)
    used = columns(recipe)
    if any(i >= len(worksheet.columns) for i in used):
        raise ValueError('A source model column no longer exists.')
    action, p = recipe['action'], recipe['parameters']
    if action == 'fit_binary_logistic':
        from .logistic import _source as logistic_source
        spec, result = logistic_source(worksheet, recipe)
        source_rows = result['row_indices']
        obs_vals = list(result['probabilities'])
        predictors = []
        for pred in spec['predictors']:
            idx = pred['index']
            col_vals = [worksheet.columns[idx].values[r] for r in source_rows]
            predictors.append(dict(
                name=pred['name'],
                index=idx,
                kind=pred['kind'],
                role=pred['role'],
                levels=list(pred.get('levels', [])),
                min=min(col_vals) if pred['role'] != 'factor' else None,
                max=max(col_vals) if pred['role'] != 'factor' else None,
            ))
        return dict(
            recipe=recipe,
            action=action,
            model_title=MODEL_TITLES[action],
            response_index=p['response_index'],
            response_name=spec['response_name'],
            is_probability=True,
            event=result.get('event'),
            observed_min=float(min(obs_vals)),
            observed_max=float(max(obs_vals)),
            predictors=predictors,
            result=result,
            warnings=list(result.get('warnings', [])),
        )
    if action in ('analyze_factorial', 'analyze_factorial_terms'):
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
        indices = list(p['factor_indices'])
        response_idx = p['response_index']
        factor_count = 0
    else:
        from .prediction import _source as ols_source
        spec, result = ols_source(worksheet, recipe)
        indices = list(spec['predictor_indices'])
        response_idx = p['response_index']
        factor_count = sum(1 for pred in spec['predictors'] if pred['role'] == 'factor')
    source_rows = result['row_indices']
    n = len(source_rows)
    train = [[worksheet.columns[j].values[r] for j in indices] for r in source_rows]
    y = np.asarray([worksheet.columns[response_idx].values[r] for r in source_rows], dtype=float)
    encode_action = 'analyze_response_surface' if action in ('analyze_factorial', 'analyze_factorial_terms') else action
    x = _encode_ols(train, encode_action, result)
    means = np.asarray([math.fsum(x[:, j] / n) for j in range(x.shape[1])])
    scales = np.max(np.abs(x - means), axis=0)
    z = (x - means) / scales
    u, singular, vh = np.linalg.svd(z, full_matrices=False)
    mean_y = math.fsum(y / n)
    unit = float(np.max(np.abs(y - mean_y)))
    gamma = vh.T @ ((u.T @ ((y - mean_y) / unit)) / singular) if unit > 0 else np.zeros(x.shape[1])
    predictors = []
    for j, idx in enumerate(indices):
        c = worksheet.columns[idx]
        is_factor = j < factor_count
        if action in ('analyze_factorial', 'analyze_factorial_terms'):
            f_code = result['factor_coding'][j]
            lo, hi = float(f_code['low']), float(f_code['high'])
            levels = []
        elif is_factor:
            lo = hi = None
            levels = list(result['coding_information'][j]['levels'])
        else:
            col_vals = [row[j] for row in train]
            lo, hi = float(min(col_vals)), float(max(col_vals))
            levels = []
        predictors.append(dict(
            name=c.name,
            index=idx,
            kind=c.kind,
            role='factor' if is_factor else 'covariate',
            levels=levels,
            min=lo,
            max=hi,
        ))
    return dict(
        recipe=recipe,
        action=action,
        encode_action=encode_action,
        model_title=MODEL_TITLES[action],
        response_index=response_idx,
        response_name=worksheet.columns[response_idx].name,
        is_probability=False,
        event=None,
        observed_min=float(np.min(y)),
        observed_max=float(np.max(y)),
        predictors=predictors,
        result=result,
        svd=dict(n=n, means=means, scales=scales, singular=singular, vh=vh, mean_y=mean_y, unit=unit, gamma=gamma),
        warnings=list(result.get('warnings', [])),
    )


def _predict_bundle_rows(bundle, rows, confidence=0.95, side='two_sided', compute_intervals=False):
    """Evaluate point fits and optional uncertainty intervals for a list of predictor rows."""
    if bundle['action'] == 'fit_binary_logistic':
        from .logistic import _encode as encode_logistic
        from scipy import special
        res = bundle['result']
        x = encode_logistic(rows, res['coding_information'], res['terms'])
        z = np.column_stack([np.ones(len(rows)), (x[:, 1:] - np.asarray(res['_centers'])) / np.asarray(res['_scales'])])
        eta = z @ np.asarray(res['_gamma'])
        probs = special.expit(eta)
        if not compute_intervals:
            return [dict(fit=float(p), se_fit=None, ci_low=None, ci_high=None, pi_low=None, pi_high=None) for p in probs]
        cov = np.asarray(res['_covariance'])
        var = np.maximum(0.0, np.einsum('ij,jk,ik->i', z, cov, z))
        quantile = float(stats.norm.isf((1.0 - confidence) / 2.0)) if side == 'two_sided' else float(stats.norm.ppf(confidence))
        out = []
        for p_val, e_val, v_val in zip(probs, eta, var):
            p_f = float(p_val)
            e_f = float(e_val)
            se_eta = math.sqrt(float(v_val))
            se_p = p_f * (1.0 - p_f) * se_eta
            ci_lo = float(special.expit(e_f - quantile * se_eta)) if side != 'upper' else None
            ci_hi = float(special.expit(e_f + quantile * se_eta)) if side != 'lower' else None
            out.append(dict(fit=p_f, se_fit=se_p, ci_low=ci_lo, ci_high=ci_hi, pi_low=None, pi_high=None))
        return out
    svd = bundle['svd']
    res = bundle['result']
    new_x = _encode_ols(rows, bundle['encode_action'], res)
    coded = (new_x - svd['means']) / svd['scales']
    fits = svd['mean_y'] + svd['unit'] * (coded @ svd['gamma'])
    if not compute_intervals:
        return [dict(fit=float(f), se_fit=None, ci_low=None, ci_high=None, pi_low=None, pi_high=None) for f in fits]
    transformed = (coded @ svd['vh'].T) / svd['singular']
    leverages = 1.0 / svd['n'] + np.sum(transformed * transformed, axis=1)
    quantile = float(stats.t.ppf((1.0 + confidence) / 2.0 if side == 'two_sided' else confidence, res['df_error']))
    out = []
    for f_val, h_val in zip(fits, leverages):
        fit_f = float(f_val)
        if res.get('status') == 'exact_fit':
            out.append(dict(fit=fit_f, se_fit=None, ci_low=None, ci_high=None, pi_low=None, pi_high=None))
        else:
            se = res['residual_stdev'] * math.sqrt(float(h_val))
            delta_ci = quantile * se
            delta_pi = quantile * res['residual_stdev'] * math.sqrt(1.0 + float(h_val))
            out.append(dict(
                fit=fit_f,
                se_fit=float(se),
                ci_low=float(fit_f - delta_ci) if side != 'upper' else None,
                ci_high=float(fit_f + delta_ci) if side != 'lower' else None,
                pi_low=float(fit_f - delta_pi) if side != 'upper' else None,
                pi_high=float(fit_f + delta_pi) if side != 'lower' else None,
            ))
    return out


def default_desirability(worksheet, model_recipe, goal='maximize', target=None):
    """Compute default Lower, Target, Upper, Weight and Importance for a response model."""
    if goal not in GOALS:
        raise ValueError('Choose Do not optimize, Minimize, Target or Maximize.')
    bundle = _fit_model_bundle(worksheet, model_recipe)
    obs_min = bundle['observed_min']
    obs_max = bundle['observed_max']
    is_prob = bundle['is_probability']
    if goal == 'none':
        return dict(
            goal='none',
            lower=None,
            target=None,
            upper=None,
            weight=1.0,
            importance=1.0,
            observed_min=obs_min,
            observed_max=obs_max,
            is_probability=is_prob,
        )
    if goal == 'minimize':
        t = obs_min if target is None else finite_number(target)
        if is_prob and not 0.0 < t < 1.0:
            t = max(1e-4, min(0.999, t))
        u = obs_max if obs_max > t else (min(0.9999, t + 0.1 * (1.0 - t)) if is_prob else t + 0.1 * max(1.0, abs(t)))
        return dict(goal='minimize', lower=None, target=float(t), upper=float(u),
                    weight=1.0, importance=1.0, observed_min=obs_min, observed_max=obs_max, is_probability=is_prob)
    if goal == 'maximize':
        t = obs_max if target is None else finite_number(target)
        if is_prob and not 0.0 < t < 1.0:
            t = max(0.001, min(0.9999, t))
        l = obs_min if obs_min < t else (max(0.0001, t - 0.1 * t) if is_prob else t - 0.1 * max(1.0, abs(t)))
        return dict(goal='maximize', lower=float(l), target=float(t), upper=None,
                    weight=1.0, importance=1.0, observed_min=obs_min, observed_max=obs_max, is_probability=is_prob)
    # goal == 'target'
    if target is None:
        t = 0.5 if is_prob else 0.5 * (obs_min + obs_max)
    else:
        t = finite_number(target)
    if is_prob:
        if not 0.0 < t < 1.0:
            raise ValueError('Target probability for binary logistic optimization must lie strictly between 0 and 1.')
        l = min(obs_min, t - 0.1 * t)
        u = max(obs_max, t + 0.1 * (1.0 - t))
        if l >= t:
            l = 0.5 * t
        if u <= t:
            u = t + 0.5 * (1.0 - t)
    else:
        span = 0.1 * abs(t) if t != 0 else 0.1 * max(1.0, obs_max - obs_min)
        l = min(obs_min, t - span)
        u = max(obs_max, t + span)
    return dict(goal='target', lower=float(l), target=float(t), upper=float(u),
                weight=1.0, importance=1.0, observed_min=obs_min, observed_max=obs_max, is_probability=is_prob)


def normalize_response_spec(worksheet, item):
    """Validate and normalize one response optimization entry."""
    if not isinstance(item, dict):
        raise ValueError('Each response specification must be a dictionary.')
    allowed = {'model_recipe', 'goal', 'lower', 'target', 'upper', 'weight', 'importance'}
    if not {'model_recipe', 'goal'} <= set(item) or not set(item) <= allowed:
        raise ValueError('Response specification requires model_recipe and goal.')
    recipe = normalize_model_recipe(item['model_recipe'])
    goal = item['goal']
    if goal not in ('minimize', 'target', 'maximize'):
        raise ValueError('Active response optimization goal must be minimize, target or maximize.')
    bundle = _fit_model_bundle(worksheet, recipe)
    defaults = default_desirability(worksheet, recipe, goal=goal, target=item.get('target'))
    weight = finite_number(item.get('weight', 1.0))
    importance = finite_number(item.get('importance', 1.0))
    if not 0.1 <= weight <= 10.0 or not 0.1 <= importance <= 10.0:
        raise ValueError('Desirability weight and importance must lie between 0.1 and 10.')
    t = defaults['target'] if item.get('target') is None else finite_number(item['target'])
    if bundle['is_probability'] and not 0.0 < t < 1.0:
        raise ValueError('Binary logistic target probability must be strictly between 0 and 1.')
    if goal == 'minimize':
        if item.get('lower') is not None:
            raise ValueError('Minimize goal does not accept a lower bound.')
        l = None
        u = defaults['upper'] if item.get('upper') is None else finite_number(item['upper'])
        if t >= u:
            raise ValueError(f"{bundle['response_name']}: Target must be strictly less than Upper for Minimize.")
        if bundle['is_probability'] and u > 1.0:
            raise ValueError(f"{bundle['response_name']}: Upper probability bound cannot exceed 1.")
    elif goal == 'maximize':
        if item.get('upper') is not None:
            raise ValueError('Maximize goal does not accept an upper bound.')
        u = None
        l = defaults['lower'] if item.get('lower') is None else finite_number(item['lower'])
        if l >= t:
            raise ValueError(f"{bundle['response_name']}: Lower must be strictly less than Target for Maximize.")
        if bundle['is_probability'] and l < 0.0:
            raise ValueError(f"{bundle['response_name']}: Lower probability bound cannot be negative.")
    else:
        l = defaults['lower'] if item.get('lower') is None else finite_number(item['lower'])
        u = defaults['upper'] if item.get('upper') is None else finite_number(item['upper'])
        if not l < t < u:
            raise ValueError(f"{bundle['response_name']}: Target must lie strictly between Lower and Upper.")
        if bundle['is_probability'] and (l < 0.0 or u > 1.0):
            raise ValueError(f"{bundle['response_name']}: Probability bounds must lie within [0, 1].")
    return dict(
        model_recipe=recipe,
        goal=goal,
        lower=l,
        target=t,
        upper=u,
        weight=weight,
        importance=importance,
    ), bundle


def discover_models(worksheet, history, family=None):
    """Discover the latest valid fitted model per response column on the active worksheet."""
    family_map = {
        'regression': ('multiple_regression',),
        'glm': ('general_linear_model',),
        'response_surface': ('analyze_response_surface',),
        'logistic': ('fit_binary_logistic',),
        'factorial': ('analyze_factorial', 'analyze_factorial_terms'),
    }
    allowed_actions = family_map.get(family)
    by_response = {}
    ordered_responses = []
    for entry in history:
        if not isinstance(entry, dict) or entry.get('source_unavailable'):
            continue
        from .native_mpx_models import resolve_entry_recipe
        raw_recipe = resolve_entry_recipe(entry, worksheet)
        if not isinstance(raw_recipe, dict):
            continue
        candidates = []
        act = raw_recipe.get('action')
        if act == 'predict_model':
            candidates.append(raw_recipe.get('parameters', {}).get('model_recipe'))
        elif act == 'optimize_responses':
            for r_item in raw_recipe.get('parameters', {}).get('responses', []):
                if isinstance(r_item, dict):
                    candidates.append(r_item.get('model_recipe'))
        else:
            candidates.append(raw_recipe)
        for cand in candidates:
            try:
                recipe = normalize_model_recipe(cand)
                if allowed_actions and recipe['action'] not in allowed_actions:
                    continue
                bundle = _fit_model_bundle(worksheet, recipe)
            except (ValueError, TypeError, KeyError, IndexError, ArithmeticError):
                continue
            resp_idx = bundle['response_index']
            if resp_idx not in by_response:
                ordered_responses.append(resp_idx)
            by_response[resp_idx] = dict(
                entry=entry,
                recipe=recipe,
                bundle=bundle,
                response_index=resp_idx,
                response_name=bundle['response_name'],
                model_title=bundle['model_title'],
            )
    return [by_response[idx] for idx in ordered_responses]


def _merge_predictors(bundles, options):
    """Merge predictors across all active models and apply constraints/starting values."""
    response_indices = {b['response_index'] for b in bundles}
    merged = {}
    order = []
    for b in bundles:
        for p in b['predictors']:
            idx = p['index']
            if idx in response_indices:
                raise ValueError('A response column cannot also be a predictor in the optimized models.')
            if idx not in merged:
                order.append(idx)
                merged[idx] = dict(
                    index=idx,
                    name=p['name'],
                    kind=p['kind'],
                    role=p['role'],
                    levels=list(p['levels']),
                    observed_min=p['min'],
                    observed_max=p['max'],
                )
            else:
                cur = merged[idx]
                if cur['role'] != p['role'] or cur['kind'] != p['kind']:
                    raise ValueError(f"Predictor {p['name']} has incompatible roles across models.")
                if cur['role'] == 'factor':
                    common = [lvl for lvl in cur['levels'] if lvl in p['levels']]
                    if not common:
                        raise ValueError(f"Factor {p['name']} has no common levels across models.")
                    cur['levels'] = common
                else:
                    cur['observed_min'] = min(cur['observed_min'], p['min'])
                    cur['observed_max'] = max(cur['observed_max'], p['max'])
    constraints_by_idx = {c['index']: c for c in options['constraints']}
    starts_by_idx = {s['index']: s['value'] for s in options['starting_values']}
    unknown_c = set(constraints_by_idx) - set(merged)
    if unknown_c:
        raise ValueError('Constraint references a column that is not an active model predictor.')
    unknown_s = set(starts_by_idx) - set(merged)
    if unknown_s:
        raise ValueError('Starting value references a column that is not an active model predictor.')
    predictors = []
    for idx in order:
        info = merged[idx]
        c = constraints_by_idx.get(idx, dict(index=idx, mode='none', value=None, lower=None, upper=None))
        mode = c['mode']
        if info['role'] == 'factor':
            if mode == 'region':
                raise ValueError(f"Categorical factor {info['name']} supports Hold at value or No constraints, not region bounds.")
            if mode == 'hold':
                if c['value'] not in info['levels']:
                    raise ValueError(f"Hold value for {info['name']} must be an observed factor level.")
                active_levels = [c['value']]
                lo, hi = c['value'], c['value']
            else:
                active_levels = list(info['levels'])
                lo, hi = active_levels[0], active_levels[-1]
            start_val = starts_by_idx.get(idx, active_levels[0])
            if start_val not in active_levels:
                if mode == 'hold':
                    start_val = active_levels[0]
                else:
                    raise ValueError(f"Starting value for {info['name']} must be an allowed factor level.")
            predictors.append(dict(
                index=idx,
                name=info['name'],
                kind=info['kind'],
                role='factor',
                constraint_mode=mode,
                hold_value=c['value'] if mode == 'hold' else None,
                lower=lo,
                upper=hi,
                observed_min=None,
                observed_max=None,
                levels=list(info['levels']),
                active_levels=active_levels,
                starting_value=start_val,
            ))
        else:
            obs_lo, obs_hi = info['observed_min'], info['observed_max']
            if mode == 'hold':
                if isinstance(c['value'], str):
                    raise ValueError(f"Hold value for continuous predictor {info['name']} must be numeric.")
                hold_v = finite_number(c['value'])
                lo = hi = hold_v
            elif mode == 'region':
                lo, hi = c['lower'], c['upper']
            else:
                lo, hi = obs_lo, obs_hi
            if idx in starts_by_idx:
                sv = starts_by_idx[idx]
                if isinstance(sv, str):
                    raise ValueError(f"Starting value for continuous predictor {info['name']} must be numeric.")
                start_val = finite_number(sv)
                if mode == 'hold':
                    start_val = lo
                elif not lo <= start_val <= hi:
                    raise ValueError(f"Starting value for {info['name']} must lie within [{lo:g}, {hi:g}].")
            else:
                start_val = lo if mode == 'hold' else 0.5 * (lo + hi)
            predictors.append(dict(
                index=idx,
                name=info['name'],
                kind=info['kind'],
                role='covariate',
                constraint_mode=mode,
                hold_value=lo if mode == 'hold' else None,
                lower=float(lo),
                upper=float(hi),
                observed_min=float(obs_lo),
                observed_max=float(obs_hi),
                levels=[],
                active_levels=[],
                starting_value=float(start_val),
            ))
    return predictors


def optimize(worksheet, responses, options=None):
    """Optimize one or more fitted responses on the current worksheet."""
    o = settings(options)
    if not isinstance(responses, list) or not 1 <= len(responses) <= 8:
        raise ValueError('Select 1 to 8 fitted responses to optimize.')
    norm_responses = []
    bundles = []
    seen_resp = set()
    for item in responses:
        spec, bundle = normalize_response_spec(worksheet, item)
        r_idx = bundle['response_index']
        if r_idx in seen_resp:
            raise ValueError(f"Duplicate response in optimization: {bundle['response_name']}.")
        seen_resp.add(r_idx)
        norm_responses.append(spec)
        bundles.append(bundle)
    predictors = _merge_predictors(bundles, o)
    pred_pos = {p['index']: j for j, p in enumerate(predictors)}
    bundle_pred_positions = [[pred_pos[p['index']] for p in b['predictors']] for b in bundles]

    cont_indices = [j for j, p in enumerate(predictors) if p['role'] == 'covariate' and p['constraint_mode'] != 'hold']
    cat_Editable = [j for j, p in enumerate(predictors) if p['role'] == 'factor']
    cat_level_lists = [predictors[j]['active_levels'] for j in cat_Editable]
    total_cat_combos = math.prod((len(lvls) for lvls in cat_level_lists), start=1)
    if total_cat_combos > MAX_CATEGORICAL_COMBINATIONS:
        raise ValueError(f'Categorical factor combinations ({total_cat_combos}) exceed the {MAX_CATEGORICAL_COMBINATIONS} limit; hold one or more factors.')

    importances = [r['importance'] for r in norm_responses]
    total_importance = math.fsum(importances)

    def build_full_setting(cont_vec, cat_combo):
        row = [p['starting_value'] for p in predictors]
        for j, p in enumerate(predictors):
            if p['constraint_mode'] == 'hold':
                row[j] = p['hold_value']
        for k, j in enumerate(cat_Editable):
            row[j] = cat_combo[k]
        for k, j in enumerate(cont_indices):
            row[j] = float(cont_vec[k])
        return row

    def evaluate_candidates(full_rows):
        all_preds = []
        for b, pos_list in zip(bundles, bundle_pred_positions):
            sub_rows = [[row[pos] for pos in pos_list] for row in full_rows]
            preds = _predict_bundle_rows(b, sub_rows, compute_intervals=False)
            all_preds.append([item['fit'] for item in preds])
        results = []
        for r_i, row in enumerate(full_rows):
            fits = [all_preds[m_i][r_i] for m_i in range(len(bundles))]
            d_list = [
                individual_desirability(fits[m_i], r_spec['goal'], r_spec['lower'], r_spec['target'], r_spec['upper'], r_spec['weight'])
                for m_i, r_spec in enumerate(norm_responses)
            ]
            comp_d = composite_desirability(d_list, importances)
            # Smooth tie-breaker / guidance penalty when comp_d == 0
            penalty = 0.0
            tie = 0.0
            for y_hat, r_spec in zip(fits, norm_responses):
                w = r_spec['importance'] / total_importance
                t = r_spec['target']
                scale = max(1e-6, (r_spec['upper'] if r_spec['upper'] is not None else t) - (r_spec['lower'] if r_spec['lower'] is not None else t))
                if r_spec['goal'] == 'minimize':
                    if y_hat >= r_spec['upper']:
                        penalty += w * ((y_hat - r_spec['upper']) / scale + 1.0) ** 2
                    tie += w * max(0.0, (y_hat - t) / scale) ** 2
                elif r_spec['goal'] == 'maximize':
                    if y_hat <= r_spec['lower']:
                        penalty += w * ((r_spec['lower'] - y_hat) / scale + 1.0) ** 2
                    tie += w * max(0.0, (t - y_hat) / scale) ** 2
                else:
                    if y_hat <= r_spec['lower']:
                        penalty += w * ((r_spec['lower'] - y_hat) / scale + 1.0) ** 2
                    elif y_hat >= r_spec['upper']:
                        penalty += w * ((y_hat - r_spec['upper']) / scale + 1.0) ** 2
                    tie += w * ((y_hat - t) / scale) ** 2
            score = -comp_d + 1e-12 * tie if comp_d > 0.0 else 1.0 + penalty + 1e-3 * tie
            results.append(dict(
                setting=list(row),
                fits=fits,
                desirabilities=d_list,
                composite_desirability=comp_d,
                score=score,
            ))
        return results

    # Build continuous seed points inside bounds [lower, upper]
    k_cont = len(cont_indices)
    cont_bounds = [(predictors[j]['lower'], predictors[j]['upper']) for j in cont_indices]
    cont_seeds = []
    if k_cont > 0:
        user_start = [predictors[j]['starting_value'] for j in cont_indices]
        mid_start = [0.5 * (lo + hi) for lo, hi in cont_bounds]
        cont_seeds.append(user_start)
        if mid_start != user_start:
            cont_seeds.append(mid_start)
        # Add corner combinations (or subset if k_cont > 5)
        if k_cont <= 5:
            for bits in itertools.product((0.0, 1.0), repeat=k_cont):
                cont_seeds.append([lo + b * (hi - lo) for (lo, hi), b in zip(cont_bounds, bits)])
            if k_cont <= 3:
                for bits in itertools.product((0.0, 0.25, 0.5, 0.75, 1.0), repeat=k_cont):
                    cont_seeds.append([lo + b * (hi - lo) for (lo, hi), b in zip(cont_bounds, bits)])
        else:
            for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
                cont_seeds.append([lo + frac * (hi - lo) for lo, hi in cont_bounds])
            for dim in range(k_cont):
                for end in (0.0, 1.0):
                    pt = list(mid_start)
                    pt[dim] = cont_bounds[dim][0] + end * (cont_bounds[dim][1] - cont_bounds[dim][0])
                    cont_seeds.append(pt)
        # Deterministic Halton-like interior points
        primes = (2, 3, 5, 7, 11, 13, 17, 19)
        for idx_pt in range(1, 25):
            pt = []
            for d_i, (lo, hi) in enumerate(cont_bounds):
                base = primes[d_i % len(primes)]
                f = 1.0
                r_v = 0.0
                n_v = idx_pt
                while n_v > 0:
                    f /= base
                    r_v += f * (n_v % base)
                    n_v //= base
                pt.append(lo + r_v * (hi - lo))
            cont_seeds.append(pt)
    else:
        cont_seeds.append([])

    polished_candidates = []
    cat_combinations = list(itertools.product(*cat_level_lists)) if cat_Editable else [()]

    for cat_combo in cat_combinations:
        seed_rows = [build_full_setting(vec, cat_combo) for vec in cont_seeds]
        evaluated = evaluate_candidates(seed_rows)
        evaluated.sort(key=lambda item: item['score'])
        if k_cont == 0:
            polished_candidates.append(evaluated[0])
            continue
        top_seeds = [evaluated[0]]
        for cand in evaluated[1:]:
            if len(top_seeds) >= 6:
                break
            vec_c = [cand['setting'][j] for j in cont_indices]
            if all(max(abs(vec_c[d] - s['setting'][cont_indices[d]]) / max(1e-9, cont_bounds[d][1] - cont_bounds[d][0]) for d in range(k_cont)) > 0.08 for s in top_seeds):
                top_seeds.append(cand)
        for seed in top_seeds:
            x0 = np.asarray([seed['setting'][j] for j in cont_indices], dtype=float)
            def obj(x_vec):
                clipped = [min(cont_bounds[d][1], max(cont_bounds[d][0], float(x_vec[d]))) for d in range(k_cont)]
                return evaluate_candidates([build_full_setting(clipped, cat_combo)])[0]['score']
            res_lbfgs = sp_optimize.minimize(obj, x0, method='L-BFGS-B', bounds=cont_bounds, options=dict(maxiter=120, ftol=1e-12))
            best_x = np.clip(res_lbfgs.x, [b[0] for b in cont_bounds], [b[1] for b in cont_bounds])
            res_nm = sp_optimize.minimize(obj, best_x, method='Nelder-Mead', bounds=cont_bounds, options=dict(maxiter=160, xatol=1e-8, fatol=1e-11))
            final_x = np.clip(res_nm.x, [b[0] for b in cont_bounds], [b[1] for b in cont_bounds])
            polished_candidates.extend(evaluate_candidates([
                build_full_setting(best_x.tolist(), cat_combo),
                build_full_setting(final_x.tolist(), cat_combo),
            ]))
            polished_candidates.append(seed)

    polished_candidates.sort(key=lambda item: (-item['composite_desirability'], item['score']))
    unique_solutions = []
    for cand in polished_candidates:
        is_dup = False
        for existing in unique_solutions:
            same_cat = all(cand['setting'][j] == existing['setting'][j] for j in cat_Editable)
            if not same_cat:
                continue
            if k_cont == 0:
                is_dup = True
                break
            max_diff = max(
                abs(cand['setting'][j] - existing['setting'][j]) / max(1e-9, predictors[j]['upper'] - predictors[j]['lower'])
                for j in cont_indices
            )
            if max_diff < 1e-3:
                is_dup = True
                break
        if not is_dup:
            unique_solutions.append(cand)
        if len(unique_solutions) >= o['max_solutions']:
            break

    best = unique_solutions[0]
    starting_row = [p['starting_value'] for p in predictors]
    starting_eval = evaluate_candidates([starting_row])[0]

    # Compute detailed predictions + intervals at the best solution
    optimal_predictions = []
    warnings = []
    for m_i, (r_spec, b, pos_list) in enumerate(zip(norm_responses, bundles, bundle_pred_positions)):
        for w_msg in b['warnings']:
            if w_msg not in warnings:
                warnings.append(w_msg)
        sub_row = [best['setting'][pos] for pos in pos_list]
        pred_detail = _predict_bundle_rows(b, [sub_row], confidence=o['confidence'], side=o['side'], compute_intervals=True)[0]
        extrap = any(
            p['role'] == 'covariate' and not (p['min'] <= best['setting'][pred_pos[p['index']]] <= p['max'])
            for p in b['predictors']
        )
        if extrap and 'Some optimal settings lie outside the observed training range; predictions are extrapolations.' not in warnings:
            warnings.append('Some optimal settings lie outside the observed training range; predictions are extrapolations.')
        optimal_predictions.append(dict(
            response_index=b['response_index'],
            response_name=b['response_name'],
            model_action=b['action'],
            model_title=b['model_title'],
            is_probability=b['is_probability'],
            event=b['event'],
            goal=r_spec['goal'],
            lower=r_spec['lower'],
            target=r_spec['target'],
            upper=r_spec['upper'],
            weight=r_spec['weight'],
            importance=r_spec['importance'],
            fit=pred_detail['fit'],
            se_fit=pred_detail['se_fit'],
            ci_low=pred_detail['ci_low'],
            ci_high=pred_detail['ci_high'],
            pi_low=pred_detail['pi_low'],
            pi_high=pred_detail['pi_high'],
            desirability=best['desirabilities'][m_i],
            extrapolated=extrap,
        ))

    if best['composite_desirability'] <= 0.0:
        warnings.append('Composite desirability is zero at the best found setting; relax response bounds or variable constraints.')

    # Build 1D Optimization Plot profile curves across each predictor
    profiles = []
    for j, p in enumerate(predictors):
        if p['role'] == 'factor':
            x_vals = list(p['levels'])
        else:
            lo = p['observed_min'] if p['constraint_mode'] == 'hold' else p['lower']
            hi = p['observed_max'] if p['constraint_mode'] == 'hold' else p['upper']
            if lo >= hi:
                delta = max(1.0, abs(lo) * 0.1)
                lo, hi = lo - delta, hi + delta
            grid = [lo + (hi - lo) * i / (PROFILE_GRID_POINTS - 1) for i in range(PROFILE_GRID_POINTS)]
            cur_v = float(best['setting'][j])
            if all(abs(cur_v - g) > 1e-12 for g in grid) and lo <= cur_v <= hi:
                grid.append(cur_v)
                grid.sort()
            x_vals = grid
        sweep_rows = []
        for xv in x_vals:
            row = list(best['setting'])
            row[j] = xv
            sweep_rows.append(row)
        sweep_eval = evaluate_candidates(sweep_rows)
        resp_curves = []
        for m_i, b in enumerate(bundles):
            resp_curves.append(dict(
                response_name=b['response_name'],
                goal=norm_responses[m_i]['goal'],
                target=norm_responses[m_i]['target'],
                lower=norm_responses[m_i]['lower'],
                upper=norm_responses[m_i]['upper'],
                y_fit=best['fits'][m_i],
                d_optimal=best['desirabilities'][m_i],
                fits=[item['fits'][m_i] for item in sweep_eval],
                desirabilities=[item['desirabilities'][m_i] for item in sweep_eval],
            ))
        profiles.append(dict(
            index=p['index'],
            name=p['name'],
            kind=p['kind'],
            role=p['role'],
            constraint_mode=p['constraint_mode'],
            low=p['lower'] if p['role'] == 'covariate' else p['levels'][0],
            high=p['upper'] if p['role'] == 'covariate' else p['levels'][-1],
            current=best['setting'][j],
            x=x_vals,
            composite_desirability=[item['composite_desirability'] for item in sweep_eval],
            responses=resp_curves,
        ))

    parameters_table = [
        dict(
            response_index=b['response_index'],
            response_name=b['response_name'],
            model_title=b['model_title'],
            is_probability=b['is_probability'],
            event=b['event'],
            goal=r_spec['goal'],
            lower=r_spec['lower'],
            target=r_spec['target'],
            upper=r_spec['upper'],
            weight=r_spec['weight'],
            importance=r_spec['importance'],
        )
        for r_spec, b in zip(norm_responses, bundles)
    ]

    solutions_table = [
        dict(
            rank=idx + 1,
            settings=list(sol['setting']),
            fits=list(sol['fits']),
            desirabilities=list(sol['desirabilities']),
            composite_desirability=sol['composite_desirability'],
        )
        for idx, sol in enumerate(unique_solutions)
    ]

    result = dict(
        analysis='response_optimizer',
        title='Response Optimization: ' + ', '.join(b['response_name'] for b in bundles),
        responses=norm_responses,
        parameters=parameters_table,
        predictors=predictors,
        predictor_names=[p['name'] for p in predictors],
        predictor_indices=[p['index'] for p in predictors],
        response_names=[b['response_name'] for b in bundles],
        starting_point=dict(
            settings=starting_row,
            fits=starting_eval['fits'],
            desirabilities=starting_eval['desirabilities'],
            composite_desirability=starting_eval['composite_desirability'],
        ),
        solutions=solutions_table,
        optimal_settings=list(best['setting']),
        optimal_composite_desirability=best['composite_desirability'],
        predictions=optimal_predictions,
        profiles=profiles,
        options=o,
        warnings=warnings,
        method='Derringer-Suich desirability optimization over current-worksheet refitted models',
        methodnotes=(
            'Source models are refitted using current worksheet values. Individual desirabilities use '
            'Derringer-Suich power transformations; composite desirability is their importance-weighted '
            'geometric mean. Continuous settings are searched via deterministic multi-start L-BFGS-B and '
            'Nelder-Mead across each allowed categorical level combination. Native-product numerical '
            'equivalence is unverified.'
        ),
        assumptions=(
            'Source models are refitted using current worksheet values. Individual desirabilities use '
            'Derringer-Suich power transformations; composite desirability is their importance-weighted '
            'geometric mean. Pointwise intervals at the optimal setting use each source model\'s inference '
            'scale. Native-product numerical equivalence is unverified.'
        ),
    )
    return _finite_result(result)
