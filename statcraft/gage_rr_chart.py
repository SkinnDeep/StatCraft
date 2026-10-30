"""Six-panel crossed Gage R&R plots, drawn from persisted study observations."""
import math
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QColor,QFont
from .graph_interaction import style_pen,style_color

COLORS=['#3e739b','#b46e39','#53856e','#9266a5','#b6485a','#628d9a']
# Standard three-sigma range / subgroup-mean chart constants, subgroup sizes 2–10.
CONSTANTS={2:(1.880,0.,3.267),3:(1.023,0.,2.574),4:(.729,0.,2.282),5:(.577,0.,2.114),6:(.483,0.,2.004),7:(.419,.076,1.924),8:(.373,.136,1.864),9:(.337,.184,1.816),10:(.308,.223,1.777)}
MAX_PARTS=100
MAX_OPERATORS=20
MAX_PLOT_OBSERVATIONS=20000


def _panel(title,labels,xlabel,ylabel,series,**extra):
    return dict(kind='gage_rr',title=title,categories=[str(a) for a in labels],xlabel=str(xlabel),ylabel=str(ylabel),series=series,**extra)


def _series(label,x,y,connect=False,rows=None):
    return dict(label=str(label),x=list(x),y=list(y),connect=connect,row_indices=list(rows or []))


def prepare(chart,result):
    r=result; parts=r['parts'];operators=r['operators'];data=r['plot_data'];raw=data['rows'];cells=data['cells']
    if not parts or not operators or not raw or not cells:raise ValueError('Gage R&R plots require complete study observations.')
    if len(parts)>MAX_PARTS or len(operators)>MAX_OPERATORS or len(raw)>MAX_PLOT_OBSERVATIONS:
        raise ValueError('Gage R&R graph display supports at most 100 parts, 20 operators, and 20,000 observations. The complete numerical report remains available.')
    if any(not math.isfinite(float(a['value'])) for a in raw):raise ValueError('Gage observations must be finite.')
    # Preserve the engine's Python factor equality (numeric 1 and 1.0 are one level).
    # Only labels are converted to strings; grouping remains typed throughout.
    part_index={a:i+1 for i,a in enumerate(parts)};operator_index={a:i+1 for i,a in enumerate(operators)}
    raw_by_operator={a:[] for a in operators};cell_lookup={}
    for a in raw:raw_by_operator[a['operator']].append(a)
    for a in cells:cell_lookup[a['part'],a['operator']]=a
    measurement=r.get('measurement','Measurement');part_name=r.get('part','Part');operator_name=r.get('operator','Operator')
    components=r['study_variation']; selected=[]
    for group in [('Total Gage R&R','total_grr','total_gage_rr','gage_rr'),('Repeatability','repeatability'),('Reproducibility','reproducibility'),('Part-To-Part','part_to_part')]:
        a=next((a for a in components if a.get('key') in group or a['source'].casefold().replace('-',' ').replace(' ','')==group[0].casefold().replace('-',' ').replace(' ','')),None)
        if a is not None:selected.append(a)
    if not selected:selected=components
    component_series=[]
    for key,label in [('percent_contribution','%Contribution'),('percent_study_variation','%Study Var'),('percent_tolerance','%Tolerance')]:
        values=[a.get(key) for a in selected]
        if any(v is not None for v in values):component_series.append(_series(label,range(1,len(values)+1),values))
    undefined_components=not component_series
    if undefined_components:component_series=[_series('Undefined',range(1,len(selected)+1),[None]*len(selected))]
    charts=[_panel('Components of Variation',[a['source'].replace(' ','\n') for a in selected],'','Percent',component_series,bars=True,undefined=undefined_components)]
    by_part=[];by_operator=[];interaction=[]
    for index,operator in enumerate(operators):
        observations=raw_by_operator[operator]
        by_part.append(_series(operator,[part_index[a['part']] for a in observations],[a['value'] for a in observations],rows=[a['row']+1 for a in observations]))
        points=[cell_lookup[part,operator] for part in parts]
        interaction.append(_series(operator,[part_index[a['part']] for a in points],[a['mean'] for a in points],True))
        by_operator.append(_series(operator,[index+1+((i%7)-3)*.028 for i in range(len(observations))],[a['value'] for a in observations],rows=[a['row']+1 for a in observations]))
    charts.append(_panel('Measurements by Part',parts,part_name,measurement,by_part,legend=str(operator_name)))
    ordered=[cell_lookup[part,operator] for operator in operators for part in parts]
    labels=[str(a['operator'])+'\n'+str(a['part']) for a in ordered];ranges=[a['range'] for a in ordered];means=[a['mean'] for a in ordered]
    average_range=math.fsum(v/len(ranges) for v in ranges)
    anchor=raw[0]['value'];grand_mean=anchor+math.fsum((a['value']-anchor)/len(raw) for a in raw)
    constants=CONSTANTS.get(r['repeats']);range_lines=[];mean_lines=[]
    if constants:
        a2,d3,d4=constants
        range_lines=[('UCL',d4*average_range),('Center',average_range),('LCL',d3*average_range)]
        mean_lines=[('UCL',grand_mean+a2*average_range),('Center',grand_mean),('LCL',grand_mean-a2*average_range)]
    def control_series(values):
        series=[]
        for operator in operators:
            start=(operator_index[operator]-1)*len(parts);indices=range(start,start+len(parts))
            series.append(_series(operator,[i+1 for i in indices],[values[i] for i in indices],True))
        return series
    operator_groups=[dict(label=str(operator),start=index*len(parts)+1,end=(index+1)*len(parts),parts=[str(part) for part in parts]) for index,operator in enumerate(operators)]
    charts.append(_panel('R Chart by Operator',labels,str(operator_name)+' / '+str(part_name),'Sample Range',control_series(ranges),limits=range_lines,zero=True,operator_groups=operator_groups))
    charts.append(_panel('Measurements by Operator',operators,operator_name,measurement,by_operator,legend=str(operator_name)))
    charts.append(_panel('Xbar Chart by Operator',labels,str(operator_name)+' / '+str(part_name),'Sample Mean',control_series(means),limits=mean_lines,operator_groups=operator_groups))
    charts.append(_panel('Part × Operator Interaction',parts,part_name,'Mean '+str(measurement),interaction,legend=str(operator_name)))
    # Validate plotting ranges during preparation so unsupported extremes display
    # the ordinary chart error, rather than raising from a Qt paint callback.
    for panel in charts:
        values=[v for series in panel['series'] for v in series['y'] if v is not None]+[v for _,v in panel.get('limits',[])]
        chart._bounds(values or [0.],panel.get('bars',False) or panel.get('zero',False))
    chart.panels=charts;chart.panel_columns=2
    chart.note='Balanced crossed ANOVA study · R/Xbar limits use average cell range and standard constants.' if constants else 'Balanced crossed ANOVA study · R/Xbar control limits unavailable for replicate counts outside 2–10.'


