"""Independent individual-value and mean-interval calculations and source recipes."""
import copy
import math
from statistics import stdev
from .model import finite_number
from .boxplot_graphs import VARIANTS,validate_parameters as validate_roles,build_boxplots

PLOT_TYPES=('individual','interval')
DISPLAY_KEYS=('individual','interval','bar','mean_symbol','median_symbol','mean_connect','median_connect')


def validate_display(display=None,plot_type='individual'):
    defaults=dict.fromkeys(DISPLAY_KEYS,False);defaults.update(individual=plot_type=='individual',interval=plot_type=='interval',mean_symbol=plot_type=='interval')
    if display is None:return defaults
    if not isinstance(display,dict) or set(display)-set(defaults) or any(type(v) is not bool for v in display.values()):raise ValueError('Choose supported data-display on/off controls.')
    defaults.update(display)
    if not any(defaults.values()):raise ValueError('Select at least one data display.')
    return defaults


def validate_interval(options=None):
    defaults=dict(method='confidence',confidence=.95,multiple=1.0,side='two-sided',pooled=False,bonferroni=False)
    if options is not None:
        if not isinstance(options,dict) or set(options)-set(defaults):raise ValueError('Unsupported interval options.')
        defaults.update(options)
    if defaults['method'] not in ('confidence','standard_error') or defaults['side'] not in ('two-sided','upper','lower'):raise ValueError('Choose a supported interval type and side.')
    level=finite_number(defaults['confidence']);multiple=finite_number(defaults['multiple'])
    if not .001<=level<=.99999 or not 0<multiple<=100:raise ValueError('Confidence must be 0.1–99.999%; standard-error multiple must be positive and at most 100.')
    if type(defaults['pooled']) is not bool or type(defaults['bonferroni']) is not bool:raise ValueError('Pool error and Bonferroni must be on or off.')
    if defaults['side']!='two-sided' and level<=.5:raise ValueError('One-sided confidence bounds require a confidence level above 50%.')
    if defaults['method']=='standard_error' and (defaults['side']!='two-sided' or defaults['bonferroni']):raise ValueError('Standard-error intervals use two sides without Bonferroni.')
    return dict(defaults,confidence=level,multiple=multiple)


def validate_parameters(worksheet,response_indices,plot_type='individual',variant='one',group_indices=None,variable_position='outer',layout='combined',display=None,interval_options=None,jitter=.12,color_levels=None):
    if plot_type not in PLOT_TYPES:raise ValueError('Choose individual-value or interval plots.')
    roles=validate_roles(worksheet,response_indices,variant,group_indices,variable_position,layout)
    jitter=finite_number(jitter)
    if not 0<=jitter<=.4:raise ValueError('Category jitter must be between 0 and 0.4.')
    levels=list(range(len(roles['group_indices']))) if color_levels is None else color_levels
    if not isinstance(levels,list) or len(levels)>4 or any(type(i) is not int or not 0<=i<len(roles['group_indices']) for i in levels) or len(set(levels))!=len(levels):raise ValueError('Attribute variables must be selected grouping levels.')
    return dict(response_indices=roles['response_indices'],plot_type=plot_type,variant=variant,group_indices=roles['group_indices'],variable_position=variable_position,
        layout=roles['layout'],display=validate_display(display,plot_type),interval_options=validate_interval(interval_options),jitter=jitter,color_levels=list(levels))


