"""Independent bounded binary logit models, likelihood inference and predictions.

Reference equations: https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/regression/how-to/fit-binary-logistic-model/methods-and-formulas/estimated-equation/
Uses reference contrasts and safeguarded maximum likelihood, without proprietary
code. Native-product numerical equivalence has not been established.
"""
import itertools
import math
import numpy as np
from scipy import stats, special, optimize
from .glm import validate_terms
from .model import finite_number
from .value_order import ordered_values

DEFAULTS = dict(confidence=.95, graphs='none', threshold=.5, method=True,
    response_information=True, model_summary=True, coefficients=True,
    odds_ratios=True, equation=True, diagnostics='unusual')


def _finite_result(value):
    """Ensure every derived numeric value is JSON-safe, including diagnostics."""
    if isinstance(value, dict):
        for child in value.values():_finite_result(child)
    elif isinstance(value, (list, tuple)):
        for child in value:_finite_result(child)
    elif isinstance(value, (float, np.floating)) and not math.isfinite(value):
        raise ValueError('Logistic result arithmetic exceeds supported finite precision; rescale predictors or simplify the model.')
    return value


def settings(options=None):
    if options is None:
        return dict(DEFAULTS)
    if not isinstance(options, dict) or set(options) != set(DEFAULTS):
        raise ValueError('Unsupported binary logistic options.')
    o = dict(options)
    for k in ('confidence', 'threshold'):
        if type(o[k]) not in (int, float) or not math.isfinite(o[k]) or not 0 < o[k] < 1:
            raise ValueError(k.capitalize()+' must be strictly between zero and one.')
    if o['graphs'] not in ('none', 'four'):
        raise ValueError('Choose no graphs or four residual plots.')
    for key in ('method','response_information','model_summary','coefficients','odds_ratios','equation'):
        if type(o[key]) is not bool:raise ValueError('Choose valid logistic result display settings.')
    if o['diagnostics'] not in ('none','unusual','all'):raise ValueError('Choose valid diagnostic display settings.')
    return o


def _encode(inputs, coding, terms):
    blocks = []
    for j, info in enumerate(coding):
        values = [r[j] for r in inputs]
        if info['kind'] == 'factor':
            blocks.append([np.asarray([float(v == level) for v in values]) for level in info['levels'][:-1]])
        else:
            blocks.append([np.asarray(values, dtype=float)])
    encoded = []
    for term in terms:
        for combination in itertools.product(*(range(len(blocks[i])) for i in term)):
            product = np.ones(len(inputs))
            for i, j in zip(term, combination):
                product *= blocks[i][j]
            encoded.append(product)
    result = np.column_stack([np.ones(len(inputs))]+encoded)
    if not np.all(np.isfinite(result)):
        raise ValueError('Interaction arithmetic exceeds the supported finite range.')
    return result


def _roc(probabilities, successes, trials):
    positive = float(sum(successes)); negative = float(sum(trials-successes))
    groups = {}
    for p, y, m in zip(probabilities, successes, trials):
        a, b = groups.get(float(p), (0., 0.)); groups[float(p)] = (a+float(y), b+float(m-y))
    curve = [dict(threshold=None, sensitivity=0., specificity=1., false_positive_rate=0., tpr=0., fpr=0.)]
    tp = fp = area = 0.; prev_x = prev_y = 0.
    for p in sorted(groups, reverse=True):
        a, b = groups[p]; tp += a; fp += b; x = fp/negative; y = tp/positive
        area += (x-prev_x)*(y+prev_y)/2; prev_x, prev_y = x, y
        curve.append(dict(threshold=p, sensitivity=y, specificity=1-x, false_positive_rate=x, tpr=y, fpr=x))
    return curve, area


