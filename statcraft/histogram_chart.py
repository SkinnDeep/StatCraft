"""Original painter for shared-bin histograms and per-group fitted curves."""
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QColor,QFont
from .graph_hover import histogram_info
from .graph_interaction import PALETTE,style_color,style_pen


def draw_histogram_groups(chart,painter,area,panel):
    series=panel['series'];xs=list(panel['edges']);ys=[]
    for item in series:
        ys+=item['counts']
        for _,cx,cy,_ in item['curves']:xs+=cx;ys+=cy
    plot,x,y=chart._axes(painter,area,chart._bounds(xs),chart._bounds(ys,True),panel['xlabel'],panel['ylabel'])
    painter.save();painter.setClipRect(plot.adjusted(-1,-1,1,1))
    for index,item in enumerate(series):
        name='s'+str(index);color=PALETTE[item.get('color_index',index)%len(PALETTE)]
        style=chart.graph_style(name,fill=color,edge=color,line_width=.7,line_style='solid',opacity=.45 if len(series)>1 else .8,visible=True)
        if style['visible']:
            painter.setPen(style_pen(style));painter.setBrush(style_color(style['fill'],style['opacity']))
            for bin_index,(left,right,count) in enumerate(zip(item['edges'],item['edges'][1:],item['counts'])):
                rect=QRectF(QPointF(x(left),y(count)),QPointF(x(right),y(0))).normalized()
                painter.drawRect(rect);chart.remember_rect(name,rect)
                info = histogram_info(left,right,count,panel.get('ylabel','Frequency'),item.get('label',''),item.get('source'),item.get('row_indices'),last=bin_index==len(item['counts'])-1)
                chart.remember_hover(rect,info)
                if hasattr(chart,'remember_bar_brush'):chart.remember_bar_brush(rect,info.get('rows',[]))
        for _,cx,cy,_ in item['curves']:
            fit='fit'+str(index)
            chart._path(painter,cx,cy,x,y,color,2,style=chart.graph_style(fit,color=color),target=fit)
    painter.restore();painter.setFont(QFont('Segoe UI',9))
    if panel.get('group_name'):
        chart._text(painter,QRectF(plot.right()+10,area.top(),96,22),panel['group_name'],align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
    for index,item in enumerate(series):
        name='s'+str(index);color=PALETTE[item.get('color_index',index)%len(PALETTE)]
        style=chart.graph_style(name,fill=color,edge=color,opacity=.7,visible=True,legend_visible=True)
        if not style['legend_visible']:continue
        yy=plot.top()+index*42
        painter.setPen(style_pen(dict(style,line_width=.7)));painter.setBrush(style_color(style['fill'],style['opacity']))
        rect=QRectF(plot.right()+10,yy+3,11,11);painter.drawRect(rect)
        chart.remember_rect(name,QRectF(plot.right()+8,yy,94,38))
        label=painter.fontMetrics().elidedText(item['label'],Qt.TextElideMode.ElideRight,78)
        chart._text(painter,QRectF(plot.right()+25,yy,78,20),label,align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        chart._text(painter,QRectF(plot.right()+25,yy+18,78,18),'N '+str(item['n']),align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
