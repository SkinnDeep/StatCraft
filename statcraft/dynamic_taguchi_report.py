"""Readable dynamic Taguchi methods, run fits, response tables and model reports."""
from .taguchi_analysis_report import sections as static_sections, display


def sections(result):
    # Response tables and GLM subsections share the static report's typed schema.
    compatible = dict(result, options=dict(result['options'], sn_type='Dynamic'))
    tables = static_sections(compatible)
    options = result['options']
    tables[0] = ('Method', ['Setting', 'Value'], [
        ['Analysis', 'Dynamic Taguchi'], ['Response columns', ', '.join(result['response_names'])],
        ['Signal values (response-column order)', ', '.join(display(value) for value in result['signal_values'])],
        ['Line reference', 'Fitted intercept' if options['reference_method'] == 'none' else 'Fixed point'],
        ['Reference signal', options['reference_signal'] if options['reference_method'] == 'fixed' else 'Not fixed'],
        ['Reference response', options['reference_response'] if options['reference_method'] == 'fixed' else 'Not fixed'],
        ['S/N formula', result['sn_formula']], ['Complete runs', result['n_runs']],
        ['Measurements per run', result['measurements_per_run']],
        ['Omitted worksheet rows', ', '.join(str(row + 1) for row in result['omitted_rows']) or 'None'],
    ])
    tables.insert(1, ('Dynamic Run Fits', ['Worksheet row', 'Slope', 'Intercept', 'Residual SD', 'Error DF', 'MSE', 'S/N'],
                     [[row['row'] + 1, row['slope'], row['intercept'], row['residual_sd'], row['df_error'], row['mse'], row['sn']] for row in result['rows']]))
    unavailable = [[row['row'] + 1, row['sn_note']] for row in result['rows'] if row.get('sn_note')]
    if unavailable:
        tables.insert(2, ('Unavailable Run Statistics', ['Worksheet row', 'Reason'], unavailable))
    return tables


def text_report(result):
    lines = []
    for heading, headers, rows in sections(result):
        data = [[display(value) for value in row] for row in rows]
        widths = [min(90, max(len(str(headers[i])), max((len(row[i]) for row in data), default=0))) for i in range(len(headers))]
        lines.extend([heading, '  '.join(str(value).ljust(width) for value, width in zip(headers, widths))])
        lines.extend('  '.join(value.ljust(width) for value, width in zip(row, widths)) for row in data)
        lines.append('')
    lines.extend(result.get('notes', []))
    return '\n'.join(lines)


format_dynamic_taguchi_report = text_report
