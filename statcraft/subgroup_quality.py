"""Original equal-size Xbar-R charts; published rounded constants, Test 1 only.

Contracts and primary sources: outputs/statcraft-subgroup-quality-contracts.md.
Native exact constants, defaults and full application parity are unverified.
"""
import math
from .engine import normalize_numeric, MISSING_SENTINEL

# Official published d2/d3 table, n=2..10; retain its stated decimal precision.
RANGE_CONSTANTS = {
    2: (1.128, .8525), 3: (1.693, .8884), 4: (2.059, .8798),
    5: (2.326, .8641), 6: (2.534, .8480), 7: (2.704, .8332),
    8: (2.847, .8198), 9: (2.970, .8078), 10: (3.078, .7971),
}


def _finite(value):
    if not math.isfinite(value):
        raise ValueError('Xbar-R arithmetic exceeds the supported numeric range.')
    return value


def _value(value):
    result = normalize_numeric(value)
    # Nonfinite values are input errors here, rather than silently deleted cells.
    if value is not None and result is None and value != MISSING_SENTINEL:
        raise ValueError('Xbar-R observations must be finite; use None for missing cells.')
    return result


def xbar_r(subgroups):
    """Each list is one equal-size subgroup (2..10 cells).

    Wholly missing groups preserve None gaps. Partly missing groups, ragged
    sizing, bool/text/nonfinite cells and no complete groups are rejected.
    Historical parameters, stages and tests other than Test 1 are unsupported.
    """
    groups = [list(group) for group in subgroups]
    if not groups:
        raise ValueError('Xbar-R requires at least one complete subgroup.')
    n = len(groups[0])
    if n not in RANGE_CONSTANTS:
        raise ValueError('Xbar-R subgroup size must be between 2 and 10.')
    if any(len(group) != n for group in groups):
        raise ValueError('Xbar-R requires equal-size subgroups, including wholly missing gaps.')
    means, ranges, indices, normalized = [], [], [], []
    try:
        for row, group in enumerate(groups):
            values = [_value(v) for v in group]
            normalized.append(values)
            missing = sum(v is None for v in values)
            if missing == n:
                means.append(None); ranges.append(None)
            elif missing:
                raise ValueError(f'Subgroup {row+1} is partly missing; each subgroup must be complete or wholly missing.')
            else:
                means.append(_finite(math.fsum(v/n for v in values)))
                ranges.append(_finite(max(values)-min(values)))
                indices.append(row)
        count = len(indices)
        if not count:
            raise ValueError('Xbar-R requires at least one complete subgroup.')
        center = _finite(math.fsum(means[i]/count for i in indices))
        average_range = _finite(math.fsum(ranges[i]/count for i in indices))
        d2, d3 = RANGE_CONSTANTS[n]
        sigma = _finite(average_range/d2)
        mean_width = _finite((sigma/math.sqrt(n))*3)
        range_width = _finite((d3*sigma)*3)
        xlow, xhigh = _finite(center-mean_width), _finite(center+mean_width)
        rlow, rhigh = max(0., _finite(average_range-range_width)), _finite(average_range+range_width)
    except OverflowError as exc:
        raise ValueError('Xbar-R arithmetic exceeds the supported numeric range.') from exc
    warnings = []
    if count == 1:
        warnings.append('Only one complete subgroup: estimated limits are preliminary.')
    if sigma == 0:
        warnings.append('Zero estimated within-subgroup variation: control limits coincide.')
    return dict(method='Equal-size Xbar-R; average range/d2; three-sigma limits; Test 1 only',
                subgroups=normalized, means=means, ranges=ranges, count=count,
                missing=len(groups)-count, row_indices=indices, subgroup_size=n,
                within_stdev=sigma, d2=d2, d3=d3,
                xbar_center=center, xbar_lcl=xlow, xbar_ucl=xhigh,
                r_center=average_range, r_lcl=rlow, r_ucl=rhigh,
                xbar_signals=[i+1 for i in indices if means[i]<xlow or means[i]>xhigh],
                r_signals=[i+1 for i in indices if ranges[i]<rlow or ranges[i]>rhigh],
                warnings=warnings,
                missing_policy='Wholly missing equal-size subgroups retain gaps; partly missing subgroups and nonfinite observations are rejected.',
                assumptions='Independent rational subgroups; independent approximately normal observations within equal-size subgroups, with a common within-subgroup variance.')
