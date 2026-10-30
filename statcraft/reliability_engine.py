"""Original parametric reliability MLE with aligned right censoring.

Likelihood combines failure densities and survivor probabilities. Approximate
intervals use observed information and the delta method; no fixed uncertainty or
invented goodness-of-fit statistic is returned. Native equivalence is unverified.
"""
from __future__ import annotations

import math
import numbers
import numpy as np
from scipy import stats
from scipy.optimize import minimize


def _validated_arrays(times, events):
    try:
        t = np.asarray(times, dtype=float)
        e = np.asarray(events, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('Times and event indicators must be numeric arrays.') from exc
    if t.ndim != 1 or e.ndim != 1 or len(t) != len(e) or not len(t):
        raise ValueError('Times and event indicators must be nonempty aligned vectors.')
    if not np.all(np.isfinite(t)) or not np.all(t > 0):
        raise ValueError('Lifetime observations must be positive finite numbers.')
    if not np.all(np.isfinite(e)) or not np.all((e == 0) | (e == 1)):
        raise ValueError('Event indicators must be 0 (censored) or 1 (failed).')
    return t, e.astype(int)


def fit_kaplan_meier(times, events):
    """Product-limit estimate, with failures preceding censors at tied times."""
    times, events = _validated_arrays(times, events)
    survival, risk = 1.0, len(times)
    table = {'times': [], 'n_at_risk': [], 'n_failed': [], 'survival': [], 'cum_hazard': []}
    for time in np.unique(times):
        mask = times == time
        failures = int(np.sum(events[mask]))
        if failures:
            survival *= 1.0 - failures / risk
            table['times'].append(float(time))
            table['n_at_risk'].append(int(risk))
            table['n_failed'].append(failures)
            table['survival'].append(float(survival))
            table['cum_hazard'].append(-math.log(survival) if survival > 0 else None)
        risk -= int(np.sum(mask))
    return table


def _observed_covariance(objective, optimum):
    """Central-difference observed information in unconstrained fit coordinates."""
    x = np.asarray(optimum, dtype=float)
    h = 1e-4 * np.maximum(1.0, np.abs(x))
    dim = len(x)
    f0 = objective(x)
    information = np.empty((dim, dim))
    for i in range(dim):
        ei = np.zeros(dim); ei[i] = h[i]
        information[i, i] = (objective(x + ei) - 2 * f0 + objective(x - ei)) / h[i]**2
        for j in range(i):
            ej = np.zeros(dim); ej[j] = h[j]
            value = (objective(x + ei + ej) - objective(x + ei - ej)
                     - objective(x - ei + ej) + objective(x - ei - ej)) / (4 * h[i] * h[j])
            information[i, j] = information[j, i] = value
    if not np.all(np.isfinite(information)):
        return None
    eigenvalues = np.linalg.eigvalsh(information)
    if min(eigenvalues) <= 0 or max(eigenvalues) / min(eigenvalues) > 1e12:
        return None
    return np.linalg.inv(information)


def _finite_interval(center, standard_error, z, logarithmic=False):
    try:
        if logarithmic:
            low = center * math.exp(-z * standard_error / center)
            high = center * math.exp(z * standard_error / center)
        else:
            low, high = center - z * standard_error, center + z * standard_error
    except (OverflowError, ZeroDivisionError):
        return [None, None]
    return [float(low) if math.isfinite(low) else None,
            float(high) if math.isfinite(high) else None]


def fit_parametric_reliability(times, events, dist_name='weibull', confidence_level=0.95):
    """Fit a positive-lifetime distribution with asymptotic information intervals.

    Interval accuracy can be poor with few failures. Censored goodness-of-fit
    statistics and native adjusted Anderson-Darling statistics are unavailable.
    """
    times, events = _validated_arrays(times, events)
    if not isinstance(confidence_level, numbers.Real) or isinstance(confidence_level, (bool, np.bool_)) or not math.isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise ValueError('Confidence level must be strictly between 0 and 1.')
    if not isinstance(dist_name, str) or dist_name.lower() not in ('weibull', 'lognormal', 'exponential', 'normal'):
        raise ValueError('Unsupported reliability distribution.')
    dist_name = dist_name.lower()
    failures = times[events == 1]
    censors = times[events == 0]
    n_events = len(failures)
    if n_events < 2:
        raise ValueError('Reliability analysis requires at least 2 observed failure events.')
    if dist_name != 'exponential' and (np.ptp(times) == 0 or (np.ptp(failures) == 0 and (not len(censors) or np.max(censors) <= failures[0]))):
        raise ValueError('A finite scale estimate requires variation in lifetime observations.')
    z = float(stats.norm.isf((1.0 - confidence_level) / 2))
    median = float(np.median(times))
    log_times = np.log(times)
    if dist_name == 'weibull':
        initial = np.array([0.0, math.log(median)])
        names, positive = ['shape', 'scale'], [True, True]
        def model(x):
            return stats.weibull_min(math.exp(x[0]), scale=math.exp(x[1]))
        def parameters(x):
            return np.exp(x)
    elif dist_name == 'lognormal':
        initial = np.array([float(np.mean(log_times)), math.log(max(.1, float(np.std(log_times))))])
        names, positive = ['location', 'scale'], [False, True]
        def model(x):
            return stats.lognorm(math.exp(x[1]), scale=math.exp(x[0]))
        def parameters(x):
            return np.array([x[0], math.exp(x[1])])
    elif dist_name == 'normal':
        initial = np.array([float(np.mean(times)), math.log(max(median * 1e-3, float(np.std(times))))])
        names, positive = ['mean', 'stdev'], [False, True]
        def model(x):
            return stats.norm(loc=x[0], scale=math.exp(x[1]))
        def parameters(x):
            return np.array([x[0], math.exp(x[1])])
    else:
        initial = np.array([math.log(float(np.sum(times)) / n_events)])
        names, positive = ['scale_mean'], [True]
        def model(x):
            return stats.expon(scale=math.exp(x[0]))
        def parameters(x):
            return np.exp(x)

    def objective(x):
        try:
            with np.errstate(all='ignore'):
                distribution = model(x)
                value = -float(np.sum(distribution.logpdf(failures)) + np.sum(distribution.logsf(censors)))
            return value if math.isfinite(value) else 1e100
        except (OverflowError, ValueError, FloatingPointError):
            return 1e100

    if dist_name == 'exponential':
        optimum = initial
        converged = math.isfinite(objective(optimum)) and objective(optimum) < 1e99
    else:
        fit = minimize(objective, initial, method='BFGS', options={'gtol': 1e-6, 'maxiter': 2000})
        if not fit.success:
            # Precision-loss failures are common with BFGS; independently converge
            # a derivative-free simplex, rather than accepting a failed optimizer.
            fit = minimize(objective, fit.x if np.all(np.isfinite(fit.x)) else initial,
                           method='Nelder-Mead', options={'maxiter':5000, 'xatol':1e-9, 'fatol':1e-9})
        optimum, converged = np.asarray(fit.x), bool(fit.success)
    if not converged or objective(optimum) >= 1e99:
        raise ValueError('Reliability maximum likelihood fit did not converge to a finite solution.')
    distribution = model(optimum)
    parameter_values = parameters(optimum)
    mttf = float(distribution.mean())
    if not np.all(np.isfinite(parameter_values)) or not math.isfinite(mttf):
        raise ValueError('Fitted reliability parameters or mean exceed the supported numeric range.')
    covariance = _observed_covariance(objective, optimum)
    warnings = []
    if n_events < 10:
        warnings.append('Few failures: maximum likelihood estimates and asymptotic confidence intervals may be imprecise.')
    if covariance is None:
        warnings.append('Observed information is singular or unstable; confidence intervals are unavailable.')
    parameter_se, parameter_ci = {}, {}
    for i, (name, estimate, is_positive) in enumerate(zip(names, parameter_values, positive)):
        estimate = float(estimate)
        if covariance is None:
            parameter_se[name], parameter_ci[name] = None, [None, None]
        else:
            se = math.sqrt(max(0.0, float(covariance[i, i]))) * (estimate if is_positive else 1.0)
            parameter_se[name] = se
            parameter_ci[name] = _finite_interval(estimate, se, z, is_positive)
    percentile_table = []
    for percent in (1., 5., 10., 20., 50., 90.):
        estimate = float(distribution.ppf(percent / 100))
        if not math.isfinite(estimate):
            raise ValueError('Fitted reliability percentile exceeds the supported numeric range.')
        low, high = None, None
        se = None
        if covariance is not None:
            gradient = []
            for i in range(len(optimum)):
                h = 1e-5 * max(1.0, abs(optimum[i]))
                step = np.zeros(len(optimum)); step[i] = h
                gradient.append((float(model(optimum + step).ppf(percent / 100))
                                 - float(model(optimum - step).ppf(percent / 100))) / (2 * h))
            gradient = np.asarray(gradient)
            variance = float(gradient @ covariance @ gradient)
            if math.isfinite(variance) and variance >= 0:
                se = math.sqrt(variance)
                low, high = _finite_interval(estimate, se, z, dist_name != 'normal')
        percentile_table.append({'percent':percent, 'estimate':estimate, 'lower':low, 'upper':high, 'standard_error':se})
    ad_stat = None
    if len(censors) == 0:
        ordered = np.sort(times)
        index = np.arange(1, len(times) + 1)
        with np.errstate(all='ignore'):
            value = -len(times) - float(np.sum((2 * index - 1) * (distribution.logcdf(ordered) + distribution.logsf(ordered[::-1]))) / len(times))
        if math.isfinite(value):
            ad_stat = max(0.0, value)
        else:
            warnings.append('Anderson-Darling statistic is numerically unavailable for this fit.')
    else:
        warnings.append('A censored-data goodness-of-fit statistic is not implemented; Anderson-Darling is unavailable.')
    return {
        'analysis':'reliability_distribution', 'dist_name':dist_name,
        'n_total':len(times), 'n_events':n_events, 'n_censored':len(censors),
        'log_likelihood':-objective(optimum),
        'parameters':dict(zip(names, map(float, parameter_values))),
        'parameter_se':parameter_se, 'parameter_ci':parameter_ci,
        'mttf':mttf, 'confidence_level':float(confidence_level),
        'inference_method':'Observed-information delta method (asymptotic)',
        'ad_stat':ad_stat, 'ad_method':'Unadjusted Anderson-Darling; uncensored data only',
        'percentile_table':percentile_table,
        'times':times.tolist(), 'events':events.tolist(), 'warnings':warnings,
    }


def run_reliability_analysis(time_values, censor_values=None, censor_value=None,
                             dist_name='weibull', confidence_level=0.95):
    """Clean aligned missing rows; reject invalid times and censor indicators."""
    if censor_values is not None and len(censor_values) != len(time_values):
        raise ValueError('Censor values must have the same length as lifetime observations.')
    if isinstance(censor_value, numbers.Real) and not math.isfinite(censor_value):
        raise ValueError('The censor value must be finite.')
    times, events, rows, missing = [], [], [], []
    for i, value in enumerate(time_values):
        censor = censor_values[i] if censor_values is not None else 1
        if value is None or (censor_values is not None and censor is None):
            missing.append(i + 1)
            continue
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'Lifetime in row {i + 1} must be a positive finite number.')
        if censor_values is None:
            event = 1
        elif censor_value is not None:
            if isinstance(censor, numbers.Real) and not math.isfinite(censor):
                raise ValueError(f'Censor indicator in row {i + 1} must be finite.')
            event = 0 if censor == censor_value else 1
        elif censor in (0, 1, '0', '1'):
            event = int(censor)
        else:
            raise ValueError(f'Censor indicator in row {i + 1} must be 0 or 1, or specify a censor value.')
        times.append(float(value)); events.append(event); rows.append(i + 1)
    if len(times) < 3:
        raise ValueError('Reliability analysis requires at least 3 complete lifetime observations.')
    result = fit_parametric_reliability(times, events, dist_name, confidence_level)
    result['kaplan_meier'] = fit_kaplan_meier(times, events)
    result['used_rows'], result['missing_rows'] = rows, missing
    if missing:
        result['warnings'].append(f'{len(missing)} incomplete rows were omitted as aligned time/censor pairs.')
    return result

