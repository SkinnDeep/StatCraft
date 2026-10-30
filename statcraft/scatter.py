"""Original bounded scatterplot series, linear fits and connection ordering."""
import math
from itertools import zip_longest
from .engine import normalize_numeric
from .value_order import ordered_values

MODES={'simple':'Simple','groups':'With Groups','regression':'With Regression',
       'regression_groups':'With Regression and Groups','connect':'With Connect Line',
       'connect_groups':'With Connect and Groups'}
ORDERS=('Increasing X','Increasing Y','Worksheet')


def linear_fit(points):
    if len(points)<2: raise ValueError('Each regression group needs at least two complete observations.')
    xs,ys=zip(*points); sx=max(map(abs,xs)) or 1.; sy=max(map(abs,ys)) or 1.
    x=[v/sx for v in xs]; y=[v/sy for v in ys]
    mx=math.fsum(x)/len(x); my=math.fsum(y)/len(y)
    dx=[v-mx for v in x]; dy=[v-my for v in y]
    denominator=math.fsum(v*v for v in dx)
    if denominator<=0: raise ValueError('Each regression group must have distinct X values.')
    coefficient=math.fsum(a*b for a,b in zip(dx,dy))/denominator
    slope=coefficient*sy/sx if coefficient else 0.
    intercept=my*sy-slope*(mx*sx)
    endpoints=[min(xs),max(xs)]
    fitted=[sy*(my+coefficient*(v/sx-mx)) for v in endpoints]
    if not all(math.isfinite(v) for v in [slope,intercept]+fitted): raise ValueError('The fitted line exceeds supported numeric precision.')
    return {'intercept':intercept,'slope':slope,'x':endpoints,'y':fitted}


def build(worksheet,x_index,y_index,mode='simple',group_index=None,order='Increasing X',title='',x_label='',y_label=''):
    if mode not in MODES or order not in ORDERS: raise ValueError('Unsupported scatterplot type or connection order.')
    if any(type(i) is not int or i<0 or i>=len(worksheet.columns) for i in (x_index,y_index)):
        raise ValueError('Select available X and Y columns.')
    xcol,ycol=[worksheet.columns[i] for i in (x_index,y_index)]
    if any(c.kind!='number' for c in (xcol,ycol)): raise ValueError('Scatterplot X and Y must be numeric.')
    grouped=mode in ('groups','regression_groups','connect_groups')
    if grouped:
        if type(group_index) is not int or not 0<=group_index<len(worksheet.columns): raise ValueError('Select a grouping variable.')
        groupcol=worksheet.columns[group_index]
        if groupcol.kind not in ('number','text'): raise ValueError('Grouping variables must be numeric or text.')
        groupvalues=groupcol.values
    else:
        if group_index is not None: raise ValueError('This scatterplot type does not use a grouping variable.')
        groupcol=None; groupvalues=[]
    for value in (title,x_label,y_label):
        if not isinstance(value,str) or len(value)>256: raise ValueError('Plot labels must be text of at most 256 characters.')
    rows=zip_longest(xcol.values,ycol.values,groupvalues) if grouped else ((a,b,'') for a,b in zip_longest(xcol.values,ycol.values))
    groups={}; missing=0
    for row,(a,b,g) in enumerate(rows,1):
        a,b=normalize_numeric(a),normalize_numeric(b)
        if grouped and groupcol.kind=='number': g=normalize_numeric(g)
        if a is None or b is None or grouped and (g is None or g==''):
            missing+=1; continue
        key=(type(g).__name__,g)
        if key not in groups:
            if len(groups)>=20: raise ValueError('The implemented grouped scatterplot supports at most 20 nonempty groups.')
            groups[key]={'label':str(g),'points':[],'rows':[]}
        groups[key]['points'].append([a,b]); groups[key]['rows'].append(row)
    if not groups: raise ValueError('Selected variables have no complete numeric pairs and group values.')
    series=[]; fits=[]; summaries=[]
    keys=list(groups)
    if grouped:
        levels=ordered_values(groupcol,[key[1] for key in keys])
        keys=sorted(keys,key=lambda key:levels.index(key[1]))
    for key in keys:
        group=groups[key]
        points=group['points']; indices=group['rows']
        connect=mode in ('connect','connect_groups')
        if connect and order!='Worksheet':
            pairs=sorted(zip(points,indices),key=lambda item:item[0][0 if order=='Increasing X' else 1])
            points,indices=map(list,zip(*pairs))
        fit=linear_fit(points) if mode in ('regression','regression_groups') else None
        name=group['label'] if grouped else 'All observations'
        series.append({'label':name,'x':[p[0] for p in points],'y':[p[1] for p in points],
                       'row_indices':indices,'connect':connect,'fit':fit})
        summaries.append({'group':name,'count':len(points)})
        if fit: fits.append({'group':name,'count':len(points),'intercept':fit['intercept'],'slope':fit['slope']})
    return {'graph':'scatter','scatter_mode':mode,'variables':[xcol.name,ycol.name],
            'xlabel':x_label or xcol.name,'ylabel':y_label or ycol.name,
            'plot_title':title or ycol.name+' vs '+xcol.name,
            'group_variable':groupcol.name if grouped else None,
            'count':sum(len(s['x']) for s in series),'missing':missing,'series':series,
            'group_statistics':summaries,'fits':fits,'connection_order':order if mode in ('connect','connect_groups') else None,
            'convention':'Complete worksheet rows only; incomplete X/Y/group values are omitted. Text groups follow column value order; numeric groups sort numerically. Linear fits are independent least-squares lines per group, without confidence bands. Connect lines join retained observations in the selected order.'}
