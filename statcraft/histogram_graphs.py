"""Original grouped histogram snapshots; native numerical equivalence is unverified.

Groups share equal-width intervals within each response. Percent and Density
normalize within each observed group, including when several groups overlap.
Missing response/group pairs are omitted independently for each response.
"""
import bisect
import math
from statistics import NormalDist, mean, stdev

from .histogram_options import build_histogram_panel, validate_histogram_settings
from .model import finite_number
from .value_order import ordered_values

VARIANTS = ('simple', 'fit', 'groups', 'fit_groups')
MAX_SERIES = 16
MAX_OBSERVATIONS = 100000


def validate_parameters(worksheet, response_indices, variant='simple', group_index=None,
                        layout='overlay', settings=None):
    """Validate selection/settings without changing the worksheet or graph history."""
    if variant not in VARIANTS:
        raise ValueError('Choose Simple, With Fit, With Groups, or With Fit and Groups.')
    if (not isinstance(response_indices, (list, tuple)) or
            not 1 <= len(response_indices) <= MAX_SERIES or
            any(type(i) is not int or not 0 <= i < len(worksheet.columns) for i in response_indices)):
        raise ValueError('Select from 1 to 16 numeric graph variables.')
    if len(set(response_indices)) != len(response_indices):
        raise ValueError('Select each graph variable only once.')
    for index in response_indices:
        if worksheet.columns[index].kind != 'number':
            raise ValueError('Histogram graph variables must be numeric.')
    grouped = variant in ('groups', 'fit_groups')
    if grouped:
        if (type(group_index) is not int or not 0 <= group_index < len(worksheet.columns) or
                worksheet.columns[group_index].kind not in ('number', 'text')):
            raise ValueError('Select a numeric or text grouping variable.')
        if group_index in response_indices:
            raise ValueError('The grouping variable must differ from graph variables.')
    elif group_index is not None:
        raise ValueError('Use a grouped histogram variant to select a grouping variable.')
    if layout not in ('overlay', 'panels'):
        raise ValueError('Choose overlaid groups or separate panels.')
    requested = {} if settings is None else settings
    if not isinstance(requested, dict):
        raise ValueError('Histogram settings must be an object.')
    expected_fit = 'Normal' if variant in ('fit', 'fit_groups') else None
    if 'fit' in requested and requested['fit'] != expected_fit:
        raise ValueError('Histogram fit settings must match the chosen variant.')
    options = validate_histogram_settings(dict(requested, fit=expected_fit))
    return dict(response_indices=list(response_indices), variant=variant,
                group_index=group_index, layout=layout if grouped else 'overlay', settings=options)


def _group_label(value, kind):
    return value if kind == 'text' else format(finite_number(value), '.17g')


def _series(values, rows, label, edges, options):
    width = edges[1] - edges[0]
    counts = [0] * (len(edges) - 1)
    for value in values:
        index = min(len(counts) - 1, max(0, bisect.bisect_right(edges, value) - 1))
        counts[index] += 1
    n = len(values)
    if options['cumulative']:
        for index in range(1, len(counts)):
            counts[index] += counts[index - 1]
    scale = options['scale']
    if scale == 'Percent':
        counts = [100.0 * count / n for count in counts]
    elif scale == 'Density':
        counts = [count / n / width for count in counts]
    if any(not math.isfinite(value) for value in counts):
        raise ValueError('Histogram counts exceed plotting precision.')
    curves = []
    fit_parameters = None
    if options['fit'] == 'Normal':
        if n < 2:
            raise ValueError('A Normal fit requires at least two observations in every group.')
        center, deviation = mean(values), stdev(values)
        if not math.isfinite(deviation) or deviation <= 0:
            raise ValueError('A Normal fit requires a positive sample standard deviation in every group.')
        normal = NormalDist(center, deviation)
        xs = [edges[0] + (edges[-1] - edges[0]) * i / 160 for i in range(161)]
        if options['cumulative']:
            multiplier = n if scale == 'Frequency' else 100.0
            ys = [normal.cdf(x) * multiplier for x in xs]
        else:
            multiplier = n * width if scale == 'Frequency' else 100.0 * width if scale == 'Percent' else 1.0
            ys = [normal.pdf(x) * multiplier for x in xs]
        if any(not math.isfinite(value) for value in ys):
            raise ValueError('Normal fit exceeds plotting precision.')
        curves.append(('Normal', xs, ys, '#51846b'))
        fit_parameters = dict(mean=center, stdev=deviation, n=n)
    return dict(label=label, edges=list(edges), counts=counts, curves=curves,
                source=list(values), row_indices=list(rows), n=n, fit_parameters=fit_parameters)


