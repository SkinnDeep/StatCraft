"""Readable tables for the balanced crossed random-effects Gage R&R study."""


def sections(result):
    r=result; o=r.get('options',r.get('settings',{})); interaction=r['interaction']
    tables=[('Method',['Setting','Value'],[
        ['Study','Crossed Gage R&R, ANOVA method'],
        ['Measurement',r.get('measurement','Measurement')],
        ['Parts',len(r['parts'])],['Operators',len(r['operators'])],['Replicates per cell',r['repeats']],
        ['Observations',r['n']],['Incomplete rows omitted',r['missing']],
        ['Study variation multiplier',o.get('study_multiplier',6)],
        ['Part × operator interaction','Pooled into repeatability' if interaction['pooled'] else 'Retained'],
        ['Interaction removal alpha',interaction['alpha']],
        ['Tolerance width',o.get('tolerance')],['Reference process SD (%Process only)',o.get('process_stdev')],
    ])]
    for key,title in [('anova_with_interaction','Two-Way ANOVA with Interaction'),('anova','Analysis of Variance — Final Model')]:
        tables.append((title,['Source','DF','SS','MS','F-Value','P-Value'],[[a.get(k) for k in ('source','df','ss','ms','f','p_value')] for a in r[key]]))
    tables.append(('Variance Components',['Source','Variance','%Contribution'],[[a['source'],a['variance'],a.get('percent_contribution')] for a in r['variance_components']]))
    headers=['Source','StdDev (SD)','Study Var','%Study Var']; keys=['source','sd','study_variation','percent_study_variation']
    if o.get('tolerance') is not None:headers.append('%Tolerance');keys.append('percent_tolerance')
    if o.get('process_stdev') is not None:headers.append('%Process');keys.append('percent_process')
    tables.append(('Gage Evaluation',headers,[[a.get(k) for k in keys] for a in r['study_variation']]))
    tables.append(('Number of Distinct Categories',['NDC','Note'],[[r.get('ndc'),r.get('ndc_note','')]]))
    return tables


def text_report(result):
    def display(value):
        if value is None:return '*'
        if isinstance(value,float):return format(value,'.7g')
        return str(value)
    lines=[]
    for title,headers,rows in sections(result):
        data=[[display(v) for v in row] for row in rows]
        widths=[max(len(h),max((len(row[i]) for row in data),default=0)) for i,h in enumerate(headers)]
        lines.extend([title,'  '.join(h.ljust(w) for h,w in zip(headers,widths))])
        lines.extend('  '.join(value.ljust(w) for value,w in zip(row,widths)) for row in data)
        lines.append('')
    lines.append('Balanced crossed study; parts and operators are random effects. Negative estimated variance components are truncated to zero.')
    if result.get('options',result.get('settings',{})).get('process_stdev') is not None:
        lines.append('Reference process SD is used only as the %Process denominator; it does not replace the estimated variance components.')
    lines.extend(result.get('warnings',[]))
    return '\n'.join(lines)
