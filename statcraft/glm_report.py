"""Human-readable model reports shared by desktop, text, Office and print paths."""
def sections(r):
    o=r['options'];tables=[]
    if o['method']:
        tables.append(('Method',['Setting','Value'],[['Factors','Fixed'],['Sum of squares','Adjusted (Type III)' if o['ss_type']=='adjusted' else 'Sequential (Type I)'],['Factor coding','(-1, 0, +1)' if o['coding']=='effect' else '(1, 0)'],['Covariates',{'none':'Do not standardize','center':'Subtract the mean','scale':'Divide by standard deviation','standardize':'Subtract mean and divide by standard deviation'}[o['standardize']]],['Confidence level',str(100*o['confidence'])+'%'],['Missing data','Omit incomplete model rows']]))
    if o['factor_information'] and r['factor_information']:
        tables.append(('Factor Information',['Factor','Type','Levels','Values','Reference'],[[a[k] for k in ('factor','type','levels','values','reference')] for a in r['factor_information']]))
    if o['anova']:
        rows=[[a[k] for k in ('source','df','seq_ss','adj_ss','ms','f','p_value')] for a in r['anova_terms']]
        rows.extend([['Error',r['df_error'],r['ss_error'],r['ss_error'],r['ms_error'],None,None],['Total',r['df_total'],r['ss_total'],r['ss_total'],None,None,None]])
        tables.append(('Analysis of Variance',['Source','DF','Seq SS','Adj SS','Adj MS' if o['ss_type']=='adjusted' else 'Seq MS','F-Value','P-Value'],rows))
    if o['model_summary']:
        tables.append(('Model Summary',['S','R-sq','R-sq(adj)','N','N*'],[[r['residual_stdev'],str(round(100*r['r_squared'],4))+'%',str(round(100*r['adjusted_r_squared'],4))+'%',r['count'],r['missing']]]))
    if o['coefficients']:
        tables.append(('Coefficients',['Term','Coef','SE Coef','T-Value','P-Value','Lower CI','Upper CI'],[[a[k] for k in ('name','estimate','standard_error','t','p_value','ci_low','ci_high')] for a in r['coefficients']]))
    if o['diagnostics']!='none':
        rows=[a for a in r['diagnostics'] if o['diagnostics']=='all' or a['flag']]
        if rows:tables.append(('Fits and Diagnostics'+(' for Unusual Observations' if o['diagnostics']=='unusual' else ''),['Obs','Response','Fit','Resid','Std Resid','Leverage',"Cook's D",''],[[a[k] for k in ('row','response','fit','residual','standardized_residual','leverage','cooks_distance','flag')] for a in rows]))
    return tables


def text_report(r):
    def display(value):return '*' if value is None else format(value,'.7g') if isinstance(value,float) else str(value)
    lines=[]
    for title,headers,rows in sections(r):
        strings=[[display(v) for v in row] for row in rows]
        widths=[min(75,max(len(headers[i]),max((len(row[i]) for row in strings),default=0))) for i in range(len(headers))]
        lines.extend([title,'  '.join(value.ljust(width) for value,width in zip(headers,widths))])
        lines.extend('  '.join(value.ljust(width) for value,width in zip(row,widths)) for row in strings)
        lines.append('')
    lines.extend([r['assumptions'],'R: |standardized residual| > 2. X: leverage > 3p/n; p includes the intercept.'])
    lines.extend(r.get('warnings',[]));return '\n'.join(lines)