def build_histograms(worksheet, response_indices, variant='simple', group_index=None,
                     layout='overlay', settings=None):
    """Return detached JSON-safe data only after every group has been validated."""
    parameters = validate_parameters(worksheet, response_indices, variant, group_index, layout, settings)
    options = parameters['settings']
    grouping = worksheet.columns[group_index] if group_index is not None else None
    panels, retained, total_series = [], 0, 0
    for index in parameters['response_indices']:
        column = worksheet.columns[index]
        observations = {}
        for row, value in enumerate(column.values):
            if value is None:
                continue
            if grouping is None:
                label = column.name or 'C' + str(index + 1)
            else:
                group = grouping.values[row] if row < len(grouping.values) else None
                if group is None:
                    continue
                label = _group_label(group, grouping.kind)
            values, rows = observations.setdefault(label, ([], []))
            values.append(finite_number(value))
            rows.append(row + 1)
            retained += 1
            if retained > MAX_OBSERVATIONS:
                raise ValueError('Histogram snapshots support at most 100000 retained observations.')
        if not observations:
            raise ValueError('Every graph variable needs at least one nonmissing observation with a nonmissing group.')
        labels = ordered_values(grouping, observations) if grouping is not None else list(observations)
        total_series += len(labels)
        if total_series > MAX_SERIES:
            raise ValueError('Histograms support at most 16 response/group combinations.')
        pooled = [value for label in labels for value in observations[label][0]]
        edges = build_histogram_panel(pooled, dict(options, fit=None))['edges']
        series = [_series(*observations[label], label, edges, options) for label in labels]
        for color_index,item in enumerate(series):item['color_index']=color_index
        xlabel = column.name or 'C' + str(index + 1)
        ylabel = ('Cumulative ' if options['cumulative'] else '') + options['scale']
        common = dict(kind='histogram_groups', xlabel=xlabel, ylabel=ylabel,
                      edges=list(edges), response_index=index,
                      group_name=grouping.name if grouping is not None else '',
                      histogram_settings=dict(options))
        if grouping is not None and parameters['layout'] == 'panels':
            for group in series:
                panels.append(dict(common, title=xlabel + ' — ' + group['label'], series=[group]))
        else:
            panels.append(dict(common, title=xlabel, series=series))
    return dict(graph='histogram_graphs', panels=panels, parameters=parameters,
                title='Histogram of ' + ', '.join(worksheet.columns[i].name or 'C' + str(i + 1)
                                                for i in parameters['response_indices']),
                histogram_source=[list(series['source']) for panel in panels for series in panel['series']])


