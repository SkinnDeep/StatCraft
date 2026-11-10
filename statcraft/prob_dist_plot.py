"""Probability Distribution Plot Engine for Statcraft.

Implements Minitab-identical continuous and discrete probability distribution
calculations, density curves, cumulative probabilities, and shaded probability
regions (Right Tail, Left Tail, Both Tails, Middle / Interval).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


SUPPORTED_DISTRIBUTIONS = {
    'Normal': {'params': [('mean', 'Mean', 0.0), ('stdev', 'Standard Deviation', 1.0)], 'discrete': False},
    'Student\'s t': {'params': [('df', 'Degrees of Freedom', 10.0)], 'discrete': False},
    'Chi-Square': {'params': [('df', 'Degrees of Freedom', 5.0)], 'discrete': False},
    'F': {'params': [('df_num', 'Numerator DF', 5.0), ('df_den', 'Denominator DF', 10.0)], 'discrete': False},
    'Binomial': {'params': [('n', 'Number of Trials', 20), ('p', 'Event Probability', 0.5)], 'discrete': True},
    'Poisson': {'params': [('lambda', 'Mean (Lambda)', 5.0)], 'discrete': True},
    'Exponential': {'params': [('scale', 'Scale (1/Rate)', 1.0)], 'discrete': False},
    'Gamma': {'params': [('shape', 'Shape (k)', 3.0), ('scale', 'Scale (Theta)', 2.0)], 'discrete': False},
    'Weibull': {'params': [('shape', 'Shape (Beta)', 2.0), ('scale', 'Scale (Eta)', 10.0)], 'discrete': False},
    'Uniform': {'params': [('lower', 'Lower Endpoint', 0.0), ('upper', 'Upper Endpoint', 1.0)], 'discrete': False},
    'Lognormal': {'params': [('mean', 'Location (Meanlog)', 0.0), ('stdev', 'Scale (SDlog)', 1.0)], 'discrete': False},
    'Logistic': {'params': [('location', 'Location', 0.0), ('scale', 'Scale', 1.0)], 'discrete': False},
}


def get_distribution_scipy(dist_name: str, params: Dict[str, float]):
    """Instantiate a scipy frozen distribution object given user parameters."""
    name = dist_name.strip()
    if name in ('Normal', 'norm'):
        mean = float(params.get('mean', 0.0))
        stdev = float(params.get('stdev', 1.0))
        if stdev <= 0:
            raise ValueError('Standard deviation must be positive.')
        return stats.norm(loc=mean, scale=stdev), False

    elif name in ("Student's t", 't'):
        df = float(params.get('df', 10.0))
        if df <= 0:
            raise ValueError('Degrees of freedom must be positive.')
        return stats.t(df=df), False

    elif name in ('Chi-Square', 'chi2'):
        df = float(params.get('df', 5.0))
        if df <= 0:
            raise ValueError('Degrees of freedom must be positive.')
        return stats.chi2(df=df), False

    elif name in ('F', 'f'):
        df1 = float(params.get('df_num', 5.0))
        df2 = float(params.get('df_den', 10.0))
        if df1 <= 0 or df2 <= 0:
            raise ValueError('Numerator and denominator degrees of freedom must be positive.')
        return stats.f(dfn=df1, dfd=df2), False

    elif name in ('Binomial', 'binom'):
        n = int(round(float(params.get('n', 20))))
        p = float(params.get('p', 0.5))
        if n < 1:
            raise ValueError('Number of trials must be at least 1.')
        if not (0.0 <= p <= 1.0):
            raise ValueError('Event probability must be between 0 and 1.')
        return stats.binom(n=n, p=p), True

    elif name in ('Poisson', 'poisson'):
        lam = float(params.get('lambda', 5.0))
        if lam <= 0:
            raise ValueError('Poisson mean (lambda) must be positive.')
        return stats.poisson(mu=lam), True

    elif name in ('Exponential', 'expon'):
        scale = float(params.get('scale', 1.0))
        if scale <= 0:
            raise ValueError('Exponential scale must be positive.')
        return stats.expon(scale=scale), False

    elif name in ('Gamma', 'gamma'):
        shape = float(params.get('shape', 3.0))
        scale = float(params.get('scale', 2.0))
        if shape <= 0 or scale <= 0:
            raise ValueError('Gamma shape and scale must be positive.')
        return stats.gamma(a=shape, scale=scale), False

    elif name in ('Weibull', 'weibull'):
        shape = float(params.get('shape', 2.0))
        scale = float(params.get('scale', 10.0))
        if shape <= 0 or scale <= 0:
            raise ValueError('Weibull shape and scale must be positive.')
        return stats.weibull_min(c=shape, scale=scale), False

    elif name in ('Uniform', 'uniform'):
        lower = float(params.get('lower', 0.0))
        upper = float(params.get('upper', 1.0))
        if upper <= lower:
            raise ValueError('Upper endpoint must exceed lower endpoint.')
        return stats.uniform(loc=lower, scale=upper - lower), False

    elif name in ('Lognormal', 'lognorm'):
        mean = float(params.get('mean', 0.0))
        stdev = float(params.get('stdev', 1.0))
        if stdev <= 0:
            raise ValueError('Lognormal scale (stdev) must be positive.')
        return stats.lognorm(s=stdev, scale=math.exp(mean)), False

    elif name in ('Logistic', 'logistic'):
        loc = float(params.get('location', 0.0))
        scale = float(params.get('scale', 1.0))
        if scale <= 0:
            raise ValueError('Logistic scale must be positive.')
        return stats.logistic(loc=loc, scale=scale), False

    else:
        raise ValueError(f'Unsupported distribution: {dist_name}')


def compute_probability_distribution_plot(
    distribution: str = 'Normal',
    parameters: Optional[Dict[str, float]] = None,
    mode: str = 'single',  # 'single' or 'probability'
    shade_by: str = 'probability',  # 'probability' or 'x_value'
    tail: str = 'both',  # 'right', 'left', 'both', 'middle'
    prob_value: float = 0.05,
    x_value: Optional[float] = None,
    x_low: Optional[float] = None,
    x_high: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute the distribution plot snapshot, density points, and shaded area."""
    params = dict(parameters or {})
    dist_obj, is_discrete = get_distribution_scipy(distribution, params)

    # Compute descriptive stats
    try:
        mean = float(dist_obj.mean())
    except Exception:
        mean = 0.0
    try:
        var = float(dist_obj.var())
        stdev = math.sqrt(var) if var >= 0 else 0.0
    except Exception:
        var = 0.0
        stdev = 0.0

    # Determine plotting domain
    if is_discrete:
        # Discrete: Binomial or Poisson
        if hasattr(dist_obj, 'dist') and dist_obj.dist.name == 'binom':
            n_trials = int(params.get('n', 20))
            x_min = 0
            x_max = min(n_trials, max(20, int(dist_obj.ppf(0.9995)) + 1))
        else:
            x_min = 0
            x_max = max(15, int(dist_obj.ppf(0.9995)) + 2)

        xs = list(range(x_min, x_max + 1))
        pmf_vals = [float(dist_obj.pmf(k)) for k in xs]
        points = [[k, p] for k, p in zip(xs, pmf_vals)]
        curve_points = points
        domain_min = x_min - 0.5
        domain_max = x_max + 0.5
        y_max = max(pmf_vals) * 1.15 if pmf_vals else 1.0
    else:
        # Continuous
        # Default domain from 0.0005 to 0.9995 quantiles
        p_lo = 0.0005
        p_hi = 0.9995
        try:
            q_lo = float(dist_obj.ppf(p_lo))
            q_hi = float(dist_obj.ppf(p_hi))
        except Exception:
            q_lo = mean - 4 * (stdev if stdev > 0 else 1.0)
            q_hi = mean + 4 * (stdev if stdev > 0 else 1.0)

        if not math.isfinite(q_lo) or not math.isfinite(q_hi) or q_hi <= q_lo:
            q_lo = mean - 4.0
            q_hi = mean + 4.0

        num_pts = 301
        xs = np.linspace(q_lo, q_hi, num_pts).tolist()
        pdf_vals = [float(dist_obj.pdf(x)) if math.isfinite(float(dist_obj.pdf(x))) else 0.0 for x in xs]
        curve_points = [[x, y] for x, y in zip(xs, pdf_vals)]
        domain_min = q_lo
        domain_max = q_hi
        y_max = max(pdf_vals) * 1.18 if pdf_vals else 1.0

    # Handle View Single mode
    if mode == 'single':
        return {
            'graph': 'probability_distribution',
            'analysis': 'probability_distribution',
            'title': f'Distribution Plot: {distribution}',
            'distribution': distribution,
            'parameters': params,
            'is_discrete': is_discrete,
            'mode': 'single',
            'domain': [domain_min, domain_max],
            'y_max': y_max,
            'curve_points': curve_points,
            'discrete_bars': [{'x': k, 'prob': p, 'shaded': False} for k, p in zip(xs, pmf_vals)] if is_discrete else [],
            'shaded_regions': [],
            'cutoffs': [],
            'mean': mean,
            'variance': var,
            'stdev': stdev,
            'total_shaded_prob': 0.0,
        }

    # Handle View Probability mode
    # Validate shaded area inputs
    c1: Optional[float] = None
    c2: Optional[float] = None
    p1: float = 0.0
    p2: float = 0.0
    p_total: float = 0.0

    if shade_by == 'probability':
        prob = float(prob_value)
        if not (0.0 < prob < 1.0):
            raise ValueError('Probability must be strictly between 0 and 1.')

        if tail == 'right':
            c1 = float(dist_obj.ppf(1.0 - prob))
            p1 = float(1.0 - dist_obj.cdf(c1) if not is_discrete else 1.0 - dist_obj.cdf(c1 - 1))
            p_total = p1
        elif tail == 'left':
            c1 = float(dist_obj.ppf(prob))
            p1 = float(dist_obj.cdf(c1))
            p_total = p1
        elif tail == 'both':
            half = prob / 2.0
            c1 = float(dist_obj.ppf(half))
            c2 = float(dist_obj.ppf(1.0 - half))
            p1 = float(dist_obj.cdf(c1))
            p2 = float(1.0 - dist_obj.cdf(c2) if not is_discrete else 1.0 - dist_obj.cdf(c2 - 1))
            p_total = p1 + p2
        elif tail == 'middle':
            half_out = (1.0 - prob) / 2.0
            c1 = float(dist_obj.ppf(half_out))
            c2 = float(dist_obj.ppf(1.0 - half_out))
            p_total = float(dist_obj.cdf(c2) - dist_obj.cdf(c1))
            p1 = p_total
        else:
            raise ValueError(f'Unsupported tail type: {tail}')

    elif shade_by == 'x_value':
        if tail in ('right', 'left'):
            if x_value is None:
                raise ValueError('Please specify an X value.')
            c1 = float(x_value)
            if tail == 'right':
                p1 = float(1.0 - dist_obj.cdf(c1) if not is_discrete else 1.0 - dist_obj.cdf(c1 - 1))
                p_total = p1
            else:
                p1 = float(dist_obj.cdf(c1))
                p_total = p1
        elif tail in ('both', 'middle'):
            if x_low is None or x_high is None:
                raise ValueError('Please specify both lower and upper X cutoff values.')
            c1 = float(x_low)
            c2 = float(x_high)
            if c2 < c1:
                c1, c2 = c2, c1
            if tail == 'both':
                p1 = float(dist_obj.cdf(c1))
                p2 = float(1.0 - dist_obj.cdf(c2) if not is_discrete else 1.0 - dist_obj.cdf(c2 - 1))
                p_total = p1 + p2
            else:
                p_total = float(dist_obj.cdf(c2) - dist_obj.cdf(c1))
                p1 = p_total
        else:
            raise ValueError(f'Unsupported tail type: {tail}')
    else:
        raise ValueError(f'Unsupported shade_by: {shade_by}')

    # Construct shaded regions
    shaded_regions = []
    cutoffs = []

    if is_discrete:
        discrete_bars = []
        for k, p in zip(xs, pmf_vals):
            is_shaded = False
            if tail == 'right' and c1 is not None and k >= c1:
                is_shaded = True
            elif tail == 'left' and c1 is not None and k <= c1:
                is_shaded = True
            elif tail == 'both' and c1 is not None and c2 is not None and (k <= c1 or k >= c2):
                is_shaded = True
            elif tail == 'middle' and c1 is not None and c2 is not None and (c1 <= k <= c2):
                is_shaded = True
            discrete_bars.append({'x': k, 'prob': p, 'shaded': is_shaded})
    else:
        discrete_bars = []
        # Generate shaded polygon coordinates for continuous curve
        if tail == 'right' and c1 is not None:
            sub_xs = np.linspace(max(domain_min, c1), domain_max, 120).tolist()
            poly = [[sub_xs[0], 0.0]] + [[x, float(dist_obj.pdf(x))] for x in sub_xs] + [[sub_xs[-1], 0.0]]
            shaded_regions.append({'polygon': poly, 'prob': p1, 'pos': (c1 + domain_max) / 2.0})
            cutoffs.append({'x': c1, 'label': f'X = {c1:.4g}', 'p': p1})

        elif tail == 'left' and c1 is not None:
            sub_xs = np.linspace(domain_min, min(domain_max, c1), 120).tolist()
            poly = [[sub_xs[0], 0.0]] + [[x, float(dist_obj.pdf(x))] for x in sub_xs] + [[sub_xs[-1], 0.0]]
            shaded_regions.append({'polygon': poly, 'prob': p1, 'pos': (domain_min + c1) / 2.0})
            cutoffs.append({'x': c1, 'label': f'X = {c1:.4g}', 'p': p1})

        elif tail == 'both' and c1 is not None and c2 is not None:
            sub_left = np.linspace(domain_min, min(domain_max, c1), 80).tolist()
            poly_left = [[sub_left[0], 0.0]] + [[x, float(dist_obj.pdf(x))] for x in sub_left] + [[sub_left[-1], 0.0]]
            shaded_regions.append({'polygon': poly_left, 'prob': p1, 'pos': (domain_min + c1) / 2.0})

            sub_right = np.linspace(max(domain_min, c2), domain_max, 80).tolist()
            poly_right = [[sub_right[0], 0.0]] + [[x, float(dist_obj.pdf(x))] for x in sub_right] + [[sub_right[-1], 0.0]]
            shaded_regions.append({'polygon': poly_right, 'prob': p2, 'pos': (c2 + domain_max) / 2.0})

            cutoffs.append({'x': c1, 'label': f'X1 = {c1:.4g}', 'p': p1})
            cutoffs.append({'x': c2, 'label': f'X2 = {c2:.4g}', 'p': p2})

        elif tail == 'middle' and c1 is not None and c2 is not None:
            sub_mid = np.linspace(max(domain_min, c1), min(domain_max, c2), 120).tolist()
            poly = [[sub_mid[0], 0.0]] + [[x, float(dist_obj.pdf(x))] for x in sub_mid] + [[sub_mid[-1], 0.0]]
            shaded_regions.append({'polygon': poly, 'prob': p_total, 'pos': (c1 + c2) / 2.0})
            cutoffs.append({'x': c1, 'label': f'X1 = {c1:.4g}', 'p': p1})
            cutoffs.append({'x': c2, 'label': f'X2 = {c2:.4g}', 'p': p2})

    return {
        'graph': 'probability_distribution',
        'analysis': 'probability_distribution',
        'title': f'Distribution Plot: {distribution}',
        'distribution': distribution,
        'parameters': params,
        'is_discrete': is_discrete,
        'mode': 'probability',
        'shade_by': shade_by,
        'tail': tail,
        'domain': [domain_min, domain_max],
        'y_max': y_max,
        'curve_points': curve_points,
        'discrete_bars': discrete_bars,
        'shaded_regions': shaded_regions,
        'cutoffs': cutoffs,
        'c1': c1,
        'c2': c2,
        'p1': p1,
        'p2': p2,
        'total_shaded_prob': p_total,
        'mean': mean,
        'variance': var,
        'stdev': stdev,
    }
