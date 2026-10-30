"""Original bounded histogram calculations for recovered graph-option concepts.

Equal-width binning and sample-statistic normal fits are StatCraft policies;
the native application's numerical bin rules have not been established.
"""
import bisect
import math
import statistics

from .model import finite_number


def _bounds(values):
    low,high=min(values),max(values)
    if low==high:
        delta=max(abs(low)*0.05,0.5)
        lower,upper=low-delta,high+delta
        if not math.isfinite(lower): lower=low
        if not math.isfinite(upper): upper=high
        low,high=lower,upper
    span=high-low
    if not math.isfinite(span) or span<=0:
        raise ValueError('Histogram values span an unsupported floating-point range.')
    return low,high


def _series(label,values,bins,bounds,fit):
    low,high=bounds; span=high-low
    edges=[low+span*(i/bins) for i in range(bins+1)]
    edges[-1]=high
    if any(a>=b for a,b in zip(edges,edges[1:])):
        raise ValueError('The requested bins are too narrow for these numeric values.')
    counts=[0]*bins
    for value in values:
        index=min(bins-1,max(0,bisect.bisect_right(edges,value)-1))
        counts[index]+=1
    mean=float(statistics.mean(values))
    stdev=float(statistics.stdev(values)) if len(values)>1 else None
    if not math.isfinite(mean) or stdev is not None and not math.isfinite(stdev):
        raise ValueError('Histogram summary exceeds the supported numeric range.')
    curve_x=[]; curve_y=[]
    if fit:
        if len(values)<2 or not stdev:
            raise ValueError('A normal fit requires at least two distinct observations in every displayed series.')
        height=(len(values)*((span/bins)/stdev))/math.sqrt(2*math.pi)
        if not math.isfinite(height): raise ValueError('The normal-fit curve exceeds the supported numeric range.')
        curve_x=[low+span*(i/200) for i in range(201)]
        for x in curve_x:
            z=(x-mean)/stdev
            curve_y.append(height*math.exp(-0.5*z*z))
    return dict(label=label,edges=edges,counts=counts,curve_x=curve_x,curve_y=curve_y,
                mean=mean,stdev=stdev,count=len(values))


def compute(worksheet,indices,group_index=None,bins=10,display='Separate',bars=True,
            area=False,fit_normal=False,transpose=False,same_x=False,same_y=False):
    """Compute grouped numeric/date histograms, with explicit bounded options."""
    if not isinstance(indices,(list,tuple)) or not 1<=len(indices)<=8:
        raise ValueError('Select between one and eight histogram variables.')
    if any(type(i) is not int or i<0 or i>=len(worksheet.columns) for i in indices) or len(set(indices))!=len(indices):
        raise ValueError('Choose distinct valid histogram variables.')
    if type(bins) is not int or not 1<=bins<=200: raise ValueError('Choose between 1 and 200 bins.')
    if display not in ('Separate','Overlay'): raise ValueError('Choose Separate or Overlay histogram display.')
    if any(type(v) is not bool for v in (bars,area,fit_normal,transpose,same_x,same_y)):
        raise ValueError('Histogram options must be enabled or disabled.')
    if not bars and not area and not fit_normal:
        raise ValueError('Enable bars, area, or a normal fit.')
    selected=[worksheet.columns[i] for i in indices]
    if any(c.kind not in ('number','date') for c in selected):
        raise ValueError('Histograms require numeric or date variables.')
    group=None
    if group_index is not None:
        if type(group_index) is not int or not 0<=group_index<len(worksheet.columns) or group_index in indices:
            raise ValueError('Choose a separate valid grouping variable.')
        group=worksheet.columns[group_index]
        if group.kind not in ('number','text'): raise ValueError('Grouping requires a numeric or text variable.')
    if sum(len(c.values) for c in selected)+(len(group.values) if group else 0)>10000:
        raise ValueError('Histogram input is limited to 10000 source cells.')
    for column in selected+([group] if group else []): column.validate()
    grouped=[]; group_keys=[]; total=0; omitted=0
    for column in selected:
        entries={}
        for row,value in enumerate(column.values):
            if value is None: continue
            key=None
            if group:
                key=group.values[row] if row<len(group.values) else None
                if key is None:
                    omitted+=1; continue
                if key not in group_keys:
                    group_keys.append(key)
                    if len(group_keys)>20: raise ValueError('Histograms support at most 20 groups.')
            total+=1
            if total>5000: raise ValueError('Histograms support at most 5000 plotted observations.')
            entries.setdefault(key,[]).append(finite_number(value))
        if not entries: raise ValueError('Every histogram variable needs at least one observation with a nonmissing group.')
        for key,values in entries.items():
            label=column.name
            if group: label+=' — '+group.name+' = '+('""' if key=='' else str(key))
            grouped.append((label,column.name,values))
    shared=_bounds([v for _,_,values in grouped for v in values]) if display=='Overlay' or same_x else None
    series=[_series(label,values,bins,shared or _bounds(values),fit_normal) for label,_,values in grouped]
    panels=[]
    sets=[list(range(len(series)))] if display=='Overlay' else [[i] for i in range(len(series))]
    for positions in sets:
        items=[series[i] for i in positions]
        y_max=max(max(item['counts']+item['curve_y']) for item in items)
        panels.append(dict(kind='histogram',title='Histogram' if display=='Overlay' else items[0]['label'],
                           xlabel=', '.join(c.name for c in selected) if display=='Overlay' else grouped[positions[0]][1],
                           ylabel='Frequency',series=items,bars=bars,area=area,transpose=transpose,
                           x_bounds=[items[0]['edges'][0],items[0]['edges'][-1]],y_max=y_max))
    if same_y:
        y_max=max(panel['y_max'] for panel in panels)
        for panel in panels: panel['y_max']=y_max
    return dict(graph='histogram_configurable',title='Histogram of '+', '.join(c.name for c in selected),
                panels=panels,bins=bins,display=display,bars=bars,area=area,fit_normal=fit_normal,
                transpose=transpose,same_x=same_x,same_y=same_y,omitted_missing_group=omitted,
                count=total)
