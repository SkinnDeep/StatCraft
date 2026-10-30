from .glm_report import sections as base_sections


def sections(r):
    tables=base_sections(r)
    for i,(title,headers,rows) in enumerate(tables):
        if title=='Method':tables[i]=(title,['Setting','Value'],[['Factors','Continuous, coded to low = −1 and high = +1'],['Sum of squares','Adjusted' if r['options']['ss_type']=='adjusted' else 'Sequential'],['Confidence level',str(100*r['confidence'])+'%'],['Missing data','Omit incomplete model rows']])
        if title=='Analysis of Variance':
            extra=[]
            for key,label in [('lack_of_fit','  Lack-of-Fit'),('pure_error','  Pure Error')]:
                a=r[key]
                if a['df']>0:extra.append([label,a['df'],a['ss'],a['ss'],a['ms'],a.get('f'),a.get('p_value')])
            rows[-1:-1]=extra
    if r['options']['factor_information']:
        tables.insert(1 if r['options']['method'] else 0,('Factor Coding',['Factor','Low (−1)','Center (0)','High (+1)'],[[a[k] for k in ('name','low','center','high')] for a in r.get('surface_coding_information',r['coding_information'])]))
    return tables


def text_report(r):
    # Share the plain-text table formatter without modifying global report behavior.
    lines=[]
    for title,headers,rows in sections(r):
        display=lambda v:'*' if v is None else format(v,'.7g') if isinstance(v,float) else str(v)
        data=[[display(v) for v in row] for row in rows];widths=[max(len(h),max((len(row[i]) for row in data),default=0)) for i,h in enumerate(headers)]
        lines += [title,'  '.join(v.ljust(w) for v,w in zip(headers,widths))]+['  '.join(v.ljust(w) for v,w in zip(row,widths)) for row in data]+['']
    return '\n'.join(lines+[r['assumptions']]+r.get('warnings',[]))


def design_sections(r):
    rows=[[key.replace('_',' ').title(),value] for key,value in r.items() if key not in ('analysis','factor_coding','design_table','convention')]
    tables=[('Design Summary',['Setting','Value'],rows),('Factor Settings',['Factor','Low (cube)','Center','High (cube)'],[[c[k] for k in ('name','low','center','high')] for c in r['factor_coding']])]
    if r.get('design_table'):
        keys=list(r['design_table'][0]);tables.append(('Design Table',keys,[[row[k] for k in keys] for row in r['design_table']]))
    return tables


def design_text(r):
    lines=[]
    for title,headers,rows in design_sections(r):
        lines += [title,'  '.join(headers)]+['  '.join(str(v) for v in row) for row in rows]+['']
    return '\n'.join(lines+[r['convention']])
