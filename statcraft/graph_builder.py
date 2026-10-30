"""Original typed graph-builder mappings compiled into existing graph engines."""
import copy
import math
from .model import finite_number

TYPES={'scatter':'Scatterplot','histogram':'Histogram','boxplot':'Boxplot','dotplot':'Dotplot',
    'individual_value':'Individual Value Plot','interval_plot':'Interval Plot','bar_chart':'Bar Chart',
    'time_series':'Time Series Plot','matrix_plot':'Matrix Plot'}
DEFAULTS=dict(title='',bins=10,fit=False,stack=False,variable_position='outer',layout='combined',confidence=.95,pooled=False,bonferroni=False)


def validate_options(options=None):
    if options is not None and (not isinstance(options,dict) or set(options)-set(DEFAULTS)):raise ValueError('Unsupported Graph Builder options.')
    p=dict(DEFAULTS,**(options or {}))
    if not isinstance(p['title'],str) or len(p['title'])>145:raise ValueError('Graph titles support up to 145 characters.')
    if type(p['bins']) is not int or not 2<=p['bins']<=200:raise ValueError('Choose 2 to 200 intervals.')
    if any(type(p[k]) is not bool for k in ('fit','stack','pooled','bonferroni')):raise ValueError('Builder switches must be on or off.')
    if p['variable_position'] not in ('outer','inner') or p['layout'] not in ('combined','panels'):raise ValueError('Choose a supported variable order and graph arrangement.')
    if not .5<finite_number(p['confidence'])<=.99999:raise ValueError('Confidence must be above 50% and at most 99.999%.')
    return copy.deepcopy(p)


def validate_mapping(graph_type,response_indices,x_index=None,group_indices=None,options=None):
    if graph_type not in TYPES:raise ValueError('Choose a supported Graph Builder graph type.')
    groups=[] if group_indices is None else group_indices
    for name,values in (('Graph variables',response_indices),('Grouping variables',groups)):
        if not isinstance(values,(list,tuple)) or any(type(i) is not int or i<0 for i in values) or len(set(values))!=len(values):raise ValueError(name+' must identify distinct worksheet columns.')
    maximum=1 if graph_type in ('scatter','bar_chart') else 8 if graph_type in ('matrix_plot','time_series') else 16
    minimum=2 if graph_type=='matrix_plot' else 1
    if not minimum<=len(response_indices)<=maximum:raise ValueError('Select '+str(minimum)+' to '+str(maximum)+' graph variables for '+TYPES[graph_type]+'.')
    if x_index is not None and (type(x_index) is not int or x_index<0):raise ValueError('Choose a valid X variable.')
    if graph_type=='scatter' and x_index is None:raise ValueError('Scatterplot requires an X variable.')
    if graph_type not in ('scatter','time_series') and x_index is not None:raise ValueError('This graph type does not use an X variable.')
    if x_index in response_indices or x_index in groups or set(response_indices)&set(groups):raise ValueError('Graph, X and grouping roles must use different columns.')
    group_max=0 if graph_type in ('bar_chart','matrix_plot') else 1 if graph_type in ('scatter','histogram','time_series') else 4 if len(response_indices)==1 else 3
    if len(groups)>group_max:raise ValueError('This graph accepts at most '+str(group_max)+' grouping variables.')
    if graph_type=='time_series' and x_index is not None and len(response_indices)>7:raise ValueError('Time series with an X variable supports at most 7 response columns.')
    p=validate_options(options)
    if graph_type not in ('scatter','histogram'):p['fit']=False
    if graph_type!='dotplot':p['stack']=False
    if graph_type not in ('boxplot','dotplot','individual_value','interval_plot') and not (graph_type=='histogram' and groups):p['layout']='combined'
    if graph_type!='interval_plot':p['pooled']=False;p['bonferroni']=False
    if graph_type=='dotplot' and p['stack'] and len(response_indices)>1 and not groups:p['layout']='combined'
    return dict(graph_type=graph_type,response_indices=list(response_indices),x_index=x_index,group_indices=list(groups),options=p)


def validate_parameters(worksheet,**arguments):
    p=validate_mapping(**arguments);indices=p['response_indices']+p['group_indices']+([] if p['x_index'] is None else [p['x_index']])
    if any(i>=len(worksheet.columns) for i in indices):raise ValueError('A builder source column is no longer available.')
    kinds=('number','text') if p['graph_type']=='bar_chart' else ('number',)
    if any(worksheet.columns[i].kind not in kinds for i in p['response_indices']):raise ValueError('Graph variables must be '+('numeric or text.' if p['graph_type']=='bar_chart' else 'numeric.'))
    if any(worksheet.columns[i].kind not in ('number','text') for i in p['group_indices']):raise ValueError('Grouping variables must be numeric or text.')
    if p['x_index'] is not None and worksheet.columns[p['x_index']].kind not in (('number','date') if p['graph_type']=='time_series' else ('number',)):raise ValueError('Choose a compatible X variable.')
    if sum(len(worksheet.columns[i].values) for i in p['response_indices'])>100000:raise ValueError('Graph Builder supports at most 100000 selected response cells.')
    return p


def compute_builder(worksheet,**arguments):
    from .app import Presenter
    p=validate_parameters(worksheet,**arguments);kind=p['graph_type'];responses=p['response_indices'];groups=p['group_indices'];options=p['options']
    isolated=Presenter();isolated.worksheet=copy.deepcopy(worksheet)
    variant=('one' if len(responses)==1 else 'multiple')+('_groups' if groups else '')
    if kind=='scatter':
        mode=('regression_groups' if groups else 'regression') if options['fit'] else ('groups' if groups else 'simple')
        e=isolated.scatter_plot(p['x_index'],responses[0],mode,groups[0] if groups else None)
    elif kind=='histogram':
        variant=('fit_groups' if groups else 'fit') if options['fit'] else ('groups' if groups else 'simple')
        e=isolated.histogram_graphs(responses,variant,groups[0] if groups else None,'panels' if options['layout']=='panels' else 'overlay',{'bins':options['bins'],'fit':'Normal' if options['fit'] else None})
    elif kind=='boxplot':e=isolated.boxplot_graphs(responses,variant,groups,options['variable_position'],options['layout'])
    elif kind=='dotplot':
        if options['stack'] and groups:variant='one_stack_groups' if len(responses)==1 else 'multiple_stack_groups'
        elif options['stack'] and len(responses)>1:variant='multiple_stack'
        e=isolated.dotplot_graphs(responses,variant,groups,options['variable_position'],options['layout'],stack=options['stack'],intervals=options['bins'])
    elif kind in ('individual_value','interval_plot'):
        e=isolated.categorical_points(responses,'individual' if kind=='individual_value' else 'interval',variant,groups,options['variable_position'],options['layout'],
            interval_options={'confidence':options['confidence'],'pooled':options['pooled'],'bonferroni':options['bonferroni']})
    else:
        indices=([p['x_index']]+responses) if p['x_index'] is not None else responses
        e=isolated.expanded_graph(kind,indices,groups[0] if groups else None)
    result=copy.deepcopy(e['result']);result['builder_graph_type']=kind
    if options['title']:
        result['title']=options['title'];result['plot_title']=options['title']
    return p,options['title'] or e['title'],result
