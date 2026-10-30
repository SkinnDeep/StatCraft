"""Align lifetime and censor columns by worksheet row before reliability fitting.

Blank rows are omitted as pairs. Invalid nonblank values are rejected rather
than silently reclassified as failures. Row indices are zero based and refer to
original worksheet rows, including when a column has trailing missing cells.
"""
import math
from .analysis_bindings import KEY, normalize, resolve


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value, row, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be numeric at worksheet row {row + 1}.')
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f'{label} must be finite at worksheet row {row + 1}.') from error
    if not math.isfinite(value):
        raise ValueError(f'{label} must be finite at worksheet row {row + 1}.')
    return value


def prepare_inputs(sheet, settings):
    """Return aligned inputs and row provenance without modifying source data.

    A selected censor column participates in complete-case omission. A shorter
    column supplies trailing missing cells, consistent with worksheet semantics.
    With no censor_value, codes must be 0/1 (numeric or text). With a specified
    censor_value, that exact numeric/text value denotes censoring; other finite
    numeric or nonblank text values denote observed failures.
    """
    if not isinstance(settings, dict):
        raise ValueError('Reliability analysis requires settings.')
    cfg = resolve('reliability_distribution', sheet, settings) if KEY in settings else normalize('reliability_distribution', sheet, settings)
    time_index = cfg['column_index']
    censor_index = cfg.get('censor_index')
    if censor_index is not None and censor_index == time_index:
        raise ValueError('Lifetime and censoring must use separate columns.')
    time_column = sheet.columns[time_index]
    censor_column = sheet.columns[censor_index] if censor_index is not None else None
    censor_value = cfg.get('censor_value') if censor_column is not None else None
    if censor_value is not None:
        if isinstance(censor_value, bool) or not isinstance(censor_value, (str, int, float)):
            raise ValueError('Censoring value must be a finite number or nonblank text.')
        if isinstance(censor_value, str) and not censor_value.strip():
            raise ValueError('Censoring value must not be blank.')
        if isinstance(censor_value, (int, float)):
            try:
                valid = math.isfinite(float(censor_value))
            except (OverflowError, ValueError):
                valid = False
            if not valid:
                raise ValueError('Censoring value must be finite.')
    times, codes, used, omitted = [], [], [], []
    row_count = max(len(time_column.values), len(censor_column.values) if censor_column else 0)
    for row in range(row_count):
        time = time_column.values[row] if row < len(time_column.values) else None
        code = censor_column.values[row] if censor_column and row < len(censor_column.values) else None
        if _missing(time) or (censor_column is not None and _missing(code)):
            omitted.append(row)
            continue
        time = _number(time, row, 'Lifetime')
        if time <= 0:
            raise ValueError(f'Lifetime must be positive at worksheet row {row + 1}.')
        if censor_column is not None:
            if isinstance(code, bool) or not isinstance(code, (str, int, float)):
                raise ValueError(f'Invalid censoring code at worksheet row {row + 1}.')
            if isinstance(code, (int, float)):
                _number(code, row, 'Censoring code')
            if censor_value is None:
                if code not in (0, 1, '0', '1'):
                    raise ValueError(f'Censoring code must be 0 or 1 at worksheet row {row + 1}.')
                code = int(code)
            codes.append(code)
        times.append(time)
        used.append(row)
    return {'time_values': times, 'censor_values': codes if censor_column is not None else None,
            'censor_value': censor_value, 'row_indices': used, 'omitted_rows': omitted,
            'invalid_count': 0, 'settings': cfg}
