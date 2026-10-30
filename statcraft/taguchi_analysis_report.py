"""Readable shared static Taguchi reports, including available GLM sections."""


def display(value):
    if value is None:
        return '*'
    if isinstance(value, float):
        return format(value, '.7g')
    return str(value)


def sections(result):
    tables = [('Method', ['Setting', 'Value'], [
        ['Analysis', 'Static Taguchi'], ['Response columns', ', '.join(result['response_names'])],
        ['S/N goal', result['options']['sn_type']], ['S/N formula', result['sn_formula']],
        ['Complete runs', result['n_runs']], ['Response measurements per run', result['measurements_per_run']],
        ['Omitted worksheet rows', ', '.join(str(row + 1) for row in result['omitted_rows']) or 'None']])]
    for metric, table in result['response_tables'].items():
        factors = table['factors']
        count = max(len(factor['levels']) for factor in factors)
        headers = ['Level'] + [factor['name'] for factor in factors]
        rows = []
        for index in range(count):
            rows.append([index + 1] + [factor['levels'][index]['value'] if index < len(factor['levels']) else None for factor in factors])
        rows.extend([['Delta'] + [factor['delta'] for factor in factors], ['Rank'] + [factor['rank'] for factor in factors]])
        tables.append(('Response Table for ' + table['label'], headers, rows))
        tables.append(('Factor Levels for ' + table['label'], ['Factor', 'Level', 'Setting', 'Runs', 'Available'],
                       [[factor['name'], index + 1, entry['label'], entry['count'], entry['available']]
                        for factor in factors for index, entry in enumerate(factor['levels'])]))
    tables.append(('Marginal Settings That Maximize S/N', ['Factor', 'Tied best levels', 'Mean S/N'],
                   [[item['factor_name'], ', '.join(map(str, item['levels'])) or '*', item['sn']] for item in result['optimum_settings']]))
    if result.get('models'):
        from .glm_report import sections as glm_sections
        for metric, model in result['models'].items():
            title = result['response_tables'][metric]['label']
            if model is None:
                tables.append(('Main-Effects Model for ' + title, ['Status', 'Reason'], [['Unavailable', result['model_unavailable'].get(metric, 'Not estimable')]]))
            else:
                for heading, headers, rows in glm_sections(model):
                    tables.append((title + ': ' + heading, headers, rows))
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


format_taguchi_report = text_report
