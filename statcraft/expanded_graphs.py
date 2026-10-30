"""Bounded original graph calculations. Native-product parity is unverified.

Snapshots contain only finite JSON values and neutral drawing instructions.
Missing observations are omitted with original row alignment, never imputed.
Surface plots require an observed rectangular grid, with no interpolation.
"""
from collections import Counter
import json
import math
import statistics
from scipy import stats
from .model import finite_number
from .value_order import ordered_values

LABELS = {
    'binned_scatter':'Binned Scatterplot', 'matrix_plot':'Matrix Plot',
    'correlogram':'Correlogram', 'bubble':'Bubble Plot', 'marginal':'Marginal Plot',
    'dotplot':'Dotplot', 'stem_leaf':'Stem-and-Leaf', 'probability_plot':'Probability Plot',
    'ecdf':'Empirical CDF', 'distribution_plot':'Probability Distribution Plot',
    'interval_plot':'Interval Plot', 'individual_value':'Individual Value Plot',
    'line_plot':'Line Plot', 'time_series':'Time Series Plot',
    'parallel_coordinates':'Parallel Coordinates Plot', 'bar_chart':'Bar Chart',
    'heatmap':'Heatmap', 'pie_chart':'Pie Chart', 'area_graph':'Area Graph',
    'contour':'Contour Plot', 'scatter3d':'3D Scatterplot', 'surface3d':'3D Surface Plot'}
MAX_OBSERVATIONS = 5000
MAX_CELLS = 10000
_MULTI = {'matrix_plot','correlogram','parallel_coordinates','heatmap','dotplot','stem_leaf',
          'probability_plot','ecdf','interval_plot','individual_value','time_series'}
_THREE = {'bubble','contour','scatter3d','surface3d'}
_TWO = {'binned_scatter','marginal'}
GROUP_METHODS = {'binned_scatter','matrix_plot','bubble','marginal','dotplot','probability_plot',
                 'ecdf','interval_plot','individual_value','line_plot','time_series','area_graph'}
METHODS = {name:{'label':label,
    'minimum':0 if name=='distribution_plot' else 3 if name in _THREE else 2 if name in _TWO or name in ('matrix_plot','correlogram','parallel_coordinates') else 1,
    'maximum':0 if name=='distribution_plot' else 3 if name in _THREE else 2 if name in _TWO or name in ('line_plot','area_graph') else 8 if name in _MULTI else 1,
    'roles':['X variable','Y variable','Bubble size' if name=='bubble' else 'Z variable'] if name in _THREE else ['X variable','Y variable'] if name in _TWO else ['Variables'],
    'group_allowed':name in GROUP_METHODS,
    'kinds':['number','text'] if name in ('bar_chart','pie_chart') else ['number','date'] if name=='time_series' else ['number']}
    for name,label in LABELS.items()}


def _xy(title, x_label, y_label, series):
    return {'kind':'xy','title':title,'x_label':x_label,'y_label':y_label,'series':series}


def _series(name, points, connect=False, **extra):
    return dict(name=name,points=points,connect=connect,**extra)


def _category(value,kind):
    return value if kind=='text' else format(finite_number(value),'.17g')


def _hist(values, bins):
    low,high=min(values),max(values)
    if low==high:
        return [str(low)],[len(values)]
    step=(high-low)/bins
    if not math.isfinite(step) or step<=0:raise ValueError('Data range exceeds plotting precision.')
    counts=[0]*bins
    for value in values:counts[min(bins-1,int((value-low)/step))]+=1
    return [format(low+(i+.5)*step,'.6g') for i in range(bins)],counts


def _model(distribution, parameters):
    if not isinstance(parameters,dict):raise ValueError('Distribution parameters must be an object.')
    expected={'Normal':{'mean','stdev'},'Uniform':{'lower','upper'},'Exponential':{'rate'}}
    if distribution not in expected:raise ValueError('Choose Normal, Uniform or Exponential.')
    if set(parameters)-expected[distribution]:raise ValueError('Unknown distribution parameter.')
    p={k:finite_number(v) for k,v in parameters.items()}
    if distribution=='Normal':
        mean,sd=p.get('mean',0.),p.get('stdev',1.)
        if sd<=0:raise ValueError('Standard deviation must be positive.')
        return stats.norm(loc=mean,scale=sd)
    if distribution=='Uniform':
        low,high=p.get('lower',0.),p.get('upper',1.)
        if high<=low or not math.isfinite(high-low):raise ValueError('Upper bound must exceed lower bound within finite range.')
        return stats.uniform(loc=low,scale=high-low)
    rate=p.get('rate',1.)
    if rate<=0 or not math.isfinite(1/rate):raise ValueError('Rate must be positive within finite range.')
    return stats.expon(scale=1/rate)