def draw_panel(chart,p,area,panel):
    series=panel['series'];n=len(panel['categories']);values=[v for a in series for v in a['y'] if v is not None]+[v for _,v in panel.get('limits',[])]
    groups=panel.get('operator_groups',[])
    # Control charts have a two-level axis: part ticks, then one operator label
    # per block. Never repeat a long operator name beneath every observation.
    custom_ticks=bool(groups) or n>20
    categories=['']*n if custom_ticks else panel['categories']
    plot,x,y=chart._axes(p,area,(.5,n+.5),chart._bounds(values or [0.],panel.get('bars',False) or panel.get('zero',False)),'' if groups else panel['xlabel'],panel['ylabel'],categories=categories)
    if custom_ticks:
        p.setFont(QFont('Segoe UI',8));metrics=p.fontMetrics()
        ticks=groups or [dict(label='',start=1,end=n,parts=panel['categories'])]
        for group in ticks:
            count=group['end']-group['start']+1;block_width=plot.width()*count/n
            label_width=max(24,max((metrics.horizontalAdvance(label) for label in group['parts']),default=24)+8)
            stride=max(1,math.ceil(count*label_width/max(1,block_width)))
            tick_width=max(24,plot.width()/n*stride)
            for j in range(0,count,stride):
                label=metrics.elidedText(group['parts'][j],Qt.TextElideMode.ElideRight,int(tick_width-3))
                chart._text(p,QRectF(x(group['start']+j)-tick_width/2,plot.bottom()+5,tick_width,18),label,'#697884')
            if groups:
                center=x((group['start']+group['end'])/2)
                label=metrics.elidedText(group['label'],Qt.TextElideMode.ElideRight,max(1,int(block_width-8)))
                chart._text(p,QRectF(center-block_width/2,plot.bottom()+24,block_width,18),label,'#263440')
        if groups:chart._text(p,QRectF(plot.left(),plot.bottom()+43,plot.width(),18),panel['xlabel'],'#697884')
    p.save();p.setClipRect(plot.adjusted(-1,-1,1,1))
    for i,a in enumerate(series):
        color=COLORS[i%len(COLORS)];target='s'+str(i);style=chart.graph_style(target,color=color,fill=color,edge=color,marker_size=5,line_width=1.2)
        if not style.get('visible',True):continue
        if panel.get('bars'):
            width=.72/max(1,len(series));p.setPen(style_pen(style));p.setBrush(style_color(style['fill'],style.get('opacity',1)))
            for position,value in zip(a['x'],a['y']):
                if value is None:continue
                center=position-.36+(i+.5)*width;rect=QRectF(QPointF(x(center-width/2),y(0)),QPointF(x(center+width/2),y(value))).normalized();p.drawRect(rect);chart.remember_rect(target,rect)
        else:
            if a['connect']:chart._path(p,a['x'],a['y'],x,y,color,style=style,target=target)
            for j,(position,value) in enumerate(zip(a['x'],a['y'])):
                if value is None:continue
                row=a['row_indices'][j] if j<len(a['row_indices']) else None
                chart._marker(p,QPointF(x(position),y(value)),color,i,style,target,row)
    for i,(label,value) in enumerate(panel.get('limits',[])):
        color='#51846b' if label=='Center' else '#bb4147'
        chart._path(p,[.5,n+.5],[value,value],x,y,color,dashed=True,style=chart.graph_style('ref'+str(i),color=color),target='ref'+str(i))
    for group in groups[:-1]:
        chart._path(p,[group['end']+.5]*2,[chart._bounds(values or [0.],panel.get('zero',False))[0],chart._bounds(values or [0.],panel.get('zero',False))[1]],x,y,'#c6cdd2',dashed=True)
    p.restore();p.setFont(QFont('Segoe UI',8))
    if panel.get('undefined'):
        chart._text(p,plot,'Percentages undefined: zero total variation.','#697884')
    if panel.get('bars') or panel.get('legend'):
        for i,a in enumerate(series):
            chart._text(p,QRectF(plot.right()+6,plot.top()+i*25,94,24),p.fontMetrics().elidedText(a['label'],Qt.TextElideMode.ElideRight,90),COLORS[i%len(COLORS)],Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
    for i,(label,value) in enumerate(panel.get('limits',[])):
        chart._text(p,QRectF(plot.right()+6,plot.top()+i*34,94,32),label+'\n'+format(value,'.4g'),'#51846b' if label=='Center' else '#bb4147',Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
