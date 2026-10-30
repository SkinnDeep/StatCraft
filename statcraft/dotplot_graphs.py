"""Independent binned dotplots with explicit series, lanes and source rows."""
import math
from .model import finite_number
from .value_order import ordered_values
from .boxplot_graphs import validate_parameters as validate_roles

VARIANTS=('one','one_groups','one_stack_groups','multiple','multiple_stack','multiple_groups','multiple_stack_groups')


def validate_parameters(worksheet,response_indices,variant='one',group_indices=None,variable_position='outer',layout='combined',stack=True,intervals=None,color_levels=None):
    if variant not in VARIANTS:raise ValueError('Choose a supported dotplot type.')
    if type(stack) is not bool:raise ValueError('Stack dots must be on or off.')
    if intervals is not None and (type(intervals) is not int or not 1<=intervals<=200):raise ValueError('Dot intervals must be automatic or an integer from 1 to 200.')
    base=('multiple' if variant.startswith('multiple') else 'one')+('_groups' if variant.endswith('groups') else '')
    roles=validate_roles(worksheet,response_indices,base,group_indices,variable_position,layout)
    levels=list(range(max(0,len(roles['group_indices'])-3),len(roles['group_indices']))) if color_levels is None else color_levels
    if not isinstance(levels,list) or len(levels)>3 or any(type(i) is not int or not 0<=i<len(roles['group_indices']) for i in levels) or len(set(levels))!=len(levels):raise ValueError('Choose at most three grouping variables for attribute assignment.')
    if variant=='multiple_stack' and layout!='combined':raise ValueError('Stack Y’s requires variables on the same graph.')
    return {**{k:v for k,v in roles.items() if k not in ('display','variant')},'variant':variant,'stack':stack,'intervals':intervals,'color_levels':list(levels)}


def build_dotplots(worksheet,**arguments):
    p=validate_parameters(worksheet,**arguments);groups=[worksheet.columns[i] for i in p['group_indices']]
    data=[];keys=[];total=0
    for response in p['response_indices']:
        observed={}
        for row,value in enumerate(worksheet.columns[response].values):
            if value is None:continue
            key=tuple(g.values[row] if row<len(g.values) else None for g in groups)
            if any(v is None for v in key):continue
            values,rows=observed.setdefault(key,([],[]));values.append(finite_number(value));rows.append(row+1);total+=1
            if total>10000:raise ValueError('Dotplots support at most 10000 retained observations.')
        if not observed:raise ValueError('Every graph variable needs observations with complete grouping values.')
        data.append((response,observed));keys.extend(key for key in observed if key not in keys)
    ranks=[{v:i for i,v in enumerate(ordered_values(g,[key[j] for key in keys]))} for j,g in enumerate(groups)]
    keys.sort(key=lambda key:tuple(ranks[j][v] for j,v in enumerate(key)))
    color_keys=list(dict.fromkeys(tuple(key[i] for i in p['color_levels']) for key in keys))
    colors={key:color_keys.index(tuple(key[i] for i in p['color_levels'])) for key in keys}
    batches=[data] if p['layout']=='combined' else [[pair] for pair in data];panels=[];series_count=0
    for batch in batches:
        values=[v for _,observed in batch for source,_ in observed.values() for v in source]
        lo,hi=min(values),max(values);count=p['intervals'] or min(50,max(1,math.ceil(math.sqrt(len(values)))))
        width=(hi-lo)/count if hi!=lo else 0
        if not math.isfinite(hi-lo) or hi!=lo and (not math.isfinite(width) or width<=0):raise ValueError('Dotplot range exceeds plotting precision.')
        series=[];lanes=[];lane_keys=[]
        for response,observed in batch:
            for key in keys:
                if key not in observed:continue
                name=worksheet.columns[response].name or 'C'+str(response+1)
                collapsed=p['stack'] and '_stack' in p['variant']
                lane_group=key[:-1] if collapsed and groups else key
                lane_response=None if collapsed and p['variant']=='multiple_stack' else response
                lane_key=(lane_response,lane_group)
                if lane_key not in lane_keys:
                    lane_keys.append(lane_key)
                    levels=[str(v) for v in lane_group]
                    if lane_response is not None and len(batch)>1:levels.insert(0 if p['variable_position']=='outer' else len(levels),name)
                    lanes.append(' / '.join(levels) or (name if len(batch)==1 else 'Graph variables'))
                source,rows=observed[key]
                series.append(dict(label=name+(' / '+' / '.join(map(str,key)) if key else ''),response_index=response,group_values=list(key),
                    lane=lane_keys.index(lane_key),color_index=colors[key] if groups else p['response_indices'].index(response),source=source,row_indices=rows,points=[]))
        if p['variable_position']=='inner' and len(batch)>1 and groups:
            series.sort(key=lambda s:(keys.index(tuple(s['group_values'])),p['response_indices'].index(s['response_index'])))
            order=[]
            for s in series:
                if s['lane'] not in order:order.append(s['lane'])
            lanes=[lanes[i] for i in order]
            for s in series:s['lane']=order.index(s['lane'])
        bins={};heights=[0]*len(lanes)
        for s in series:
            for value,row in zip(s['source'],s['row_indices']):
                bucket=0 if width==0 else min(count-1,max(0,int((value-lo)/width)))
                x=lo if width==0 else lo+(bucket+.5)*width
                slot=(s['lane'],bucket);level=bins.get(slot,0)+1;bins[slot]=level;heights[s['lane']]=max(heights[s['lane']],level)
                s['points'].append(dict(x=x,level=level,row=row,value=value))
        series_count+=len(series)
        if series_count>32:raise ValueError('Dotplots support at most 32 observed response/group combinations.')
        panels.append(dict(kind='dotplot_groups',title=(worksheet.columns[batch[0][0]].name if len(batches)>1 else ''),
            xlabel=worksheet.columns[batch[0][0]].name if len(batch)==1 else 'Data',ylabel='',lanes=lanes,heights=heights,series=series,
            value_range=[lo,hi],intervals=count,interval_width=width))
    result=dict(graph='dotplot_graphs',title='Dotplot of '+', '.join(worksheet.columns[i].name for i in p['response_indices']),parameters=p,panels=panels,
        convention='Each dot represents one observation; equal-width intervals share boundaries within each panel.')
    validate_result(result);return result


