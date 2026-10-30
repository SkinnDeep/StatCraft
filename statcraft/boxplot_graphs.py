"""Original categorical boxplot calculations with explicit observed-group ordering."""
import copy
import math
from statistics import mean
from .model import finite_number
from .value_order import ordered_values

VARIANTS=('one','one_groups','multiple','multiple_groups')
DISPLAY=dict(iqr_box=True,whiskers=True,outliers=True,individual=False,
             median_symbol=False,mean_symbol=False,median_connect=False,mean_connect=False)


def validate_display(display=None):
    if display is None:return dict(DISPLAY)
    if not isinstance(display,dict) or set(display)-set(DISPLAY) or any(type(v) is not bool for v in display.values()):
        raise ValueError('Boxplot display settings must use supported on/off controls.')
    return dict(DISPLAY,**display)


def validate_parameters(worksheet,response_indices,variant='one',group_indices=None,
                        variable_position='outer',layout='combined',display=None):
    if variant not in VARIANTS:raise ValueError('Choose a supported boxplot type.')
    groups=[] if group_indices is None else group_indices
    if (not isinstance(response_indices,(list,tuple)) or not 1<=len(response_indices)<=16 or
        any(type(i) is not int or not 0<=i<len(worksheet.columns) or worksheet.columns[i].kind!='number' for i in response_indices) or len(set(response_indices))!=len(response_indices)):
        raise ValueError('Select 1 to 16 distinct numeric graph variables.')
    if variant.startswith('one') and len(response_indices)!=1:raise ValueError('One Y requires exactly one graph variable. Choose Multiple Y for several.')
    if not isinstance(groups,(list,tuple)) or len(set(groups))!=len(groups) or any(type(i) is not int or not 0<=i<len(worksheet.columns) or worksheet.columns[i].kind not in ('number','text') for i in groups):
        raise ValueError('Select distinct numeric or text grouping columns.')
    maximum=4 if variant=='one_groups' else 3 if variant=='multiple_groups' else 0
    if maximum and not 1<=len(groups)<=maximum or not maximum and groups:raise ValueError('Choose '+str(maximum)+' or fewer grouping columns for this type, with at least one for grouped plots.')
    if set(groups)&set(response_indices):raise ValueError('Graph and grouping variables must be different columns.')
    if variable_position not in ('outer','inner') or layout not in ('combined','panels'):raise ValueError('Choose a supported scale order and graph arrangement.')
    return dict(response_indices=list(response_indices),variant=variant,group_indices=list(groups),variable_position=variable_position,
                layout=layout if variant.startswith('multiple') else 'combined',display=validate_display(display))


