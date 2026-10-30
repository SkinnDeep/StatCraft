"""Original categorical points, mean bars and Student-t/SE interval rendering."""
from PySide6.QtCore import QPointF,QRectF
from .graph_hover import point_info,summary_info
from .graph_interaction import PALETTE,draw_marker,style_pen,style_color


def plot_values(panel):
    values=[];display=panel['display']
    for item in panel['items']:
        if display['individual']:values.extend(item['source'])
        values.extend([item['mean'],item['median']])
        if display['interval']:values.extend(item[k] for k in ('lower','upper') if item[k] is not None)
    if display['bar']:values.append(0)
    return values


def draw_categorical_points(chart,p,area,panel):
    items=panel['items'];d=panel['display']
    plot,x,y=chart._axes(p,area,(.25,len(items)+.75),chart._bounds(plot_values(panel)),panel['xlabel'],panel['ylabel'],categories=[item['label'] for item in items])
    p.save();p.setClipRect(plot.adjusted(-1,-1,1,1))
    width=min(50,(x(1.4)-x(1))*.9)
    for index,item in enumerate(items):
        position=index+1;center=x(position);color=PALETTE[item['color_index']%len(PALETTE)]
        if d['bar']:
            target='bar'+str(index);style=chart.graph_style(target,fill=color,edge=color,line_width=1,opacity=.3,visible=True)
            if style['visible']:
                rect=QRectF(QPointF(center-width/2,y(0)),QPointF(center+width/2,y(item['mean']))).normalized();p.setPen(style_pen(style));p.setBrush(style_color(style['fill'],style['opacity']));p.drawRect(rect);chart.remember_rect(target,rect)
                chart.remember_hover(rect,summary_info('bar',[('Group',item['label']),('N',item['n']),('Mean',item['mean'])]),plot)
        if d['interval']:
            target='int'+str(index);style=chart.graph_style(target,color=color,line_width=1.6,visible=True)
            if style['visible']:
                high=plot.top()+3 if item['upper'] is None else y(item['upper']);low=plot.bottom()-3 if item['lower'] is None else y(item['lower'])
                p.setPen(style_pen(style));p.drawLine(QPointF(center,low),QPointF(center,high))
                for value,pixel,direction in ((item['lower'],low,-1),(item['upper'],high,1)):
                    if value is not None:p.drawLine(QPointF(center-5,pixel),QPointF(center+5,pixel))
                    else:
                        p.drawLine(QPointF(center,pixel),QPointF(center-4,pixel+direction*7));p.drawLine(QPointF(center,pixel),QPointF(center+4,pixel+direction*7))
                chart.remember_path(target,[QPointF(center,low),QPointF(center,high)])
        if d['individual']:
            target='s'+str(index);style=chart.graph_style(target,color=color,fill=color,edge=color,marker='circle',marker_size=5,opacity=.8,visible=True)
            if style['visible'] and style.get('marker')!='none':
                for row,value in zip(item['row_indices'],item['source']):
                    jitter=(((row*37)%101)/100-.5)*2*panel['jitter'];point=QPointF(x(position+jitter),y(value))
                    draw_marker(p,point,style);chart.remember_marker(target,point,style.get('marker_size',5),row=row)
                    chart.remember_point_hover(point,point_info(item['label'],value,panel['xlabel'] or 'Group',panel['ylabel'] or 'Value',row=row),style.get('marker_size',5),plot)
        for key,target,shape,value in (('mean_symbol','mean','diamond',item['mean']),('median_symbol','median','cross',item['median'])):
            if d[key]:
                name=target+str(index);style=chart.graph_style(name,color=color,fill=color,edge=color,marker=shape,marker_size=9,opacity=1,visible=True)
                if style['visible'] and style.get('marker')!='none':
                    point=QPointF(center,y(value));draw_marker(p,point,style);chart.remember_marker(name,point,style.get('marker_size',9))
                    chart.remember_point_hover(point,summary_info(target,[('Group',item['label']),('N',item['n']),(target.title(),value)]),style.get('marker_size',9),plot)
    for option,key,target in (('median_connect','median','ref0'),('mean_connect','mean','ref1')):
        if d[option]:chart._path(p,list(range(1,len(items)+1)),[item[key] for item in items],x,y,'#555555',style=chart.graph_style(target,color='#555555'),target=target)
    p.restore()
