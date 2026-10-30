"""Original validation and detached appearance for panel/layout snapshots."""
import copy
import re
from .graph_styles import validate_styles
from .graph_presentation import validate_presentation
from .histogram_options import validate_histogram_settings,build_histogram_panel


def validate_appearance(appearance):
    if appearance is None:return {}
    if not isinstance(appearance,dict) or set(appearance)-{'graph_styles','graph_presentation','histogram_settings','series_labels'}:
        raise ValueError('Invalid source graph appearance.')
    result={}
    for key,validator in (('graph_styles',validate_styles),('graph_presentation',validate_presentation),('histogram_settings',validate_histogram_settings)):
        if key in appearance:result[key]=validator(appearance[key])
    if 'series_labels' in appearance:
        labels=appearance['series_labels']
        if not isinstance(labels,dict) or any(not isinstance(key,str) or not re.fullmatch(r'p\d+:s\d+',key) or not isinstance(value,str) for key,value in labels.items()):raise ValueError('Invalid source series labels.')
        result['series_labels']=dict(labels)
    return result


def appearance_from_entry(entry):
    appearance={key:entry[key] for key in ('graph_styles','graph_presentation','histogram_settings') if key in entry}
    result=entry.get('result',{});labels={}
    if result.get('graph')=='scatter' and 'series' in result:
        labels={'p0:s'+str(index):str(series.get('label','')) for index,series in enumerate(result['series'])}
    elif result.get('graph')=='expanded':
        labels={'p'+str(panel_index)+':s'+str(index):str(series.get('name','')) for panel_index,panel in enumerate(result.get('panels',[])) if panel.get('kind')=='xy' for index,series in enumerate(panel['series'])}
    if labels:appearance['series_labels']=labels
    return validate_appearance(appearance)


def apply_panel_appearance(result,appearance):
    appearance=validate_appearance(appearance)
    for child in result['graphs']:
        for key,value in appearance.items():
            if key=='series_labels':continue
            if key=='histogram_settings':build_histogram_panel(child['result'].get('histogram_source'),value)
            child[key]=copy.deepcopy(value)
            if key=='graph_presentation':child[key].update(title=child['title'][:145],title_enabled=True)
        if 'graph_styles' in child and appearance.get('series_labels'):
            labels=appearance_from_entry(child).get('series_labels',{})
            styles=copy.deepcopy(child['graph_styles'])
            for target in list(styles):
                if re.fullmatch(r'p\d+:(s|fit)\d+',target):styles.pop(target)
            for target,label in labels.items():
                panel,number=target.split(':s');source=next((key for key,value in appearance['series_labels'].items() if key.startswith(panel+':') and value==label),None)
                if source:
                    for old,new in ((source,target),(source.replace(':s',':fit'),panel+':fit'+number)):
                        if old in child['graph_styles']:styles[new]=copy.deepcopy(child['graph_styles'][old])
            child['graph_styles']=styles
    return result


def validate_composition(result):
    if not isinstance(result,dict):raise ValueError('Invalid composed graph.')
    graphs=result.get('graphs')
    if not isinstance(graphs,list) or not 1<=len(graphs)<=16:raise ValueError('Composed graphs require 1 to 16 source graphs.')
    for child in graphs:
        if not isinstance(child,dict) or not isinstance(child.get('result'),dict):raise ValueError('Invalid source graph snapshot.')
        if child['result'].get('graph') in ('panel_graph','graph_layout','panelled'):raise ValueError('Composed graphs cannot contain another composition.')
        from .graph_layouts import layout_eligible
        if not layout_eligible(child):raise ValueError('Unsupported source graph in composition.')
        if child['result'].get('graph')=='categorical_points':
            from .categorical_points import validate_result
            validate_result(child['result'])
        if child['result'].get('graph')=='dotplot_graphs':
            from .dotplot_graphs import validate_result
            validate_result(child['result'])
        if child['result'].get('graph')=='boxplot_graphs':
            from .boxplot_graphs import validate_result
            validate_result(child['result'])
        if child['result'].get('graph')=='histogram_graphs':
            from .histogram_graphs import validate_result
            validate_result(child['result'])
        validate_appearance({key:child[key] for key in ('graph_styles','graph_presentation','histogram_settings') if key in child})
        if 'histogram_settings' in child:build_histogram_panel(child['result'].get('histogram_source'),child['histogram_settings'])
    if result.get('graph')=='graph_layout':
        from .graph_layouts import build_layout
        build_layout(graphs,result.get('rows'),result.get('columns'),result.get('title',''))
    elif result.get('graph')=='panel_graph':
        if type(result.get('columns')) is not int or not 1<=result['columns']<=4:raise ValueError('Invalid panel column count.')
        if type(result.get('shared_x')) is not bool or type(result.get('shared_y')) is not bool:raise ValueError('Shared panel scales must be on or off.')
        facets=result.get('facets')
        if not isinstance(facets,list) or len(facets)!=len(graphs):raise ValueError('Panel group labels and source rows must match the graphs.')
        for facet in facets:
            if not isinstance(facet,dict) or not isinstance(facet.get('label'),str) or not isinstance(facet.get('rows'),list) or any(type(row) is not int or row<1 for row in facet['rows']):raise ValueError('Invalid panel source rows.')
    else:raise ValueError('Choose a supported graph composition.')
    return result