def validate_result(result):
    if not isinstance(result,dict) or result.get('graph')!='dotplot_graphs':raise ValueError('Invalid saved dotplot.')
    panels=result.get('panels');total=0;series_count=0
    if not isinstance(panels,list) or not 1<=len(panels)<=16:raise ValueError('Dotplots require 1 to 16 panels.')
    for panel in panels:
        if not isinstance(panel,dict) or panel.get('kind')!='dotplot_groups' or any(not isinstance(panel.get(k),str) for k in ('title','xlabel','ylabel')):raise ValueError('Invalid dotplot panel.')
        lanes=panel.get('lanes');heights=panel.get('heights');series=panel.get('series')
        if not isinstance(lanes,list) or not 1<=len(lanes)<=32 or any(not isinstance(v,str) for v in lanes):raise ValueError('Invalid dotplot categories.')
        if not isinstance(heights,list) or len(heights)!=len(lanes) or any(type(v) is not int or v<1 for v in heights):raise ValueError('Invalid dotplot stack heights.')
        if not isinstance(series,list) or not series:raise ValueError('Dotplots need series.')
        series_count+=len(series)
        if series_count>32:raise ValueError('Too many dotplot series.')
        count=panel.get('intervals');width=finite_number(panel.get('interval_width'));bounds=panel.get('value_range')
        if type(count) is not int or not 1<=count<=200 or width<0 or not isinstance(bounds,list) or len(bounds)!=2:raise ValueError('Invalid dot intervals.')
        lo,hi=map(finite_number,bounds)
        if lo>hi or not math.isfinite(hi-lo):raise ValueError('Invalid dotplot range.')
        occupied=set();actual_heights=[0]*len(lanes)
        for s in series:
            if not isinstance(s,dict) or not isinstance(s.get('label'),str) or type(s.get('lane')) is not int or not 0<=s['lane']<len(lanes) or type(s.get('color_index')) is not int or not 0<=s['color_index']<32:raise ValueError('Invalid dotplot series.')
            source=s.get('source');rows=s.get('row_indices');points=s.get('points')
            if not isinstance(source,list) or not source or not isinstance(rows,list) or len(rows)!=len(source) or not isinstance(points,list) or len(points)!=len(source):raise ValueError('Invalid dotplot source observations.')
            if any(type(r) is not int or r<1 for r in rows) or len(set(rows))!=len(rows):raise ValueError('Invalid dotplot source rows.')
            total+=len(source)
            if total>10000:raise ValueError('Too many dotplot observations.')
            for value,row,point in zip(source,rows,points):
                value=finite_number(value)
                if not isinstance(point,dict) or type(point.get('row')) is not int or point.get('row')!=row or finite_number(point.get('value'))!=value or type(point.get('level')) is not int or not 1<=point['level']<=heights[s['lane']]:raise ValueError('Invalid saved dot.')
                x=finite_number(point.get('x'))
                if not lo<=value<=hi or not lo<=x<=hi:raise ValueError('Dot outside saved value range.')
                slot=(s['lane'],x,point['level'])
                if slot in occupied:raise ValueError('Overlapping saved dot identities.')
                occupied.add(slot);actual_heights[s['lane']]=max(actual_heights[s['lane']],point['level'])
        if actual_heights!=heights:raise ValueError('Dotplot stack heights do not match observations.')
    return result
