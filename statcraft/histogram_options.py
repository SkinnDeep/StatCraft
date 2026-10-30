"""Original bounded histogram construction, independent of native binning.

Intervals have equal width; interior cutpoints belong to the right bin and the
last interval includes its upper endpoint. Normal fits use sample mean and
sample standard deviation. Native numerical equivalence is unverified.
"""
import bisect
import math
import numbers
from statistics import NormalDist, mean, stdev


def validate_histogram_settings(settings):
    """Return detached normalized settings, rejecting unsupported combinations."""
    if not isinstance(settings, dict):
        raise ValueError('Histogram settings must be an object.')
    unknown = set(settings) - {'bins', 'scale', 'cumulative', 'fit'}
    if unknown:
        raise ValueError('Unsupported histogram setting: ' + ', '.join(sorted(map(str, unknown))))
    bins = settings.get('bins', 10)
    scale = settings.get('scale', 'Frequency')
    cumulative = settings.get('cumulative', False)
    fit = settings.get('fit')
    # Bounds follow recovered controls; integral counts are our engine contract.
    if type(bins) is not int or not 2 <= bins <= 1000:
        raise ValueError('Number of intervals must be an integer from 2 to 1000.')
    if scale not in ('Frequency', 'Percent', 'Density'):
        raise ValueError('Y scale must be Frequency, Percent, or Density.')
    if type(cumulative) is not bool:
        raise ValueError('Cumulative must be true or false.')
    if fit not in (None, 'Normal'):
        raise ValueError('Fit must be None or Normal.')
    if cumulative and scale == 'Density':
        raise ValueError('Cumulative histograms require Frequency or Percent scale.')
    return dict(bins=bins, scale=scale, cumulative=cumulative, fit=fit)


def build_histogram_panel(values, settings):
    """Build a ChartWidget histogram panel from actual observations only.

Never reconstruct observations from interval counts. Callers should pass the
preserved histogram_source snapshot; missing values must already be omitted.
    """
    options = validate_histogram_settings(settings)
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError('Original histogram observations are required. Rerun this graph to retain its source.')
    clean = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
            raise ValueError('Histogram source must contain finite nonmissing numeric observations.')
        clean.append(float(value))
    low, high = min(clean), max(clean)
    if low == high:
        # A visible original convention for constant data, not native behavior.
        padding = max(.5, abs(low) * 1e-6)
        low, high = low - padding, high + padding
    width = (high - low) / options['bins']
    if not math.isfinite(width) or width <= 0:
        raise ValueError('Histogram range exceeds plotting precision.')
    edges = [low + width * i for i in range(options['bins'])] + [high]
    if any(not math.isfinite(v) for v in edges) or any(a >= b for a, b in zip(edges, edges[1:])):
        raise ValueError('Histogram intervals exceed plotting precision; use fewer intervals.')
    counts = [0] * options['bins']
    for value in clean:
        index = min(len(counts) - 1, max(0, bisect.bisect_right(edges, value) - 1))
        counts[index] += 1
    n = len(clean)
    if options['cumulative']:
        running = 0
        for i, count in enumerate(counts):
            running += count
            counts[i] = running
    scale = options['scale']
    if scale == 'Percent':
        counts = [100.0 * count / n for count in counts]
    elif scale == 'Density':
        counts = [count / n / width for count in counts]
    curves = []
    if options['fit'] == 'Normal':
        if n < 2:
            raise ValueError('A Normal fit requires at least two observations.')
        center, deviation = mean(clean), stdev(clean)
        if not math.isfinite(deviation) or deviation <= 0:
            raise ValueError('A Normal fit requires a positive sample standard deviation.')
        normal = NormalDist(center, deviation)
        xs = [low + (high - low) * i / 160 for i in range(161)]
        if options['cumulative']:
            multiplier = n if scale == 'Frequency' else 100.0
            ys = [normal.cdf(x) * multiplier for x in xs]
        else:
            multiplier = n * width if scale == 'Frequency' else 100.0 * width if scale == 'Percent' else 1.0
            ys = [normal.pdf(x) * multiplier for x in xs]
        if any(not math.isfinite(y) for y in ys):
            raise ValueError('Normal fit exceeds plotting precision.')
        curves.append(('Normal', xs, ys, '#51846b'))
    ylabel = ('Cumulative ' if options['cumulative'] else '') + scale
    return dict(kind='histogram', title='', xlabel='', ylabel=ylabel,
                edges=edges, counts=counts, curves=curves, specs=[])
