"""Validated original row identity for brushing immutable graph snapshots."""


def brushable_rows(entry):
    result=entry.get('result',{}) if isinstance(entry,dict) else {}
    rows=[]
    def links(series,key,count):
        if not isinstance(series,dict):raise ValueError('Invalid row-linked graph series.')
        source=series.get(key,[])
        if not isinstance(source,(list,tuple)):raise ValueError('Graph source rows must be a list.')
        if source and len(source)!=count:raise ValueError('Graph source rows do not match the plotted observations.')
        rows.extend(source)
    if result.get('analysis')=='attribute_capability':
        links(result, 'rows', len(result.get('rates', [])))
    if result.get('analysis')=='gage_rr':
        for observation in result.get('plot_data',{}).get('rows',[]):
            row=observation.get('row')
            if type(row) is not int or row<0:raise ValueError('Invalid Gage R&R source row.')
            rows.append(row+1)
    if result.get('analysis')=='dynamic_taguchi_analysis' and result.get('options',{}).get('show_signal_plots',False):
        rows.extend(row['row']+1 for row in result.get('rows',[])[:24])
    if result.get('analysis') in ('mixture_model','mixture_process_model'):
        rows.extend(row+1 for row in result.get('row_indices',result.get('used_rows',[])))
    if result.get('analysis')=='binary_logistic':
        source=result.get('row_indices',[])
        if not isinstance(source,list) or any(type(row) is not int or row<0 for row in source):raise ValueError('Invalid logistic graph source rows.')
        rows.extend(row+1 for row in source)
    if result.get('graph') in ('histogram_graphs','histogram'):
        for panel in result.get('panels',[]):
            for series in panel.get('series',[]):links(series,'row_indices',len(series.get('source',[])))
    if result.get('graph')=='categorical_points':
        for panel in result.get('panels',[]):
            if panel.get('display',{}).get('individual'):
                for item in panel.get('items',[]):links(item,'row_indices',len(item.get('source',[])))
    if result.get('graph')=='dotplot_graphs':
        for panel in result.get('panels',[]):
            for series in panel.get('series',[]):links(series,'row_indices',len(series.get('points',[])))
    if result.get('graph')=='scatter':
        if 'series' in result:
            for series in result['series']:
                links(series,'row_indices',len(series.get('x',[])))
        else:
            links(result,'plot_rows',len(result.get('graph_data',[])))
    elif result.get('graph')=='expanded':
        for panel in result.get('panels',[]):
            if panel.get('kind')=='xy':
                for series in panel.get('series',[]):
                    links(series,'row_indices',len(series.get('points',[])))
    if any(type(row) is not int or row<1 for row in rows):raise ValueError('Graph source rows must be positive whole numbers.')
    return sorted(set(rows))


def validate_brushed_rows(entry,worksheet,rows):
    if not isinstance(rows,(list,tuple,set)) or any(type(row) is not int for row in rows):
        raise ValueError('Choose plotted source rows.')
    allowed=set(brushable_rows(entry));selected=sorted(set(rows))
    if not allowed:raise ValueError('This graph has no retained row links. Rerun a scatter or row-aligned XY graph to enable brushing.')
    if any(row not in allowed or row>worksheet.row_count for row in selected):raise ValueError('A brushed point no longer identifies a valid worksheet row. Rerun the graph.')
    return selected
