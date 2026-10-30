"""Original vertical categorical boxplots; all point offsets are deterministic."""
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QFont
from .graph_hover import summary_info,point_info
from .graph_interaction import PALETTE,style_color,style_pen,draw_marker


def draw_boxplot_groups(chart,painter,area,panel):
    items=panel['items'];display=panel['display']
    bounds=[value for item in items for value in item['source']]
    plot,x,y=chart._axes(painter,area,(.25,len(items)+.75),chart._bounds(bounds),panel['xlabel'],panel['ylabel'],categories=[item['label'] for item in items])
    painter.save();painter.setClipRect(plot.adjusted(-1,-1,1,1))
    for index,item in enumerate(items):
        position=index+1;center=x(position);width=min(60,(x(1.4)-x(1))*.9)
        name='s'+str(index);color=PALETTE[item['color_index']%len(PALETTE)]
        style=chart.graph_style(name,color=color,edge=color,fill=color,opacity=.65,line_width=1.5,visible=True,marker='circle',marker_size=5)
        if not style['visible']:continue
        box=item['box'];painter.setPen(style_pen(style));painter.setBrush(style_color(style['fill'],style['opacity']))
        if display['whiskers']:
            painter.drawLine(QPointF(center,y(box['low'])),QPointF(center,y(box['high'])))
            for value in (box['low'],box['high']):painter.drawLine(QPointF(center-width*.3,y(value)),QPointF(center+width*.3,y(value)))
        if display['iqr_box']:
            painter.drawRect(QRectF(QPointF(center-width/2,y(box['q3'])),QPointF(center+width/2,y(box['q1']))).normalized())
            painter.drawLine(QPointF(center-width/2,y(box['median'])),QPointF(center+width/2,y(box['median'])))
        chart.remember_rect(name,QRectF(center-width/2-5,y(box['high'])-5,width+10,max(10,y(box['low'])-y(box['high'])+10)))
        chart.remember_hover(QRectF(center-width/2-5,y(box['high'])-5,width+10,max(10,y(box['low'])-y(box['high'])+10)),summary_info('boxplot',[('Group',item['label']),('N',len(item['source']))]+[(key,box[key]) for key in ('low','q1','median','q3','high')]),plot)
        if display['outliers']:
            for value in box['outliers']:
                point=QPointF(center,y(value));draw_marker(painter,point,dict(style,fill='#ffffff',opacity=1));chart.remember_marker(name,point,style.get('marker_size',5))
        if display['individual']:
            for row,value in zip(item['row_indices'],item['source']):
                offset=(((row*37)%101)/100-.5)*width*.7
                point=QPointF(center+offset,y(value));draw_marker(painter,point,dict(style,opacity=.7));chart.remember_marker(name,point,style.get('marker_size',5))
                chart.remember_point_hover(point,point_info(item['label'],value,panel['xlabel'] or 'Group',panel['ylabel'] or 'Value',row=row),style.get('marker_size',5),plot)
        if display['mean_symbol']:
            point=QPointF(center,y(item['mean']));draw_marker(painter,point,dict(style,marker='diamond',marker_size=9,opacity=1));chart.remember_marker(name,point,9)
        if display['median_symbol']:
            point=QPointF(center,y(box['median']));draw_marker(painter,point,dict(style,marker='cross',marker_size=9,opacity=1));chart.remember_marker(name,point,9)
    for name,key,title in (('median_connect','median','Median'),('mean_connect','mean','Mean')):
        if display[name]:
            values=[item['box']['median'] if key=='median' else item['mean'] for item in items]
            target='ref0' if key=='median' else 'ref1'
            chart._path(painter,list(range(1,len(items)+1)),values,x,y,'#555555',1.4,style=chart.graph_style(target,color='#555555'),target=target)
    painter.restore()
