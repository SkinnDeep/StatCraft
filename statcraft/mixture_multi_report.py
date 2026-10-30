"""Readable multi-response mixture search and selected-setting reports."""


def _v(value):return '*' if value is None else format(value,'.7g') if isinstance(value,float) else str(value)


def text_report(r):
    optimized=r['analysis']=='mixture_multi_optimization'
    lines=[r['title'],r.get('method','User-selected feasible setting'),
           'Composite desirability: '+_v(r['composite_desirability']),
           'Log composite desirability: '+_v(r['log_composite_desirability']),
           'Status: '+str(r.get('status','Converged' if optimized else 'Selected setting')),
           'Global optimum certified: '+('Yes' if r.get('global_optimum_proven',False) else 'No'),
           'Fixed mixture total: '+_v(r['total']),'','Component                       Amount           Lower           Upper']
    for name,amount,bound in zip(r['component_names'],r['components'],r['component_bounds']):
        lines.append(name.ljust(30)+_v(amount).rjust(15)+_v(bound['low']).rjust(16)+_v(bound['high']).rjust(16))
    lines+=['','Response goals and predictions:']
    for row in r['responses']:
        p=row['prediction'];lines +=['',row['response_name']+' — '+row['goal'],
            'Lower / Target / Upper: '+_v(row['lower'])+' / '+_v(row['target'])+' / '+_v(row['upper']),
            'Weight: '+_v(row['weight'])+'; importance: '+_v(row['importance']),
            'Fit: '+_v(p['fit'])+'; desirability: '+_v(row['desirability'])+'; log desirability: '+_v(row['log_desirability'])+'; SE Fit: '+_v(p['standard_error']),
            _v(r['confidence']*100)+'% mean confidence interval: '+_v(p['ci_low'])+' to '+_v(p['ci_high']),
            _v(r['confidence']*100)+'% individual prediction interval: '+_v(p['prediction_low'])+' to '+_v(p['prediction_high'])]
    lines+=['','Interactive profiles change one component by transferring amount to/from the displayed balancing component. Other components stay fixed. Selected settings are not re-optimized.']
    lines+=list(r.get('warnings',[]))
    return '\n'.join(lines)