def _solve(z, y, m):
    """Reject complete/quasi separation, then use backtracked Newton steps."""
    pure = (y == 0) | (y == m); mixed = ~pure
    if np.any(pure):
        a = z[pure]*np.where(y[pure] == 0, -1., 1.)[:, None]
        # A nonzero sum of nonnegative margins certifies a likelihood recession
        # direction. Mixed binomial rows require zero linear-predictor change.
        lp = optimize.linprog(-np.sum(a, axis=0), A_ub=-a, b_ub=np.zeros(len(a)),
            A_eq=z[mixed] if np.any(mixed) else None,
            b_eq=np.zeros(np.sum(mixed)) if np.any(mixed) else None,
            bounds=[(-1., 1.)]*z.shape[1], method='highs')
        if not lp.success:
            raise ValueError('Separation screening could not establish a finite logistic model.')
        if -lp.fun > 1e-7:
            raise ValueError('Complete or quasi-complete separation: finite maximum-likelihood coefficients do not exist. Change the model or supply overlapping outcomes.')
    b = np.zeros(z.shape[1]); b[0] = math.log(float(sum(y))/float(sum(m-y)))
    def objective(beta):
        eta = z@beta
        return float(np.sum(y*eta-m*np.logaddexp(0., eta)))
    ll = objective(b)
    for iteration in range(1, 101):
        eta = z@b; p = special.expit(eta); w = m*p*special.expit(-eta)
        h = (z.T*w)@z; grad = z.T@(y-m*p)
        try:
            step = np.linalg.solve(h, grad)
        except np.linalg.LinAlgError as exc:
            raise ValueError('Logistic information matrix is singular; reduce the model.') from exc
        factor = 1.
        for _ in range(45):
            candidate = b+factor*step; proposed = objective(candidate)
            if math.isfinite(proposed) and proposed >= ll-1e-10:
                break
            factor *= .5
        else:
            raise ValueError('Logistic model failed its safeguarded likelihood solve.')
        delta = float(np.max(np.abs(z@(factor*step)))); b = candidate; ll = proposed
        if delta < 1e-9:
            break
    else:
        raise ValueError('Logistic model did not converge within 100 iterations.')
    p = special.expit(z@b); w = m*p*special.expit(-z@b); h = (z.T*w)@z
    singular = np.linalg.svd(h, compute_uv=False)
    if singular[-1] <= singular[0]*1e-12 or np.max(np.abs(z@b)) > 35:
        raise ValueError('Logistic estimates are numerically unstable or near separation; reduce the model.')
    covariance = np.linalg.solve(h, np.eye(len(b)))
    if not np.all(np.isfinite(covariance)):
        raise ValueError('Logistic uncertainty could not be calculated in finite precision.')
    return b, covariance, iteration


