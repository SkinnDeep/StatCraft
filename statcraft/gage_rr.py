"""Independent balanced crossed Gage R&R, random two-factor ANOVA method.

Method reference: StatCraft official Crossed Gage R&R methods/formulas, method of
analysis and gage R&R table. This implements a bounded documented method, not
native product equivalence. Historical SD is a %Process denominator only; it
does not replace the study's estimated variance components. No confidence
intervals, Xbar-R estimation, nested designs, or unbalanced mixed models.
"""
import math
import numpy as np
from scipy.stats import f as f_distribution
from .value_order import ordered_values


DEFAULTS = dict(study_multiplier=6.0, tolerance=None, process_stdev=None,
                interaction_alpha=0.05, remove_interaction=True)


def settings(options=None):
    if options is None:
        return dict(DEFAULTS)
    if not isinstance(options, dict) or set(options) - set(DEFAULTS):
        raise ValueError('Unsupported crossed Gage R&R options.')
    result = dict(DEFAULTS, **options)
    for key in ('study_multiplier', 'tolerance', 'process_stdev', 'interaction_alpha'):
        value = result[key]
        if value is None and key in ('tolerance', 'process_stdev'):
            continue
        try:
            converted = float(value) if type(value) in (int, float) else float('nan')
        except (OverflowError, ValueError):
            converted = float('nan')
        if not math.isfinite(converted) or converted <= 0:
            raise ValueError(key.replace('_', ' ').capitalize() + ' must be a finite positive number.')
        result[key] = converted
    if result['interaction_alpha'] >= 1:
        raise ValueError('Interaction alpha must be between zero and one.')
    if type(result['remove_interaction']) is not bool:
        raise ValueError('Remove interaction must be true or false.')
    return result


def _test(numerator, denominator, numerator_df, denominator_df):
    if denominator == 0:
        # A finite JSON result; a positive numerator over zero has limiting p=0.
        return None, 0.0 if numerator > 0 else None
    statistic = numerator / denominator
    return (statistic if math.isfinite(statistic) else None,
            float(f_distribution.sf(statistic, numerator_df, denominator_df)))


def _row(source, df, ss, denominator=None, denominator_df=None):
    ms = ss / df if source != 'Total' else None
    statistic, probability = ((None, None) if denominator is None else
                             _test(ms, denominator, df, denominator_df))
    return dict(source=source, df=df, ss=ss, ms=ms, f=statistic, p_value=probability)


