"""Original span-2 I-MR and individual-observation normal capability methods.

Formula references and provenance are retained in the external research ledger.

Full-precision mathematical span-2 normal-range constants are used. Missing
gaps break moving ranges. Exact native constants, missing conventions, optional
tests, historical parameters, subgroup methods and bitwise parity are unverified.
"""
import math
from scipy.stats import norm
from .engine import normalize_numeric
from .analyses import describe

D2 = 2 / math.sqrt(math.pi)
D3 = math.sqrt(2 - 4 / math.pi)


def _finite(value):
    if not math.isfinite(value):
        raise ValueError('Quality calculation exceeds the supported numeric range.')
    return value


def individuals_moving_range(values):
    observations = [normalize_numeric(x) for x in values]
    clean = [x for x in observations if x is not None]
    if len(clean) < 2:
        raise ValueError('I-MR needs at least two nonmissing observations.')
    ranges = [None] * len(observations)
    for row in range(1, len(observations)):
        a, b = observations[row - 1], observations[row]
        if a is not None and b is not None:
            ranges[row] = _finite(abs(b - a))
    available = [x for x in ranges if x is not None]
    if not available:
        raise ValueError('I-MR needs at least one adjacent complete pair; missing gaps are not bridged.')
    mean = _finite(math.fsum(x / len(clean) for x in clean))
    average_range = _finite(math.fsum(x / len(available) for x in available))
    sigma = _finite(average_range / D2)
    i_lcl, i_ucl = _finite(mean - 3 * sigma), _finite(mean + 3 * sigma)
    mr_lcl = max(0.0, _finite(average_range - 3 * D3 * sigma))
    mr_ucl = _finite(average_range + 3 * D3 * sigma)
    return {'method': 'Average moving range, span 2; three-sigma limits; Test 1 only',
        'count': len(clean), 'missing': len(observations) - len(clean),
        'observations': observations, 'moving_ranges': ranges,
        'mean': mean, 'within_stdev': sigma, 'average_moving_range': average_range,
        'i_center': mean, 'i_lcl': i_lcl, 'i_ucl': i_ucl,
        'mr_center': average_range, 'mr_lcl': mr_lcl, 'mr_ucl': mr_ucl,
        'i_signals': [i + 1 for i, x in enumerate(observations) if x is not None and (x < i_lcl or x > i_ucl)],
        'mr_signals': [i + 1 for i, x in enumerate(ranges) if x is not None and (x < mr_lcl or x > mr_ucl)],
        'missing_policy': 'Missing gaps break adjacent moving-range pairs; gaps are not bridged.',
        'warnings': ['Zero estimated variation: control limits coincide.'] if sigma == 0 else []}


def normal_capability(values, lsl=None, usl=None, target=None):
    observations = [normalize_numeric(x) for x in values]
    clean = [x for x in observations if x is not None]
    parameters = []
    for label, value in [('Lower specification', lsl), ('Upper specification', usl), ('Target', target)]:
        normalized = None if value is None else normalize_numeric(value)
        if value is not None and normalized is None:
            raise ValueError(label + ' must be finite and nonmissing.')
        parameters.append(normalized)
    lsl, usl, target = parameters
    if lsl is None and usl is None:
        raise ValueError('Enter at least one specification limit.')
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError('Lower specification must be less than upper specification.')
    control = individuals_moving_range(observations)
    summary = describe(clean)
    within, overall, mean = control['within_stdev'], summary['sample_stdev'], summary['mean']
    if within <= 0 or overall is None or overall <= 0:
        raise ValueError('Capability needs positive within and overall variation.')
    result = {'method': 'Individual observations; within sigma from average adjacent moving range / d2; overall sample StDev',
        'count': len(clean), 'missing': len(observations) - len(clean), 'observations': clean,
        'mean': mean, 'within_stdev': within, 'overall_stdev': overall,
        'lsl': lsl, 'usl': usl, 'target': target,
        'assumptions': 'Normal process distribution; process stability must be assessed separately. Missing gaps are not bridged for within-sigma estimation.',
        'warnings': []}
    for prefix, sigma in [('c', within), ('p', overall)]:
        lower = None if lsl is None else _finite((mean - lsl) / (3 * sigma))
        upper = None if usl is None else _finite((usl - mean) / (3 * sigma))
        result[prefix + 'pl'] = lower
        result[prefix + 'pu'] = upper
        result[prefix + 'pk'] = min(x for x in (lower, upper) if x is not None)
        result[prefix + 'p'] = None if lsl is None or usl is None else _finite((usl - lsl) / (6 * sigma))
    result['cpm'] = None
    if target is not None:
        deviations = [_finite(x - target) for x in clean]
        scale = max(abs(x) for x in deviations)
        rms = _finite(scale * math.sqrt(math.fsum((x / scale)**2 for x in deviations) / len(clean)))
        distances = [x for x in (None if lsl is None else target - lsl,
                                None if usl is None else usl - target) if x is not None]
        result['cpm'] = _finite(min(distances) / (3 * rms))
    result['observed_ppm_below'] = 0.0 if lsl is None else sum(x < lsl for x in clean) / len(clean) * 1e6
    result['observed_ppm_above'] = 0.0 if usl is None else sum(x > usl for x in clean) / len(clean) * 1e6
    result['observed_ppm_total'] = result['observed_ppm_below'] + result['observed_ppm_above']
    for label, sigma in [('within', within), ('overall', overall)]:
        below = 0.0 if lsl is None else float(norm.cdf((lsl - mean) / sigma)) * 1e6
        above = 0.0 if usl is None else float(norm.sf((usl - mean) / sigma)) * 1e6
        result['expected_' + label + '_ppm_below'] = below
        result['expected_' + label + '_ppm_above'] = above
        result['expected_' + label + '_ppm_total'] = below + above
    return result