def fit(worksheet, response_index, continuous_indices, categorical_indices,
        event=None, trials_index=None, terms=None, options=None):
    o = settings(options)
    if not isinstance(continuous_indices, list) or not isinstance(categorical_indices, list):
        raise ValueError('Choose predictor column lists.')
    indices = list(categorical_indices)+list(continuous_indices)
    used = indices+[response_index]+([] if trials_index is None else [trials_index])
    if not 1 <= len(indices) <= 8 or len(set(used)) != len(used) or any(type(i) is not int or not 0 <= i < len(worksheet.columns) for i in used):
        raise ValueError('Choose a separate response, optional trials and 1–8 distinct predictors.')
    response = worksheet.columns[response_index]; cols = [worksheet.columns[i] for i in indices]
    if response.kind not in ('number', 'text') or any(worksheet.columns[i].kind != 'number' for i in continuous_indices) or any(c.kind not in ('number', 'text') for c in cols):
        raise ValueError('Use numeric covariates and numeric or text categorical predictors/response.')
    if trials_index is not None and (response.kind != 'number' or worksheet.columns[trials_index].kind != 'number' or event is not None):
        raise ValueError('Event/trial data require numeric counts and no response event category.')
    terms = validate_terms(terms if terms is not None else [[i] for i in range(len(indices))], len(indices))
    if sorted({i for term in terms for i in term}) != list(range(len(indices))):
        raise ValueError('Include each selected predictor in the model or remove its selection.')
    allcols = [worksheet.columns[i] for i in used]
    for column in allcols:column.validate()
    length = max(len(c.values) for c in allcols)
    if length > 20000:
        raise ValueError('Binary logistic regression supports at most 20,000 source rows.')
    rows = [r for r in range(length) if all(r < len(c.values) and c.values[r] is not None for c in allcols)]
    if not rows:
        raise ValueError('No complete model observations remain.')
    observed = [response.values[r] for r in rows]
    non_event = None
    if trials_index is None:
        levels = ordered_values(response, observed)
        if len(levels) != 2:
            raise ValueError('A binary response must have exactly two observed categories after missing-row omission.')
        if event is None:
            event = levels[-1]
        elif event not in levels or isinstance(event, bool):
            raise ValueError('The selected event must be an observed response category.')
        non_event = next(v for v in levels if v != event)
        y = np.asarray([float(v == event) for v in observed]); m = np.ones(len(rows))
    else:
        y = np.asarray(observed, dtype=float); m = np.asarray([worksheet.columns[trials_index].values[r] for r in rows], dtype=float)
        if not np.all(np.isfinite(y)) or not np.all(np.isfinite(m)) or np.any(y < 0) or np.any(m <= 0) or np.any(y > m) or np.any(m > 1e9) or np.any(y != np.floor(y)) or np.any(m != np.floor(m)):
            raise ValueError('Events/trials must be whole counts: 0 ≤ events ≤ trials, with 1–1,000,000,000 trials per row.')
    if not 0 < sum(y) < sum(m):
        raise ValueError('Both events and non-events must occur in the model data.')
    coding = []; factor_info = []; basis = []
    for j, c in enumerate(cols):
        values = [c.values[r] for r in rows]
        if j < len(categorical_indices):
            levels = ordered_values(c, values)
            if not 2 <= len(levels) <= 32:
                raise ValueError('Categorical predictors need 2–32 observed levels: '+c.name)
            coding.append(dict(name=c.name, kind='factor', levels=levels, reference=levels[-1], shift=0., scale=1.))
            factor_info.append(dict(factor=c.name, type='Fixed', levels=len(levels), values=', '.join(map(str, levels)), reference=str(levels[-1])))
            basis.append([c.name+'['+str(level)+']' for level in levels[:-1]])
        else:
            coding.append(dict(name=c.name, kind='covariate', shift=0., scale=1.)); basis.append([c.name])
    width = 1+sum(math.prod(len(basis[j]) for j in term) for term in terms)
    if width > 121 or len(rows)*width > 2000000:
        raise ValueError('Model expansion exceeds 120 predictor coefficients or two million design cells.')
    train = [[c.values[r] for c in cols] for r in rows]
    with np.errstate(over='ignore', invalid='ignore'):
        x = _encode(train, coding, terms)
    centers = np.asarray([math.fsum(x[:, j]/len(rows)) for j in range(1, width)])
    scales = np.max(np.abs(x[:, 1:]-centers), axis=0)
    if np.any(scales <= 0) or not np.all(np.isfinite(scales)):
        raise ValueError('A predictor or interaction has no supported variation.')
    z = np.column_stack([np.ones(len(rows)), (x[:, 1:]-centers)/scales])
    singular = np.linalg.svd(z, compute_uv=False)
    if len(singular) < width or singular[-1] <= singular[0]*1e-10:
        raise ValueError('Model is rank deficient or numerically ill-conditioned; remove redundant terms.')
    gamma, cov, iterations = _solve(z, y, m)
    transform = np.eye(width); transform[0, 1:] = -centers/scales
    transform[1:, 1:] = np.diag(1/scales)
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        beta = transform@gamma; covariance = transform@cov@transform.T
    if not np.all(np.isfinite(beta)) or not np.all(np.isfinite(covariance)) or np.any(np.diag(covariance)<=0):
        raise ValueError('Coefficient uncertainty exceeds supported finite precision; rescale the continuous predictors.')
    eta = z@gamma; p = special.expit(eta); q = special.expit(-eta)
    logconstant = special.gammaln(m+1)-special.gammaln(y+1)-special.gammaln(m-y+1)
    ll = float(sum(logconstant+y*(-np.logaddexp(0., -eta))+(m-y)*(-np.logaddexp(0., eta))))
    p0 = float(sum(y)/sum(m))
    null_ll = float(sum(logconstant+y*math.log(p0)+(m-y)*math.log1p(-p0)))
    ll_saturated = float(sum(logconstant+special.xlogy(y, y/m)+special.xlogy(m-y, (m-y)/m)))
    deviance = max(0., 2*(ll_saturated-ll)); expected = m*p
    component = np.maximum(0., 2*(special.xlogy(y, y/expected)+special.xlogy(m-y, (m-y)/(m*q))))
    residuals = np.sign(y-expected)*np.sqrt(component); pearson = (y-expected)/np.sqrt(m*p*q)
    leverage = np.clip(np.einsum('ij,jk,ik->i', z, cov, z)*(m*p*q), 0., 1.)
    diagnostics = []
    for j, row in enumerate(rows):
        standardized = float(residuals[j]/math.sqrt(1-leverage[j])) if leverage[j] < 1-1e-12 else None
        diagnostics.append(dict(row=row+1, response=float(y[j]), trials=float(m[j]), fit=float(p[j]), probability=float(p[j]), residual=float(residuals[j]), deviance_residual=float(residuals[j]), pearson_residual=float(pearson[j]), standardized_residual=standardized, leverage=float(leverage[j]), flag=('R' if standardized is not None and abs(standardized)>2 else '')+('X' if leverage[j]>3*width/len(rows) else '')))
    names = ['Constant']
    for term in terms:
        names += ['*'.join(parts) for parts in itertools.product(*(basis[j] for j in term))]
    quantile = float(stats.norm.isf((1-o['confidence'])/2)); coefficients = []
    exp_or = lambda v: float(math.exp(v)) if -745 < v < 709 else None
    for j, name in enumerate(names):
        se = math.sqrt(max(0., float(covariance[j, j]))); estimate = float(beta[j]); zz = estimate/se if se > 0 else 0.
        lo, hi = estimate-quantile*se, estimate+quantile*se
        coefficients.append(dict(name=name, estimate=estimate, standard_error=se, z=zz, p_value=float(2*stats.norm.sf(abs(zz))), ci_low=lo, ci_high=hi, odds_ratio=exp_or(estimate), or_low=exp_or(lo), or_high=exp_or(hi)))
    curve, auc = _roc(p, y, m); lr = max(0., 2*(ll-null_ll)); df = len(rows)-width
    pred = p >= o['threshold']
    confusion = dict(true_positive=float(sum(y[pred])), false_positive=float(sum((m-y)[pred])), true_negative=float(sum((m-y)[~pred])), false_negative=float(sum(y[~pred])))
    result = dict(analysis='binary_logistic', method='Maximum likelihood binary logistic regression — logit link', response_name=response.name, event=event, non_event=non_event, grouped=trials_index is not None,
        options=o, terms=[list(t) for t in terms], term_names=['*'.join(cols[j].name for j in term) for term in terms], coding='reference', coding_information=coding, factor_information=factor_info, factor_info=factor_info,
        predictor_indices=indices, predictor_names=[c.name for c in cols], coefficients=coefficients, log_likelihood=ll, null_log_likelihood=null_ll,
        model_lr=lr, model_lr_df=width-1, model_lr_p=float(stats.chi2.sf(lr, width-1)), deviance=deviance, pearson_chi_square=float(pearson@pearson), df_error=df,
        deviance_p=float(stats.chi2.sf(deviance, df)) if df>0 else None, pearson_p=float(stats.chi2.sf(float(pearson@pearson), df)) if df>0 else None,
        aic=-2*ll+2*width, bic=-2*ll+math.log(float(sum(m)))*width, bic_sample_size=float(sum(m)), probabilities=p.tolist(), fitted=p.tolist(), eta=eta.tolist(), row_indices=rows,
        residuals=residuals.tolist(), pearson_residuals=pearson.tolist(), counts=y.tolist(), trials=m.tolist(), diagnostics=diagnostics, roc_curve=curve, auc=auc, confusion=confusion,
        n=len(rows), missing=length-len(rows), events=float(sum(y)), non_events=float(sum(m-y)), iterations=iterations, status='converged',
        model_info=dict(link='Logit', event=event, non_event=non_event, trials=float(sum(m)), observations=len(rows), coefficients=width, iterations=iterations),
        warnings=['Deviance and Pearson goodness-of-fit chi-square approximations can be unreliable with small expected counts or ungrouped binary data.'],
        methodnotes='Complete-case maximum likelihood with fixed reference contrasts; Wald coefficient and odds-ratio intervals. Binomial constants included in likelihood. BIC uses total trials. Complete/quasi separation and unstable information matrices are rejected. No weights, offsets, stepwise selection, alternative links or overdispersion. Native-product numerical equivalence is unverified.',
        _centers=centers.tolist(), _scales=scales.tolist(), _gamma=gamma.tolist(), _covariance=cov.tolist())
    return _finite_result(result)