def build_points(worksheet,**arguments):
    p=validate_parameters(worksheet,**arguments)
    base=build_boxplots(worksheet,**{k:p[k] for k in ('response_indices','variant','group_indices','variable_position','layout')})
    items=[item for panel in base['panels'] for item in panel['items']]
    if p['display']['individual'] and sum(item['n'] for item in items)>10000:raise ValueError('Individual symbols support at most 10000 retained observations. Turn them off for a larger interval plot.')
    colors={};by_response={}
    for item in items:
        key=tuple(item['group_values'][i] for i in p['color_levels']) if p['group_indices'] else (item['response_index'],)
        if key not in colors:colors[key]=len(colors)
        item['color_index']=colors[key];item['median']=item['box']['median'];del item['box']
        item['stdev']=finite_number(stdev(item['source'])) if item['n']>1 else None
        item.update(standard_error=None,df=None,lower=None,upper=None)
        by_response.setdefault(item['response_index'],[]).append(item)
    options=p['interval_options']
    if p['display']['interval']:
        from scipy.stats import t
        for group in by_response.values():
            df=sum(item['n']-1 for item in group)
            if options['pooled'] and df<1:raise ValueError('Pooled intervals require positive within-group degrees of freedom.')
            pooled=math.sqrt(math.fsum((item['n']-1)*item['stdev']**2 for item in group if item['stdev'] is not None)/df) if options['pooled'] else None
            for item in group:
                if not options['pooled'] and item['n']<2:raise ValueError('Unpooled intervals require at least two observations in every group.')
                degrees=df if options['pooled'] else item['n']-1
                se=finite_number((pooled if options['pooled'] else item['stdev'])/math.sqrt(item['n']))
                if options['method']=='standard_error':critical=options['multiple']
                else:
                    tail=(1-options['confidence'])/(len(group) if options['bonferroni'] else 1)/(2 if options['side']=='two-sided' else 1)
                    critical=finite_number(float(t.isf(tail,degrees)))
                half=finite_number(critical*se);low=finite_number(item['mean']-half);high=finite_number(item['mean']+half)
                item.update(standard_error=se,df=degrees,lower=None if options['side']=='upper' else low,upper=None if options['side']=='lower' else high)
    for panel in base['panels']:
        panel.update(kind='categorical_points',display=copy.deepcopy(p['display']),jitter=p['jitter'])
    title=('Individual Value Plot' if p['plot_type']=='individual' else 'Interval Plot')+' of '+', '.join(worksheet.columns[i].name for i in p['response_indices'])
    note='Individual observations at their original values.'
    if p['display']['interval']:
        note=(format(options['confidence']*100,'.5g')+'% t confidence intervals for means' if options['method']=='confidence' else format(options['multiple'],'.5g')+' standard-error intervals for means')
        note+='; '+('pooled within each response' if options['pooled'] else 'separate group standard deviations')
        if options['bonferroni']:note+='; Bonferroni within each response'
        if options['side']!='two-sided':note+='; '+options['side']+' bounds'
    result=dict(graph='categorical_points',title=title,parameters=p,panels=base['panels'],convention=note)
    validate_result(result);return result


def validate_result(result):
    if not isinstance(result,dict) or result.get('graph')!='categorical_points':raise ValueError('Invalid saved categorical graph.')
    panels=result.get('panels');total=0;count=0
    if not isinstance(panels,list) or not 1<=len(panels)<=16:raise ValueError('Categorical graphs require 1 to 16 panels.')
    for panel in panels:
        if not isinstance(panel,dict) or panel.get('kind')!='categorical_points' or any(not isinstance(panel.get(k),str) for k in ('title','xlabel','ylabel')):raise ValueError('Invalid categorical graph panel.')
        display=panel.get('display');validate_display(display)
        if not isinstance(display,dict) or set(display)!=set(DISPLAY_KEYS):raise ValueError('Missing categorical display settings.')
        if not 0<=finite_number(panel.get('jitter'))<=.4:raise ValueError('Invalid saved category jitter.')
        items=panel.get('items')
        if not isinstance(items,list) or not items:raise ValueError('Categorical graphs require data groups.')
        count+=len(items)
        if count>32:raise ValueError('Too many categorical groups.')
        for item in items:
            if not isinstance(item,dict) or any(not isinstance(item.get(k),str) for k in ('label','response_name','group_label')):raise ValueError('Invalid category labels.')
            values=item.get('source');rows=item.get('row_indices');n=item.get('n')
            if not isinstance(values,list) or not values or type(n) is not int or n!=len(values) or not isinstance(rows,list) or len(rows)!=n or any(type(row) is not int or row<1 for row in rows) or len(set(rows))!=n:raise ValueError('Invalid categorical source observations/rows.')
            for value in values:finite_number(value)
            total+=n
            if total>100000:raise ValueError('Too many categorical observations.')
            if type(item.get('color_index')) is not int or not 0<=item['color_index']<32:raise ValueError('Invalid category color identity.')
            finite_number(item.get('mean'));finite_number(item.get('median'))
            for key in ('stdev','standard_error'):
                if item.get(key) is not None and finite_number(item[key])<0:raise ValueError('Invalid categorical standard deviation/error.')
            if display['interval']:
                if item.get('standard_error') is None or type(item.get('df')) is not int or item['df']<1:raise ValueError('Invalid interval degrees of freedom/error.')
                low,high=item.get('lower'),item.get('upper')
                if low is None and high is None:raise ValueError('An interval requires at least one finite endpoint.')
                if low is not None and finite_number(low)>item['mean'] or high is not None and finite_number(high)<item['mean']:raise ValueError('Invalid interval endpoints.')
    if any(panel['display']['individual'] for panel in panels) and total>10000:raise ValueError('Too many individual symbols.')
    return result