def analyze(worksheet, measurement_index, part_index, operator_index, options=None):
    """Fit balanced crossed data after aligned omission of incomplete rows.

    Factors may be numeric or text. Each observed part must be measured by each
    observed operator with the same number (at least two) of replicates.
    Undefined percentages and unlimited distinct categories return None.
    """
    o = settings(options)
    indices = [measurement_index, part_index, operator_index]
    if (any(type(i) is not int or not 0 <= i < len(worksheet.columns) for i in indices)
            or len(set(indices)) != 3):
        raise ValueError('Choose three distinct columns for measurements, parts, and operators.')
    measurement, part, operator = [worksheet.columns[i] for i in indices]
    if measurement.kind != 'number' or any(c.kind not in ('number', 'text') for c in (part, operator)):
        raise ValueError('Measurements must be numeric; parts and operators must be numeric or text.')
    for column in (measurement, part, operator):
        column.validate()
    length = max(len(c.values) for c in (measurement, part, operator))
    if length > 200000:
        raise ValueError('Crossed Gage R&R supports at most 200,000 input rows.')
    rows = [r for r in range(length)
            if all(r < len(c.values) and c.values[r] is not None for c in (measurement, part, operator))]
    parts = ordered_values(part, [part.values[r] for r in rows])
    operators = ordered_values(operator, [operator.values[r] for r in rows])
    p, q = len(parts), len(operators)
    if p < 2 or q < 2:
        raise ValueError('A crossed study needs at least two observed parts and two operators.')
    if p * q > 50000:
        raise ValueError('Crossed Gage R&R supports at most 50,000 part/operator cells.')
    cells = {(a, b): [] for a in parts for b in operators}
    for row in rows:
        cells[part.values[row], operator.values[row]].append(float(measurement.values[row]))
    counts = {len(values) for values in cells.values()}
    if len(counts) != 1 or min(counts) < 2:
        raise ValueError('Use a complete balanced crossed study with at least two equal repeats in every part/operator cell after missing rows are omitted.')
    repeats = counts.pop()
    data = np.asarray([[cells[a, b] for b in operators] for a in parts], dtype=float)
    # Center first to avoid large measurement offsets contaminating small SS.
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            centered = data - data[0, 0, 0]
            cell_mean = centered.mean(axis=2)
            part_mean, operator_mean = centered.mean(axis=(1, 2)), centered.mean(axis=(0, 2))
            grand = float(centered.mean())
            ss_part = float(q * repeats * np.sum((part_mean - grand) ** 2))
            ss_operator = float(p * repeats * np.sum((operator_mean - grand) ** 2))
            ss_interaction = float(repeats * np.sum((cell_mean - part_mean[:, None] - operator_mean[None, :] + grand) ** 2))
            ss_error = float(np.sum((centered - cell_mean[:, :, None]) ** 2))
            ss_total = float(np.sum((centered - grand) ** 2))
        except FloatingPointError as exc:
            raise ValueError('Measurement arithmetic exceeds the supported floating-point range.') from exc
    df_part, df_operator, df_interaction, df_error = p - 1, q - 1, (p - 1) * (q - 1), p * q * (repeats - 1)
    ms_part, ms_operator = ss_part / df_part, ss_operator / df_operator
    ms_interaction, ms_error = ss_interaction / df_interaction, ss_error / df_error
    full = [_row('Part', df_part, ss_part, ms_interaction, df_interaction),
            _row('Operator', df_operator, ss_operator, ms_interaction, df_interaction),
            _row('Part * Operator', df_interaction, ss_interaction, ms_error, df_error),
            _row('Repeatability', df_error, ss_error), _row('Total', len(rows) - 1, ss_total)]
    interaction_p = full[2]['p_value']
    pooled = bool(o['remove_interaction'] and interaction_p is not None and interaction_p >= o['interaction_alpha'])
    reduced = []
    if pooled:
        pooled_df = df_interaction + df_error
        pooled_ss = ss_interaction + ss_error
        denominator = pooled_ss / pooled_df
        reduced = [_row('Part', df_part, ss_part, denominator, pooled_df),
                   _row('Operator', df_operator, ss_operator, denominator, pooled_df),
                   _row('Repeatability', pooled_df, pooled_ss), _row('Total', len(rows) - 1, ss_total)]
        repeat_variance = denominator
        interaction_variance = 0.0
    else:
        denominator = ms_interaction
        repeat_variance = ms_error
        interaction_variance = max(0.0, (ms_interaction - ms_error) / repeats)
    operator_variance = max(0.0, (ms_operator - denominator) / (p * repeats))
    part_variance = max(0.0, (ms_part - denominator) / (q * repeats))
    reproducibility = operator_variance + interaction_variance
    grr = repeat_variance + reproducibility
    total = grr + part_variance
    definitions = [('total_grr', 'Total Gage R&R', grr), ('repeatability', 'Repeatability', repeat_variance),
                   ('reproducibility', 'Reproducibility', reproducibility), ('operator', 'Operator', operator_variance)]
    if not pooled:
        definitions.append(('interaction', 'Part * Operator', interaction_variance))
    definitions += [('part_to_part', 'Part-To-Part', part_variance), ('total', 'Total Variation', total)]
    components = []
    for key, source, variance in definitions:
        sd = math.sqrt(variance)
        study = o['study_multiplier'] * sd
        components.append(dict(key=key, source=source, variance=variance, sd=sd, study_variation=study,
            percent_contribution=100 * (variance / total) if total else None,
            percent_study_variation=100 * (sd / math.sqrt(total)) if total else None,
            percent_tolerance=100 * (study / o['tolerance']) if o['tolerance'] is not None else None,
            percent_process=100 * (sd / o['process_stdev']) if o['process_stdev'] is not None else None))
    if not all(value is None or not isinstance(value, float) or math.isfinite(value)
               for component in components for value in component.values()):
        raise ValueError('Study variation or percentage arithmetic exceeds the supported range.')
    ratio = 1.41 * math.sqrt(part_variance) / math.sqrt(grr) if grr else None
    ndc = max(1, math.floor(ratio)) if ratio is not None and math.isfinite(ratio) else (1 if part_variance == 0 else None)
    ndc_note = ('Undefined: all estimated variation is zero.' if total == 0 else
                'Unbounded: estimated Gage R&R variation is zero.' if grr == 0 else
                'Distinct-category ratio exceeds finite floating-point range.' if ratio is not None and not math.isfinite(ratio) else '')
    anchor = float(data[0, 0, 0])
    plot_cells = [dict(part=a, operator=b, mean=anchor + float(cell_mean[i, j]),
                       range=max(cells[a, b]) - min(cells[a, b]), values=cells[a, b])
                  for i, a in enumerate(parts) for j, b in enumerate(operators)]
    return dict(analysis='gage_rr', method='Balanced crossed random-effects ANOVA',
        measurement=measurement.name, part=part.name, operator=operator.name,
        labels=dict(measurement=measurement.name, part=part.name, operator=operator.name),
        settings=o, options=o, n=len(rows), missing=length - len(rows), row_indices=rows,
        parts=parts, operators=operators, repeats=repeats,
        anova=reduced if pooled else full, anova_with_interaction=full, anova_without_interaction=reduced,
        interaction=dict(pooled=pooled, p_value=interaction_p, alpha=o['interaction_alpha']),
        variance_components=components, study_variation=[dict(c) for c in components], ndc=ndc, ndc_note=ndc_note,
        plot_data=dict(rows=[dict(part=part.values[r], operator=operator.values[r], value=float(measurement.values[r]), row=r) for r in rows],
            cells=plot_cells, part_means=[dict(part=a, mean=anchor + float(part_mean[i])) for i, a in enumerate(parts)],
            operator_means=[dict(operator=b, mean=anchor + float(operator_mean[j])) for j, b in enumerate(operators)]))
