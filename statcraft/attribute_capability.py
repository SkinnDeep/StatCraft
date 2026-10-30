"""Original attribute capability estimates, exact intervals and chart diagnostics.

Pooled rates and Process Z follow published capability definitions. Intervals use
Clopper-Pearson (binomial) and Garwood (Poisson), independently of historical
parameters. Full native option equivalence has not been established.
"""
import math
from scipy.stats import beta, chi2, norm

DEFAULT_OPTIONS = {'confidence': 95.0, 'interval_type': 'two_sided',
                   'historical': None, 'target': 0.0, 'title': '', 'show_graphs': True}
MAX_EXACT_INTEGER = 2 ** 53


def _number(value, label, integer=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be numeric.')
    if integer and isinstance(value, int) and value > MAX_EXACT_INTEGER:
        raise ValueError(f'{label} must be a whole number no greater than 2^53.')
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{label} exceeds the supported numeric range.') from exc
    if not math.isfinite(result):
        raise ValueError(f'{label} must be finite.')
    if result < 0 or (positive and result == 0):
        raise ValueError(f'{label} must be {"positive" if positive else "nonnegative"}.')
    if integer and (not result.is_integer() or result > MAX_EXACT_INTEGER):
        raise ValueError(f'{label} must be a whole number no greater than 2^53.')
    return int(result) if integer else result


def _column(worksheet, index, label):
    if type(index) is not int or not 0 <= index < len(worksheet.columns):
        raise ValueError(f'Select a valid {label} column.')
    column = worksheet.columns[index]
    if column.kind != 'number':
        raise ValueError(f'The {label} column must be numeric.')
    return column


def _z(value):
    if value == 0:
        return None, '+Infinity'
    if value == 1:
        return None, '-Infinity'
    result = float(norm.isf(value))
    return result, f'{result:.8g}'


def analyze(worksheet, method, count_index, sample_size=1.0, size_index=None, options=None):
    """Analyze aligned complete pairs with one-based source rows.

    Confidence is a percentage. Binomial historical and target values are
    proportions; Poisson historical/target values are defects per unit. Positive
    fractional sample exposures are supported for Poisson. Missing pairs are
    omitted together. Historical parameters affect chart limits, not observed
    estimates or their confidence intervals. Only the three-sigma test is used.
    """
    if method not in ('binomial', 'poisson'):
        raise ValueError('Method must be binomial or poisson.')
    if options is not None and not isinstance(options, dict):
        raise ValueError('Options must be an object.')
    opts = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(opts)
        if unknown:
            raise ValueError('Unknown capability options: ' + ', '.join(sorted(str(key) for key in unknown)))
        opts.update(options)
    confidence = _number(opts['confidence'], 'Confidence level', positive=True)
    if confidence >= 100:
        raise ValueError('Confidence level must be strictly between 0 and 100.')
    interval_type = opts['interval_type']
    if interval_type not in ('two_sided', 'lower', 'upper'):
        raise ValueError('Interval type must be two_sided, lower, or upper.')
    if not isinstance(opts['title'], str) or type(opts['show_graphs']) is not bool:
        raise ValueError('Title must be text and show_graphs must be Boolean.')
    historical = opts['historical']
    if historical is not None:
        historical = _number(historical, 'Historical rate')
        if method == 'binomial' and historical > 1:
            raise ValueError('Historical proportion must be between 0 and 1.')
    target = opts['target']
    if target is not None:
        target = _number(target, 'Target')
        if method == 'binomial' and target > 1:
            raise ValueError('Target proportion must be between 0 and 1.')
    count_column = _column(worksheet, count_index, 'count')
    size_column = _column(worksheet, size_index, 'sample-size') if size_index is not None else None
    if size_index == count_index:
        raise ValueError('Counts and sample sizes must use different columns.')
    constant = None
    if size_column is None:
        constant = _number(sample_size, 'Sample size', integer=method == 'binomial', positive=True)
    counts, sizes, rows, omitted = [], [], [], []
    row_count = max(len(count_column.values), len(size_column.values) if size_column else 0)
    for index in range(row_count):
        count = count_column.values[index] if index < len(count_column.values) else None
        size = (size_column.values[index] if index < len(size_column.values) else None) if size_column else constant
        if count is not None:
            count = _number(count, f'Count in row {index + 1}', integer=True)
        if size is not None:
            size = _number(size, f'Sample size in row {index + 1}', integer=method == 'binomial', positive=True)
        if count is None or size is None:
            omitted.append(index + 1)
            continue
        if method == 'binomial' and count > size:
            raise ValueError(f'Defectives exceed sample size in row {index + 1}.')
        counts.append(count)
        sizes.append(size)
        rows.append(index + 1)
    if not counts:
        raise ValueError('At least one complete count and sample-size pair is required.')
    total_count = sum(counts)
    try:
        total_size = sum(sizes) if method == 'binomial' else math.fsum(sizes)
    except OverflowError as exc:
        raise ValueError('Total sample size exceeds the supported numeric range.') from exc
    if total_count > MAX_EXACT_INTEGER or not math.isfinite(total_size):
        raise ValueError('Totals exceed the supported numeric range.')
    if method == 'binomial' and total_size > MAX_EXACT_INTEGER:
        raise ValueError('Total binomial sample size exceeds 2^53.')
    observed = total_count / total_size
    rates = [c / n for c, n in zip(counts, sizes)]
    alpha = 1.0 - confidence / 100.0
    tail = alpha / 2 if interval_type == 'two_sided' else alpha
    if method == 'binomial':
        lower = float(beta.ppf(tail, total_count, total_size - total_count + 1)) if total_count else 0.0
        upper = float(beta.isf(tail, total_count + 1, total_size - total_count)) if total_count < total_size else 1.0
        if interval_type == 'lower':
            upper = 1.0
        elif interval_type == 'upper':
            lower = 0.0
    else:
        lower = float(chi2.ppf(tail, 2 * total_count)) * 0.5 / total_size if total_count else 0.0
        upper = float(chi2.isf(tail, 2 * (total_count + 1))) * 0.5 / total_size
        if interval_type == 'lower':
            upper = None
        elif interval_type == 'upper':
            lower = 0.0
    chart_rate = observed if historical is None else historical
    lcl, ucl, cumulative = [], [], []
    cumulative_count, cumulative_size = 0, 0.0
    for count, size in zip(counts, sizes):
        variance = chart_rate * (1 - chart_rate) if method == 'binomial' else chart_rate
        delta = 3 * math.sqrt(variance / size)
        lcl.append(max(0.0, chart_rate - delta))
        upper_limit = chart_rate + delta
        ucl.append(min(1.0, upper_limit) if method == 'binomial' else upper_limit)
        cumulative_count += count
        cumulative_size += size
        cumulative.append(cumulative_count / cumulative_size)
    all_numbers = [observed, *rates, *cumulative, *lcl, *ucl, lower]
    if upper is not None:
        all_numbers.append(upper)
    if not all(math.isfinite(value) for value in all_numbers):
        raise ValueError('Rates or confidence bounds exceed the supported numeric range.')
    z, z_label = _z(observed) if method == 'binomial' else (None, '')
    z_bounds = [_z(upper), _z(lower)] if method == 'binomial' else [(None, ''), (None, '')]
    title = opts['title'].strip() or f'{method.title()} Capability Analysis of {count_column.name or "C" + str(count_index + 1)}'
    notes = ['Control-chart signals use only points outside three-sigma limits.',
             'Confidence intervals estimate the observed pooled rate independently of historical parameters.']
    if omitted:
        notes.append(f'{len(omitted)} incomplete rows were omitted as aligned pairs.')
    return {
        'analysis': 'attribute_capability', 'method': method, 'title': title,
        'options': opts, 'count_name': count_column.name or f'C{count_index + 1}',
        'size_name': (size_column.name or f'C{size_index + 1}') if size_column else f'Constant {constant:g}',
        'count_index': count_index, 'size_index': size_index,
        'counts': counts, 'sample_sizes': sizes, 'rows': rows, 'omitted_rows': omitted,
        'rates': rates, 'cumulative_rates': cumulative,
        'n_samples': len(counts), 'total_count': total_count, 'total_size': total_size,
        'observed_rate': observed, 'historical_rate': historical, 'chart_rate': chart_rate,
        'target': target, 'target_percent': target * 100 if target is not None and method == 'binomial' else None,
        'confidence': confidence, 'interval_type': interval_type,
        'rate_ci': [lower, upper],
        'percent_defective': observed * 100 if method == 'binomial' else None,
        'ppm_defective': observed * 1_000_000 if method == 'binomial' else None,
        'percent_ci': [lower * 100, upper * 100] if method == 'binomial' else None,
        'ppm_ci': [lower * 1_000_000, upper * 1_000_000] if method == 'binomial' else None,
        'process_z': z, 'process_z_label': z_label,
        'process_z_ci': [value[0] for value in z_bounds],
        'process_z_ci_labels': [value[1] for value in z_bounds],
        'mean_defects': total_count / len(counts),
        'mean_dpu': observed if method == 'poisson' else None,
        'min_dpu': min(rates) if method == 'poisson' else None,
        'max_dpu': max(rates) if method == 'poisson' else None,
        'lcl': lcl, 'ucl': ucl, 'center_line': [chart_rate] * len(counts),
        'violations': [row for row, rate, lo, hi in zip(rows, rates, lcl, ucl) if rate < lo or rate > hi],
        'notes': notes,
    }