def _source(worksheet, recipe):
    if not isinstance(recipe, dict) or recipe.get('action') != 'fit_binary_logistic' or not isinstance(recipe.get('parameters'), dict):
        raise ValueError('Choose a fitted binary logistic model recipe.')
    p = recipe['parameters']
    if set(p) != {'response_index', 'continuous_indices', 'categorical_indices', 'event', 'trials_index', 'terms', 'options'}:
        raise ValueError('Invalid binary logistic source recipe.')
    result = fit(worksheet, **p); predictors = []
    for i, info in zip(result['predictor_indices'], result['coding_information']):
        c = worksheet.columns[i]
        predictors.append(dict(name=c.name, index=i, kind=c.kind, role='factor' if info['kind']=='factor' else 'covariate', levels=info.get('levels', [])))
    spec = dict(model_action='fit_binary_logistic', model_title='Binary Logistic Regression', response_name=result['response_name'], predictor_names=result['predictor_names'], predictor_indices=result['predictor_indices'], predictors=predictors)
    return spec, result


def model_spec(worksheet, model_recipe):
    return _source(worksheet, model_recipe)[0]


def predict(worksheet, model_recipe, input_mode='values', values=None, new_indices=None, options=None):
    from .prediction import settings as prediction_settings, _inputs
    o = prediction_settings(dict(confidence=.95, intervals='confidence', side='two_sided', show_equation=True, show_table=True) if options is None else options)
    if o['intervals'] not in ('confidence', 'none'):
        raise ValueError('Binary logistic predictions support probability confidence intervals only; observation prediction intervals are unavailable.')
    spec, result = _source(worksheet, model_recipe); inputs = _inputs(worksheet, spec, input_mode, values, new_indices)
    out = [dict(row=i+1, inputs=row, probability=None, se_probability=None, eta=None, se_eta=None, ci_low=None, ci_high=None, extrapolated=False, status='missing') for i, row in enumerate(inputs)]
    valid = [i for i, row in enumerate(inputs) if all(v is not None for v in row)]
    indices = spec['predictor_indices']; source_rows = result['row_indices']
    ranges = [(min(worksheet.columns[j].values[r] for r in source_rows), max(worksheet.columns[j].values[r] for r in source_rows)) if p['role']!='factor' else None for j, p in zip(indices, spec['predictors'])]
    if valid:
        try:
            with np.errstate(over='raise', invalid='raise'):
                x = _encode([inputs[i] for i in valid], result['coding_information'], result['terms'])
                z = np.column_stack([np.ones(len(valid)), (x[:, 1:]-np.asarray(result['_centers']))/np.asarray(result['_scales'])])
                eta = z@np.asarray(result['_gamma']); covariance = np.asarray(result['_covariance'])
                variance = np.maximum(0., np.einsum('ij,jk,ik->i', z, covariance, z))
                quantile = float(stats.norm.isf((1-o['confidence'])/2)) if o['side']=='two_sided' else float(stats.norm.ppf(o['confidence']))
                for i, e, v in zip(valid, eta, variance):
                    if not math.isfinite(e) or not math.isfinite(v):
                        raise ValueError('Prediction arithmetic exceeds supported finite precision.')
                    p = float(special.expit(e)); se = math.sqrt(float(v)); row = out[i]
                    row.update(probability=p, se_probability=p*(1-p)*se, eta=float(e), se_eta=se, status='converged', extrapolated=any(bound and not bound[0]<=value<=bound[1] for value, bound in zip(inputs[i], ranges)))
                    if o['intervals']=='confidence':
                        row.update(ci_low=float(special.expit(e-quantile*se)) if o['side']!='upper' else None, ci_high=float(special.expit(e+quantile*se)) if o['side']!='lower' else None)
        except (FloatingPointError, OverflowError) as exc:
            raise ValueError('Prediction arithmetic exceeds supported finite precision.') from exc
    warnings = []
    if len(valid)!=len(inputs):warnings.append('Rows missing predictor settings have no probability prediction.')
    if any(r['extrapolated'] for r in out):warnings.append('Some continuous settings exceed the observed predictor range; within-range combinations can also have limited support.')
    return _finite_result(dict(analysis='logistic_prediction', **spec, event=result['event'], non_event=result['non_event'], options=o, rows=out, count=len(inputs), used=len(valid), missing=len(inputs)-len(valid), status='converged', coefficients=result['coefficients'], warnings=warnings,
        method='Current-worksheet logistic model refit and event probability prediction', methodnotes='Pointwise Wald intervals on the logit scale, transformed to event probabilities. No new-observation prediction intervals. Native-product numerical equivalence is unverified.'))


def residual_panels(result):
    if result['options']['graphs']=='none':return []
    residuals=result['residuals']; ordered=sorted(residuals); n=len(ordered)
    scores=stats.norm.ppf((np.arange(n)+.625)/(n+.25)).tolist()
    counts,edges=np.histogram(residuals,bins=min(10,max(3,math.ceil(math.sqrt(n)))))
    return [dict(kind='normal_probability',title='Normal Probability Plot',x=ordered,y=scores,xlabel='Deviance Residual',ylabel='Normal Score'),
        dict(kind='scatter',title='Versus Fits',x=result['probabilities'],y=residuals,xlabel='Fitted Event Probability',ylabel='Deviance Residual',zero=True,row_indices=[r+1 for r in result['row_indices']]),
        dict(kind='histogram',title='Histogram',counts=counts.tolist(),edges=edges.tolist(),curves=[],specs=[],xlabel='Deviance Residual',ylabel='Frequency'),
        dict(kind='line',title='Versus Order',x=[r+1 for r in result['row_indices']],y=residuals,lines=[],xlabel='Observation Order',ylabel='Deviance Residual',zero=True,row_indices=[r+1 for r in result['row_indices']])]