def validate_result(result):
    """Validate a saved histogram snapshot and return the original input object.

    Validation never repairs or mutates data. Raw observations and row identities
    remain snapshots; aggregate bars do not acquire point brushing capabilities.
    """
    if not isinstance(result, dict) or result.get('graph') != 'histogram_graphs':
        raise ValueError('Invalid histogram graph snapshot.')
    panels = result.get('panels')
    if not isinstance(panels, list) or not 1 <= len(panels) <= MAX_SERIES:
        raise ValueError('Histogram snapshots require from 1 to 16 panels.')
    total_series, retained = 0, 0
    for panel in panels:
        if not isinstance(panel, dict) or panel.get('kind') != 'histogram_groups':
            raise ValueError('Invalid histogram panel.')
        if any(not isinstance(panel.get(key), str) for key in ('title', 'xlabel', 'ylabel')):
            raise ValueError('Histogram labels must be text.')
        options = validate_histogram_settings(panel.get('histogram_settings'))
        edges = panel.get('edges')
        if not isinstance(edges, list) or len(edges) != options['bins'] + 1:
            raise ValueError('Histogram interval edges do not match the interval count.')
        clean_edges = [finite_number(value) for value in edges]
        if any(a >= b for a, b in zip(clean_edges, clean_edges[1:])):
            raise ValueError('Histogram edges must increase.')
        series_list = panel.get('series')
        if not isinstance(series_list, list) or not series_list:
            raise ValueError('Every histogram panel needs a series.')
        total_series += len(series_list)
        if total_series > MAX_SERIES:
            raise ValueError('Histograms support at most 16 response/group combinations.')
        labels = set()
        for series in series_list:
            if not isinstance(series, dict) or not isinstance(series.get('label'), str):
                raise ValueError('Histogram series labels must be text.')
            if type(series.get('color_index',0)) is not int or not 0<=series.get('color_index',0)<16:
                raise ValueError('Invalid histogram group color identity.')
            if series['label'] in labels:
                raise ValueError('Histogram group labels must be unique within a panel.')
            labels.add(series['label'])
            if series.get('edges') != edges:
                raise ValueError('Histogram groups must share their panel intervals.')
            counts = series.get('counts')
            if not isinstance(counts, list) or len(counts) != options['bins']:
                raise ValueError('Histogram interval counts do not match the edges.')
            if any(finite_number(value) < 0 for value in counts):
                raise ValueError('Histogram counts must be nonnegative.')
            source, rows = series.get('source'), series.get('row_indices')
            if not isinstance(source, list) or not source:
                raise ValueError('Histogram source observations are required.')
            if (not isinstance(rows, list) or len(rows) != len(source) or
                    any(type(row) is not int or row <= 0 for row in rows) or len(set(rows)) != len(rows)):
                raise ValueError('Histogram source row identities are invalid.')
            if type(series.get('n')) is not int or series['n'] != len(source):
                raise ValueError('Histogram observation count does not match its source.')
            retained += len(source)
            if retained > MAX_OBSERVATIONS:
                raise ValueError('Histogram snapshots support at most 100000 retained observations.')
            for value in source:
                number = finite_number(value)
                if not clean_edges[0] <= number <= clean_edges[-1]:
                    raise ValueError('Histogram source lies outside its intervals.')
            curves = series.get('curves')
            if not isinstance(curves, (list, tuple)) or len(curves) > 1:
                raise ValueError('Histogram fits must contain at most one Normal curve.')
            if bool(curves) != (options['fit'] == 'Normal'):
                raise ValueError('Histogram fit curve does not match its settings.')
            for curve in curves:
                if (not isinstance(curve, (list, tuple)) or len(curve) != 4 or
                        curve[0] != 'Normal' or not isinstance(curve[3], str)):
                    raise ValueError('Invalid histogram fit curve.')
                xs, ys = curve[1:3]
                if (not isinstance(xs, list) or not isinstance(ys, list) or
                        not 2 <= len(xs) <= 10000 or len(xs) != len(ys)):
                    raise ValueError('Histogram fit coordinates do not match.')
                finite_xs = [finite_number(value) for value in xs]
                if any(a >= b for a, b in zip(finite_xs, finite_xs[1:])):
                    raise ValueError('Histogram fit coordinates must increase.')
                if any(finite_number(value) < 0 for value in ys):
                    raise ValueError('Histogram fit values must be nonnegative.')
    return result