def build_boxplots(worksheet,**arguments):
    from .app import boxplot_data
    p=validate_parameters(worksheet,**arguments);groups=[worksheet.columns[i] for i in p['group_indices']]
    keys=[];data=[];retained=0
    for index in p['response_indices']:
        column=worksheet.columns[index];observed={}
        for row,value in enumerate(column.values):
            if value is None:continue
            key=tuple(group.values[row] if row<len(group.values) else None for group in groups)
            if any(v is None for v in key):continue
            values,rows=observed.setdefault(key,([],[]));values.append(finite_number(value));rows.append(row+1)
            retained+=1
            if retained>100000:raise ValueError('Boxplots support at most 100000 retained observations.')
        if not observed:raise ValueError('Every graph variable needs nonmissing observations with complete groups.')
        data.append((index,observed));keys.extend(key for key in observed if key not in keys)
    ranks=[{v:i for i,v in enumerate(ordered_values(group,[key[position] for key in keys]))} for position,group in enumerate(groups)]
    order=sorted(keys,key=lambda key:tuple(ranks[i][value] for i,value in enumerate(key)))
    colors={key:i for i,key in enumerate(order)};items=[]
    for response_order,(index,observed) in enumerate(data):
        for key in order:
            if key not in observed:continue
            values,rows=observed[key];box=boxplot_data(values);average=finite_number(mean(values))
            levels=[str(value) for value in key];name=worksheet.columns[index].name or 'C'+str(index+1)
            label_levels=levels[:]
            if len(data)>1 and p['layout']=='combined':
                label_levels.insert(0 if p['variable_position']=='outer' else len(label_levels),name)
            label='\n'.join(label_levels) if label_levels else name
            items.append(dict(label=label,response_index=index,response_name=name,group_values=list(key),
                group_label=' / '.join(levels),box=box,mean=average,source=values,row_indices=rows,n=len(values),
                color_index=colors[key] if groups else response_order))
            if len(items)>32:raise ValueError('Boxplots support at most 32 observed response/group combinations.')
    if len(data)>1 and p['variable_position']=='inner' and p['layout']=='combined':
        items.sort(key=lambda item:(colors[tuple(item['group_values'])],p['response_indices'].index(item['response_index'])))
    panels=[]
    batches=([item for item in items if item['response_index']==index] for index,_ in data) if p['layout']=='panels' else [items]
    for batch in batches:
        name=batch[0]['response_name'] if p['layout']=='panels' or len(data)==1 else 'Value'
        levels=[group.name for group in groups]
        if len(data)>1 and p['layout']=='combined':levels.insert(0 if p['variable_position']=='outer' else len(levels),'Variable')
        panels.append(dict(kind='boxplot_groups',title=name if p['layout']=='panels' else '',xlabel=' / '.join(levels) or 'Variable',
            ylabel=name,items=batch,display=copy.deepcopy(p['display'])))
    result=dict(graph='boxplot_graphs',title='Boxplot of '+', '.join(worksheet.columns[i].name for i in p['response_indices']),parameters=p,
        panels=panels,convention='Clamped (n+1)p quartiles; whiskers end at observations within 1.5 IQR. Native numerical equivalence is unverified.')
    validate_result(result);return result


def validate_result(result):
    if not isinstance(result,dict) or result.get('graph')!='boxplot_graphs':raise ValueError('Invalid saved boxplot.')
    panels=result.get('panels');count=0;retained=0
    if not isinstance(panels,list) or not 1<=len(panels)<=16:raise ValueError('Boxplots require 1 to 16 panels.')
    for panel in panels:
        if not isinstance(panel,dict) or panel.get('kind')!='boxplot_groups' or any(not isinstance(panel.get(k),str) for k in ('title','xlabel','ylabel')):raise ValueError('Invalid saved boxplot panel.')
        if not isinstance(panel.get('display'),dict):raise ValueError('Missing boxplot display settings.')
        validate_display(panel['display']);items=panel.get('items')
        if not isinstance(items,list) or not items:raise ValueError('Boxplot panels need categories.')
        count+=len(items)
        if count>32:raise ValueError('Too many boxplot categories.')
        for item in items:
            if not isinstance(item,dict) or any(not isinstance(item.get(k),str) for k in ('label','response_name','group_label')):raise ValueError('Invalid boxplot category labels.')
            values=item.get('source');rows=item.get('row_indices')
            if not isinstance(values,list) or not values or type(item.get('n')) is not int or item['n']!=len(values):raise ValueError('Invalid boxplot observations.')
            for value in values:finite_number(value)
            if not isinstance(rows,list) or len(rows)!=len(values) or any(type(row) is not int or row<1 for row in rows) or len(set(rows))!=len(rows):raise ValueError('Invalid boxplot source rows.')
            retained+=len(values)
            if retained>100000:raise ValueError('Too many boxplot observations.')
            if type(item.get('color_index')) is not int or not 0<=item['color_index']<32:raise ValueError('Invalid boxplot color identity.')
            finite_number(item.get('mean'));box=item.get('box')
            if not isinstance(box,dict):raise ValueError('Invalid boxplot summary.')
            numbers=[finite_number(box.get(k)) for k in ('low','q1','median','q3','high')]
            if any(a>b for a,b in zip(numbers,numbers[1:])):raise ValueError('Boxplot summary must be ordered.')
            if not isinstance(box.get('outliers'),list):raise ValueError('Invalid boxplot outliers.')
            for value in box['outliers']:finite_number(value)
    return result
