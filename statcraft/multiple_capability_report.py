"""Readable summary and individual reports for multiple-variable capability."""


def _fmt(value):
    return '*' if value is None else f'{value:.6g}' if isinstance(value,(float,int)) else str(value)


def sections(result):
    result=result.get('result',result)
    keys=['label','n','lsl','target','usl']
    if result['method']=='normal':keys+=['cp','cpk']
    keys+=['pp','ppk','observed_ppm','expected_ppm']
    names={'label':'Variable / Group','n':'N','lsl':'LSL','target':'Target','usl':'USL',
           'cp':'Cp','cpk':'Cpk','pp':'Pp','ppk':'Ppk','observed_ppm':'Observed PPM','expected_ppm':'Expected PPM'}
    if result['method']=='normal' and result.get('options',{}).get('analysis_mode')=='between_within':
        names.update(cp='Cbw' if result['options'].get('naming_convention')=='aiag_vda' else 'Between/Within Cp',
                     cpk='Cbwk' if result['options'].get('naming_convention')=='aiag_vda' else 'Between/Within Cpk')
    if result['method']=='nonnormal' and result.get('options',{}).get('naming_convention')=='aiag_vda':
        names.update(pp='Cnp',ppk='Cnpk')
    return [('Capability Comparison',[names[key] for key in keys],[[row[key] for key in keys] for row in result['summary']])]


def format_multiple_capability_report(entry):
    result=entry.get('result',entry)
    lines=[result['title'],'']
    for title,headers,rows in sections(result):
        lines.append(title)
        lines.append(' | '.join(headers))
        lines.extend(' | '.join(_fmt(value) for value in row) for row in rows)
    lines.append('')
    for item in result['series']:
        lines.extend([item['label'],f"Rows analyzed: {len(item['rows'])}; missing: {len(item['missing_rows'])}"])
        if result['method']=='normal':
            from .capability_report import format_capability_report
            lines.append(format_capability_report(item['result']))
        else:
            from .capability_nonnormal_report import format_nonnormal_capability_report
            lines.append(format_nonnormal_capability_report({'result':item['result'],'title':item['label'],'variable_name':item['label']}))
    lines.extend(['Method Notes',*result['warnings']])
    return '\n'.join(lines)
