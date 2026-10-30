"""Readable mixture contour and optimizer reports without internal mesh dumps."""


def _value(value):
    if value is None:return '*'
    if isinstance(value,float):return format(value,'.7g')
    return str(value)


def text_report(result):
    r=result;lines=[r['title'],'Response: '+r['response_name'],'Fixed mixture total: '+_value(r['total']),'']
    if r.get('conditioning'):
        lines += ['Fixed external settings: '+r['conditioning']['summary'], 'Only the mixture composition varies; external settings remain fixed.','']
    if r['analysis']=='mixture_contour':
        lines+=['Mixture Contour Plot','Components: '+', '.join(r['selected_names']),
                'Held components: '+(', '.join(item['name']+' = '+_value(item['value']) for item in r['hold_values']) or 'None'),
                'Displayed component total: '+_value(r['display_total']),
                'Fitted response range on mesh: '+_value(r['value_range'][0])+' to '+_value(r['value_range'][1]),
                'Contour thresholds: '+(', '.join(_value(v) for v in r['levels']) or 'Constant fitted response'),
                'Mesh points: '+str(len(r['points']))+'; triangles: '+str(len(r['triangles'])),
                '','Contours are piecewise-linear interpolation of fitted mesh values, not an exact analytic level set.']
    else:
        lines+=['Response Optimization','Goal: '+r['goal']+(' '+_value(r['target']) if r['target'] is not None else ''),
                'Method: '+r['method'],'Search status: converged',
                'Global optimum certified for this fitted objective: '+('Yes' if r['global_optimum_proven'] else 'No'),
                'Converged starts: '+str(r['converged_starts']),'Selected setting: '+r['selected_origin'],'',
                'Component                       Amount           Lower           Upper']
        for name,amount,bound in zip(r['component_names'],r['components'],r['component_bounds']):
            lines.append(name.ljust(30)+_value(amount).rjust(15)+_value(bound['low']).rjust(16)+_value(bound['high']).rjust(16))
        p=r['prediction'];lines+=['','Fitted response: '+_value(p['fit']),'SE Fit: '+_value(p['standard_error']),
            _value(r['confidence']*100)+'% mean confidence interval: '+_value(p['ci_low'])+' to '+_value(p['ci_high']),
            _value(r['confidence']*100)+'% individual prediction interval: '+_value(p['prediction_low'])+' to '+_value(p['prediction_high'])]
        if r['target_error'] is not None:lines.append('Absolute target difference: '+_value(r['target_error']))
    lines+=['','Component bounds in original units:']
    lines += [name+': '+_value(bound['low'])+' to '+_value(bound['high']) for name,bound in zip(r['component_names'],r['component_bounds'])]
    lines+=['']+list(r.get('warnings',[]))
    return '\n'.join(lines)