def compute(method, worksheet, indices, group_index=None, bins=10, confidence=.95,
            distribution='Normal', parameters=None):
    """Calculate a bounded immutable graph snapshot from explicit worksheet roles.

    Multivariate graphs use complete cases. Univariate series use their own
    nonmissing observations; group-missing rows are omitted when grouping.
    Line and area X/Y roles are first/second columns; with one column X is the
    original one-based row number. Surface roles are X,Y,Z. Bubble roles X,Y,size.
    """
    if method not in LABELS:raise ValueError('Choose a supported graph type.')
    if not isinstance(indices,(list,tuple)) or len(indices)>8 or any(type(i) is not int or i<0 or i>=len(worksheet.columns) for i in indices):
        raise ValueError('Select at most 8 valid worksheet columns.')
    if len(set(indices))!=len(indices):raise ValueError('Select each graph variable once.')
    if group_index is not None and (type(group_index) is not int or not 0<=group_index<len(worksheet.columns)):
        raise ValueError('Select a valid grouping column.')
    if type(bins) is not int or not 1<=bins<=100:raise ValueError('Bins must be an integer from 1 to 100.')
    confidence=finite_number(confidence)
    if not 0<confidence<1:raise ValueError('Confidence must lie strictly between 0 and 1.')
    categorical=method in ('bar_chart','pie_chart')
    cols=[worksheet.columns[i] for i in indices]
    timed=method=='time_series' and cols and cols[0].kind=='date'
    numeric=cols[1:] if timed else cols
    if any(c.kind!='number' for c in numeric) and not categorical:raise ValueError('Select numeric graph variables; a time series may start with one date axis.')
    if timed and len(cols)<2:raise ValueError('A date time axis needs at least one numeric response.')
    if categorical and any(c.kind not in ('number','text') for c in cols):raise ValueError('Categories require numeric or text columns.')
    group=worksheet.columns[group_index] if group_index is not None else None
    if group is not None and method not in GROUP_METHODS:raise ValueError('Grouping is unavailable for this graph type.')
    if group is not None and group.kind not in ('number','text'):raise ValueError('Groups require numeric or text values.')
    selected=cols+([group] if group is not None and group_index not in indices else [])
    if sum(len(c.values) for c in selected)>MAX_CELLS:raise ValueError('Graph selection exceeds 10000 cells.')
    for c in selected:c.validate()
    minimum={'binned_scatter':2,'matrix_plot':2,'correlogram':2,'bubble':3,'marginal':2,
             'parallel_coordinates':2,'contour':3,'scatter3d':3,'surface3d':3}.get(method,1)
    exact={'binned_scatter':2,'bubble':3,'marginal':2,'bar_chart':1,'pie_chart':1,
           'contour':3,'scatter3d':3,'surface3d':3}
    if method=='distribution_plot':
        if cols:raise ValueError('Distribution plots use parameters, not worksheet columns.')
    elif len(cols)<minimum or (method in exact and len(cols)!=exact[method]):
        raise ValueError('Incorrect number of variables for this graph.')
    if method=='line_plot' and len(cols)>2:raise ValueError('Line plots accept one Y or an X/Y pair.')
    if method=='area_graph' and len(cols)>2:raise ValueError('Area graphs accept one Y or an X/Y pair.')
    rows=[]
    extent=max((len(c.values) for c in selected),default=0)
    for row in range(extent):
        label=group.values[row] if group is not None and row<len(group.values) else None
        if group is not None and label is None:continue
        values=[c.values[row] if row<len(c.values) else None for c in cols]
        rows.append((row,values,_category(label,group.kind) if group is not None else ''))
    complete=[entry for entry in rows if all(v is not None for v in entry[1])]
    if len(complete)>MAX_OBSERVATIONS:raise ValueError('Graph exceeds 5000 plotted observations.')
    panels=[]
    def univariate(index):
        values=[(row,v[index],label) for row,v,label in rows if v[index] is not None]
        if not values:raise ValueError('Graph requires nonmissing observations.')
        if len(values)>MAX_OBSERVATIONS:raise ValueError('Graph exceeds 5000 plotted observations.')
        return values
    def groups(entries):
        result={}
        for entry in entries:result.setdefault(entry[-1],[]).append(entry)
        if len(result)>20:raise ValueError('These graph variants support at most 20 groups.')
        return {key:result[key] for key in ordered_values(group,result)} if group is not None else result
    def pairs(ix,iy,connect=False):
        return [_series(label,[[v[ix],v[iy]] for _,v,_ in entries],connect,row_indices=[r+1 for r,_,_ in entries]) for label,entries in groups(complete).items()]
    if method=='distribution_plot':
        model=_model(distribution,{} if parameters is None else parameters)
        lower=float(model.ppf(.001));upper=float(model.ppf(.999))
        points=[[lower+(upper-lower)*i/200,0.] for i in range(201)]
        for point in points:point[1]=float(model.pdf(point[0]))
        panels=[_xy(distribution+' Distribution','Value','Density',[_series(distribution,points,True)])]
    elif method in ('bar_chart','pie_chart'):
        counts=Counter(_category(value,cols[0].kind) for _,value,_ in univariate(0))
        if len(counts)>20:raise ValueError('Count bar and pie charts currently support at most 20 categories.')
        categories=ordered_values(cols[0],counts)
        panels=[{'kind':'bars' if method=='bar_chart' else 'pie','title':cols[0].name,
                 'categories':categories,'values':[counts[key] for key in categories]}]
    elif method in ('matrix_plot','correlogram'):
        if len(complete)<2:raise ValueError('Matrix graphs require at least 2 complete observations.')
        if method=='matrix_plot':
            panels=[_xy(cols[x].name+' / '+cols[y].name,cols[x].name,cols[y].name,pairs(x,y))
                    for y in range(len(cols)) for x in range(len(cols)) if x!=y]
        else:
            vectors=[[v[i] for _,v,_ in complete] for i in range(len(cols))]
            if any(min(v)==max(v) for v in vectors):raise ValueError('Correlation requires nonconstant variables.')
            values=[[float(stats.pearsonr(x,y).statistic) for x in vectors] for y in vectors]
            panels=[{'kind':'heatmap','title':'Pearson Correlation','x_labels':[c.name for c in cols],
                     'y_labels':[c.name for c in cols],'values':values}]
    elif method in ('binned_scatter','bubble','marginal','scatter3d','contour','surface3d','parallel_coordinates','heatmap'):
        if not complete:raise ValueError('Graph requires complete nonmissing observations.')
        if method=='binned_scatter':
            xmin,xmax=min(v[0] for _,v,_ in complete),max(v[0] for _,v,_ in complete)
            ymin,ymax=min(v[1] for _,v,_ in complete),max(v[1] for _,v,_ in complete)
            dx=(xmax-xmin)/bins if xmax!=xmin else 1.;dy=(ymax-ymin)/bins if ymax!=ymin else 1.
            if not all(math.isfinite(v) and v>0 for v in (dx,dy)):raise ValueError('Binning range exceeds plotting precision.')
            series=[]
            for label,entries in groups(complete).items():
                counts=Counter((min(bins-1,int((v[0]-xmin)/dx)),min(bins-1,int((v[1]-ymin)/dy))) for _,v,_ in entries)
                series.append(_series(label,[[xmin+(x+.5)*dx if xmin!=xmax else xmin,
                    ymin+(y+.5)*dy if ymin!=ymax else ymin,count] for (x,y),count in sorted(counts.items())]))
            panels=[_xy('Binned Counts',cols[0].name,cols[1].name,series)]
        elif method=='bubble':
            if any(v[2]<0 for _,v,_ in complete):raise ValueError('Bubble sizes must be nonnegative.')
            panels=[_xy('Bubble Plot',cols[0].name,cols[1].name,
                [_series(label,[list(v) for _,v,_ in entries],row_indices=[r+1 for r,_,_ in entries]) for label,entries in groups(complete).items()])]
        elif method=='marginal':
            panels=[_xy('Scatterplot',cols[0].name,cols[1].name,pairs(0,1))]
            for i,c in enumerate(cols):
                categories,counts=_hist([v[i] for _,v,_ in complete],bins)
                panels.append({'kind':'bars','title':c.name+' Marginal Distribution','categories':categories,'values':counts})
        elif method=='parallel_coordinates':
            panels=[{'kind':'parallel','title':'Complete Observations','axes':[c.name for c in cols],
                     'rows':[list(v) for _,v,_ in complete]}]
        elif method=='heatmap':
            panels=[{'kind':'heatmap','title':'Complete Observations','x_labels':[c.name for c in cols],
                     'y_labels':[str(r+1) for r,_,_ in complete],'values':[list(v) for _,v,_ in complete]}]
        elif method=='scatter3d':
            panels=[{'kind':'xyz','title':'3D Scatterplot','points':[list(v) for _,v,_ in complete],
                     'axes':[c.name for c in cols]}]
        else:
            grid={}
            for _,v,_ in complete:
                if tuple(v[:2]) in grid:raise ValueError('Surface coordinates must be unique X/Y pairs.')
                grid[tuple(v[:2])]=v[2]
            xs=sorted({x for x,y in grid});ys=sorted({y for x,y in grid})
            if len(xs)<2 or len(ys)<2 or len(xs)*len(ys)!=len(grid):
                raise ValueError('Contour and surface graphs require a complete rectangular grid with at least 2 X and 2 Y values.')
            panels=[{'kind':'surface','title':LABELS[method],'x':xs,'y':ys,
                     'z':[[grid[x,y] for x in xs] for y in ys], 'contour':method=='contour',
                     'axes':[c.name for c in cols]}]
    elif method in ('line_plot','area_graph','time_series'):
        if not complete:raise ValueError('Graph requires nonmissing observations.')
        if method=='time_series':
            series=[_series(c.name+(' — '+label if label else ''),[[v[0] if timed else r+1,v[i]] for r,v,_ in entries],True,row_indices=[r+1 for r,_,_ in entries])
                    for i,c in enumerate(cols) if not timed or i>0 for label,entries in groups(complete).items()]
            x_label=cols[0].name if timed else 'Row'
        else:
            series=[_series(label,[[r+1,v[0]] if len(cols)==1 else list(v) for r,v,_ in entries],True,
                            fill=method=='area_graph',row_indices=[r+1 for r,_,_ in entries]) for label,entries in groups(complete).items()]
            x_label='Row' if len(cols)==1 else cols[0].name
        panels=[_xy(LABELS[method],x_label,cols[-1].name,series)]
        if timed:panels[0]['x_date']=True
    else:
        for i,c in enumerate(cols):
            entries=univariate(i)
            if method=='interval_plot':
                items=[]
                for label,items_raw in groups(entries).items():
                    values=[v for _,v,_ in items_raw]
                    if len(values)<2:raise ValueError('Mean intervals require at least 2 observations per group.')
                    mean=statistics.mean(values);sd=statistics.stdev(values)
                    half=float(stats.t.ppf((1+confidence)/2,len(values)-1))*sd/math.sqrt(len(values))
                    items.append({'name':label or c.name,'mean':mean,'lower':mean-half,'upper':mean+half,'count':len(values)})
                panels.append({'kind':'intervals','title':c.name,'confidence':confidence,'items':items})
            elif method=='stem_leaf':
                values=[v for _,v,_ in entries]
                magnitude=max(abs(v) for v in values)
                unit=10.**(math.floor(math.log10(magnitude))-1) if magnitude else 1.
                if not math.isfinite(unit) or unit<=0:raise ValueError('Stem-and-leaf magnitude exceeds supported precision.')
                stems={}
                for value in sorted(values):
                    units=int(math.floor(abs(value)/unit+.5));stem=('-' if value<0 else '')+str(units//10)
                    stems.setdefault(stem,[]).append(str(units%10))
                panels.append({'kind':'stem_leaf','title':c.name,'leaf_unit':unit,
                    'lines':['Leaf unit = '+format(unit,'.6g')]+[stem+' | '+' '.join(leaves) for stem,leaves in stems.items()]})
            else:
                series=[]
                for position,(label,items_raw) in enumerate(groups(entries).items()):
                    values=sorted(v for _,v,_ in items_raw)
                    if method=='probability_plot':
                        model=_model(distribution,{} if parameters is None else parameters)
                        points=[[float(model.ppf((j+.625)/(len(values)+.25))),value] for j,value in enumerate(values)]
                        connect=False
                    elif method=='ecdf':
                        counts=Counter(values);points=[];total=0
                        for value,count in sorted(counts.items()):
                            points.extend([[value,total/len(values)],[value,(total+count)/len(values)]]);total+=count
                        connect=True
                    elif method=='dotplot':
                        counts=Counter(values);points=[[value,level] for value,count in sorted(counts.items()) for level in range(1,count+1)];connect=False
                    elif method=='individual_value':points=[[position+1,value] for value in values];connect=False
                    else:raise ValueError('Unsupported graph calculation.')
                    series.append(_series(label or c.name,points,connect))
                axes={'probability_plot':('Theoretical Quantile',c.name),'ecdf':(c.name,'Cumulative Probability'),
                      'dotplot':(c.name,'Stack Count'),'individual_value':('Group',c.name)}
                panels.append(_xy(c.name,*axes[method],series))
    result={'graph':'expanded','method':method,'label':LABELS[method],'title':LABELS[method],
            'panels':panels,'convention':'Original graph algorithms; native-product equivalence is unverified.',
            'missing_policy':'Omit missing values with original row alignment; multivariate graphs use complete cases.'}
    try:json.dumps(result,allow_nan=False)
    except (ValueError,OverflowError) as exc:raise ValueError('Graph calculation exceeds finite plotting precision.') from exc
    return result
