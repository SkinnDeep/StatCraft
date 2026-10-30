"""Readable mixture/process model and all-role prediction reports."""
from .mixture_report import sections as base_sections,_fmt


def text_report(entry):
    r=entry.get('result',entry)
    if r['analysis']=='mixture_process_prediction':
        lines=[r['title'],'Response: '+r['response_name'],str(r['confidence']*100)+'% mean confidence and individual prediction intervals',
            'Components | Processes | Covariates | Block | Fit | SE Fit | Lower CI | Upper CI | Lower PI | Upper PI']
        lines += [' | '.join(_fmt(row[key]) for key in ('components','processes','covariates','block','fit','standard_error','ci_low','ci_high','prediction_low','prediction_high')) for row in r['rows']]
        return '\n'.join(lines+['']+r['warnings'])
    lines=[r['title'],'Mixture model: '+r['model'].replace('_',' '),'Fixed mixture total: '+_fmt(r['total']),
        'Mixture basis fully crossed with process polynomial order '+str(r['options']['process_order'])+'.',
        'No independent intercept; the component sum supplies the constant-response direction.',
        'Covariates are additive coded numeric terms; blocks are additive fixed effects.','']
    for label,names,coding in [('Process',r['process_names'],r['process_coding']),('Covariate',r['covariate_names'],r['covariate_coding'])]:
        for name,code in zip(names,coding):lines.append(label+' coding for '+name+': low '+_fmt(code['low'])+' maps to -1; high '+_fmt(code['high'])+' maps to +1.')
    if r['block_name']:
        lines+=['Fixed block: '+r['block_name'],'Observed levels: '+', '.join(map(str,r['block_levels'])),'Reference block level: '+str(r['block_reference'])]
    lines.append('')
    for heading,headers,rows in base_sections(r):
        if heading.startswith('Coefficients'):heading='Coefficients (raw component proportions; coded processes/covariates; reference block)'
        lines.extend([heading,' | '.join(headers)]);lines.extend(' | '.join(_fmt(value) for value in row) for row in rows);lines.append('')
    lines.extend(r['warnings'])
    return '\n'.join(lines)


format_mixture_process_report=text_report
