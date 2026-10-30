"""Readable sections for original Scheffe mixture-response fits."""


def _fmt(value):
    return '*' if value is None else f'{value:.7g}' if isinstance(value,(int,float)) else str(value)


def sections(result):
    result=result.get('result',result)
    yield ('Model Summary',['N','Terms','S','R-sq','R-sq(adj)','Error DF'],[[result['count'],len(result['coefficients']),result['residual_stdev'],result['r_squared'],result['adjusted_r_squared'],result['df_error']]])
    yield ('Coefficients (normalized raw component proportions)',['Term','Coefficient','SE Coef','T','P','Lower CI','Upper CI'],[[row[key] for key in ('name','estimate','standard_error','t','p_value','ci_low','ci_high')] for row in result['coefficients']])
    yield ('Analysis of Variance (corrected for mean)',['Source','DF','SS','MS','F','P'],[[row[key] for key in ('source','df','ss','ms','f','p_value')] for row in result['anova']])


def format_mixture_report(entry):
    result=entry.get('result',entry)
    lines=[result['title'],f"Model: {result['model'].replace('_',' ')}",f"Fixed component total: {_fmt(result['total'])}",
           'No independent intercept; the component sum supplies the constant-response direction.','']
    for heading,headers,rows in sections(result):
        lines.extend([heading,' | '.join(headers)])
        lines.extend(' | '.join(_fmt(value) for value in row) for row in rows)
        lines.append('')
    lines.append('Method Notes')
    lines.extend(result['warnings'])
    return '\n'.join(lines)
