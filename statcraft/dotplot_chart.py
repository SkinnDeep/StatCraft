"""Original dotplot painting; each retained observation keeps its row identity."""
import math
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QFont
from .graph_hover import summary_info
from .graph_interaction import PALETTE,draw_marker,style_pen


def panel_height(panel):
    return max(350,len(panel['lanes'])*85+140+math.ceil(len(panel['series'])/3)*20)


def draw_dotplot_groups(chart,painter,area,panel):
    series=panel['series'];legend_height=math.ceil(len(series)/3)*20+6 if len(series)>1 else 0
    painter.setFont(QFont('Segoe UI',9))
    for index,s in enumerate(series if len(series)>1 else []):
        left=area.left()+20+(index%3)*(area.width()-30)/3;top=area.top()+28+(index//3)*20
        color=PALETTE[s['color_index']%len(PALETTE)];style=chart.graph_style('s'+str(index),color=color,fill=color,edge=color,marker='circle',marker_size=5,opacity=1,visible=True)
        if style['visible']:
            draw_marker(painter,QPointF(left+4,top+7),style)
            label=painter.fontMetrics().elidedText(s['label'],Qt.TextElideMode.ElideRight,int((area.width()-30)/3-22))
            chart._text(painter,QRectF(left+15,top,(area.width()-30)/3-22,18),label,style['color'],Qt.AlignmentFlag.AlignLeft)
    count=len(panel['lanes']);categories=[(count-i-.8,label) for i,label in enumerate(panel['lanes'])]
    plot,x,y=chart._axes(painter,area.adjusted(0,legend_height,0,0),chart._bounds(panel['value_range']),(0,count),panel['xlabel'],panel['ylabel'],y_categories=categories)
    painter.save();painter.setClipRect(plot.adjusted(-1,-1,1,1))
    grid=chart.graph_style('grid',color='#e9edf0',line_width=1,visible=True)
    for lane in range(count):
        if grid['visible'] and getattr(chart,'annotation_grid',True):
            painter.setPen(style_pen(grid));painter.drawLine(QPointF(plot.left(),y(count-lane-.85)),QPointF(plot.right(),y(count-lane-.85)))
    for index,s in enumerate(series):
        name='s'+str(index);color=PALETTE[s['color_index']%len(PALETTE)]
        style=chart.graph_style(name,color=color,fill=color,edge=color,marker='circle',marker_size=6,opacity=1,visible=True)
        if not style['visible'] or style.get('marker')=='none':continue
        height=panel['heights'][s['lane']];step=min(.1,.65/max(1,height))
        # Preserve every observation; very tall stacks use smaller dots.
        actual_size=min(style.get('marker_size',6),max(.8,plot.height()/count*step*.92))
        for point in s['points']:
            pos=QPointF(x(point['x']),y(count-s['lane']-.85+point['level']*step))
            draw_marker(painter,pos,dict(style,marker_size=actual_size));chart.remember_marker(name,pos,actual_size,row=point['row'])
            chart.remember_point_hover(pos,summary_info('point',[('Series',s['label']),('Row',point['row']),(panel['xlabel'] or 'Value',point['value'])],row=point['row'],value=point['value']),actual_size,plot)
    painter.restore()
