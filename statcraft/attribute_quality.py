"""Original standard P/U charts: weighted centers, 3-sigma limits, Test 1 only.

Official formula contracts and explicit local policies are in
outputs/statcraft-attribute-quality-contracts.md. Native parity is unverified.
"""
import math
import numbers
from .engine import normalize_numeric

MAX_EXACT_COUNT = 2**53


def _count(value, label):
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        if value < 0 or value > MAX_EXACT_COUNT:
            raise ValueError(label + ' must be a nonnegative integer no greater than 2^53.')
    value = normalize_numeric(value)
    if value is None:
        return None
    if value < 0 or not value.is_integer() or value > MAX_EXACT_COUNT:
        raise ValueError(label + ' must be a nonnegative integer no greater than 2^53.')
    return int(value)


def _finite(value):
    if not math.isfinite(value):
        raise ValueError('Attribute chart arithmetic exceeds the supported numeric range.')
    return value


def _chart(counts, sizes, kind):
    counts, sizes = list(counts), list(sizes)
    if len(counts) != len(sizes):
        raise ValueError('Counts and sample sizes must have the same row count.')
    normalized_counts, normalized_sizes, indices = [], [], []
    for row, (c, size) in enumerate(zip(counts, sizes)):
        c = _count(c, f'Count at row {row+1}')
        size = (_count(size, f'Trials at row {row+1}') if kind == 'P'
                else normalize_numeric(size))
        if size is not None and size <= 0:
            raise ValueError(f'Sample size/exposure at row {row+1} must be positive.')
        if c is not None and size is not None and kind == 'P' and c > size:
            raise ValueError(f'Defective count at row {row+1} cannot exceed trials.')
        # Validation precedes pair omission: an invalid nonmissing partner errors.
        if c is None or size is None:
            normalized_counts.append(None); normalized_sizes.append(None)
        else:
            normalized_counts.append(c); normalized_sizes.append(size); indices.append(row)
    if not indices:
        raise ValueError('Attribute charts require at least one complete subgroup.')
    total_count = sum(normalized_counts[i] for i in indices)
    try:
        total_size = _finite(math.fsum(normalized_sizes[i] for i in indices))
        center = _finite(total_count / total_size)
    except OverflowError as exc:
        raise ValueError('Attribute chart totals exceed the supported numeric range.') from exc
    if total_count and center == 0:
        raise ValueError('Attribute rate is below the supported numeric range.')
    if kind == 'P':
        center = min(1., max(0., center))
    observations, centers, lcl, ucl, flags = [], [], [], [], []
    for c, size in zip(normalized_counts, normalized_sizes):
        if c is None:
            observations.append(None); centers.append(None)
            lcl.append(None); ucl.append(None); flags.append(None)
            continue
        rate = _finite(c / size)
        # Separate square roots prevent variance underflow before square root.
        sigma = (math.sqrt(center) * math.sqrt(1-center) / math.sqrt(size)
                 if kind == 'P' else math.sqrt(center) / math.sqrt(size))
        width = _finite(3*sigma)
        low = max(0., _finite(center-width))
        high = (min(1., center+width) if kind == 'P' else _finite(center+width))
        observations.append(rate); centers.append(center)
        lcl.append(low); ucl.append(high); flags.append(rate < low or rate > high)
    warnings = []
    if len(indices) == 1:
        warnings.append('Only one complete subgroup: estimated limits are preliminary.')
    if center == 0 or (kind == 'P' and center == 1):
        warnings.append('Estimated binomial/Poisson variation is zero; control limits coincide.')
    return dict(chart=kind, method=f'{kind} chart; weighted center; three-sigma limits; Test 1 only',
                count=len(indices), missing=len(counts)-len(indices), row_indices=indices,
                counts=normalized_counts, sample_sizes=normalized_sizes,
                total_count=total_count, total_sample_size=total_size,
                observations=observations, center=center, center_line=centers,
                lcl=lcl, ucl=ucl, signal_flags=flags,
                signals=[i+1 for i, flag in enumerate(flags) if flag is True],
                missing_policy='A missing count or denominator omits the entire subgroup; worksheet gaps remain None in every chart array.',
                assumptions=('Independent binomial trials with common defective probability across subgroups.'
                             if kind == 'P' else 'Independent Poisson defect counts with a common rate per exposure unit.'),
                warnings=warnings)


def p_chart(defectives, trials):
    """Proportions of defective items; trials must be positive integer counts."""
    return _chart(defectives, trials, 'P')


def u_chart(defects, exposure):
    """Defects per unit; positive exposure can represent fractional units."""
    return _chart(defects, exposure, 'U')
