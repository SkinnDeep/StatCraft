"""Readable joint mixture/process search settings and conditional uncertainty."""
def text_report(r):
    f=lambda v:'*' if v is None else format(v,'.8g') if isinstance(v,(int,float)) and not isinstance(v,bool) else str(v)
    lines=['Joint Mixture and Process Response Optimization','Response: '+r['response_name'],'Goal: '+r['goal']+(' = '+f(r['target']) if r['target'] is not None else ''),'Method: '+r['method'],'', 'Variable                         Lower          Setting        Upper']
    for names,values,bounds in ((r['component_names'],r['components'],r['component_bounds']),(r['process_names'],r['processes'],r['process_bounds'])):
        for name,value,pair in zip(names,values,bounds):lines.append(name.ljust(33)+f(pair['low']).ljust(15)+f(value).ljust(15)+f(pair['high']))
    lines+=['Mixture total: '+f(r['total']),'']
    for name,value in zip(r['covariate_names'],r['covariate_values']):lines.append('Held covariate '+name+': '+f(value))
    if r['block_name']:lines.append('Held block '+r['block_name']+': '+f(r['block_value']))
    p=r['prediction'];lines+=['','Predicted response: '+f(p['fit']),'SE Fit: '+f(p['standard_error']),f(100*r['confidence'])+'% confidence interval: '+f(p['ci_low'])+' to '+f(p['ci_high']),f(100*r['confidence'])+'% prediction interval: '+f(p['prediction_low'])+' to '+f(p['prediction_high']),'Converged starts: '+str(r['converged_starts']),'Selected candidate: '+r['selected_origin'],'']
    if r['target_error'] is not None:lines.append('Absolute target error: '+f(r['target_error']))
    return '\n'.join(lines+r['warnings'])
