"""Original constrained ternary contours and mixture optimizer composition plots."""
import math
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QColor,QFont,QPolygonF,QPainterPath,QPen,QPainter
from .modern_charts import ChartWidget,INK
from .model_plots_chart import CONTOUR_PALETTE
from .graph_interaction import style_pen,style_color


def _clip_value(poly,level,above):
    if not poly:return []
    output=[];previous=poly[-1];before=previous[2]>=level if above else previous[2]<=level
    for current in poly:
        inside=current[2]>=level if above else current[2]<=level
        if inside!=before:
            weight=(level-previous[2])/(current[2]-previous[2])
            output.append((previous[0]+weight*(current[0]-previous[0]),previous[1]+weight*(current[1]-previous[1]),level))
        if inside:output.append(current)
        previous=current;before=inside
    return output


def _fmt(value):return '*' if value is None else format(value,'.5g')


class MixtureExplorationChart(ChartWidget):
    def _prepare(self):
        r=self.result;self.panel_columns=1
        self.panels=[dict(kind='mixture_contour' if r['analysis']=='mixture_contour' else 'mixture_optimum')]
        self.setMinimumSize(800,650 if r['analysis']=='mixture_contour' else max(450,170+len(r['component_names'])*48))
        self.band_polygons=[]
        if r['analysis']=='mixture_contour':
            levels=r['levels'];self.band_colors=[CONTOUR_PALETTE[round(i*(len(CONTOUR_PALETTE)-1)/max(1,len(levels)))] for i in range(len(levels)+1)]
            for triangle in r['triangles']:
                raw=[(r['points'][i]['x'],r['points'][i]['y'],r['points'][i]['fit']) for i in triangle]
                for band in range(len(levels)+1):
                    poly=raw
                    if band:poly=_clip_value(poly,levels[band-1],True)
                    if band<len(levels):poly=_clip_value(poly,levels[band],False)
                    if len(poly)>=3:self.band_polygons.append((band,[(v[0],v[1]) for v in poly]))
            self.note='Amounts in original units; blank regions violate component bounds. Contours interpolate the fitted mesh.'
        else:self.note='Optimizes the fitted mean within fixed-total bounds; uncertainty is conditional on the selected mixture.'

    def _draw_panel(self,p,area,panel):
        if panel['kind']=='mixture_contour':self._contour(p,area)
        else:self._optimum(p,area)

    def _contour(self,p,area):
        r=self.result;h=math.sqrt(3)/2
        header=160 if r.get('hold_values') or r.get('conditioning') else 125
        width=min(area.width()-300,(area.height()-header)/h)
        left=area.left()+100+(area.width()-300-width)/2;bottom=area.bottom()-75
        point=lambda x,y:QPointF(left+x*width,bottom-y*width)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#f5f6f7'))
        p.drawPolygon(QPolygonF([point(0,0),point(1,0),point(.5,h)]))
        p.setRenderHint(QPainter.RenderHint.Antialiasing,False)
        for band,poly in self.band_polygons:
            p.setBrush(QColor(self.band_colors[band]));p.drawPolygon(QPolygonF([point(x,y) for x,y in poly]))
        p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        grid=self.graph_style('grid',color='#a8b8c4',line_width=.7,line_style='dot',visible=True)
        if grid.get('visible',True) and getattr(self,'annotation_grid',True):
            p.setPen(style_pen(grid))
            for t in (.2,.4,.6,.8):
                for ends in (((.5*(1-t),h*(1-t)),(1-t,0)),((t,0),(.5+.5*t,h*(1-t))),((.5*t,h*t),(1-.5*t,h*t))):
                    p.drawLine(point(*ends[0]),point(*ends[1]))
            self.remember_rect('grid',QRectF(point(0,h),point(1,0)))
        contours=self.graph_style('ref0',color='#45515b',line_width=.9,line_style='solid',visible=True)
        if contours.get('visible',True):
            p.setPen(style_pen(contours))
            for line in r['contour_lines']:
                for x1,y1,x2,y2 in line['segments']:
                    a=point(x1,y1);b=point(x2,y2);p.drawLine(a,b);self.remember_path('ref0',[a,b])
        axis=self.graph_style('axis',color='#52616d',line_width=1.1,line_style='solid',visible=True)
        p.setFont(QFont('Segoe UI',10))
        if axis.get('visible',True):
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(style_pen(axis))
            boundary=[point(*v) for v in r['polygon']]
            p.drawPolygon(QPolygonF(boundary));self.remember_path('axis',boundary+[boundary[0]])
            p.drawPolygon(QPolygonF([point(0,0),point(1,0),point(.5,h)]))
            for t in (0.,.2,.4,.6,.8,1.):
                label=_fmt(t*r['display_total'])
                a=point(.5*(1-t),h*(1-t));b=point(t,0);c=point(1-.5*t,h*t)
                self._text(p,QRectF(a.x()-65,a.y()-10,52,20),label,axis['color'],Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self._text(p,QRectF(b.x()-30,b.y()+6,60,20),label,axis['color'])
                self._text(p,QRectF(c.x()+12,c.y()-10,60,20),label,axis['color'],Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            p.setFont(QFont('Segoe UI',11,QFont.Weight.DemiBold));names=r['selected_names']
            for name,rect in [(names[0],QRectF(left-80,bottom+34,190,40)),(names[1],QRectF(left+width-110,bottom+34,190,40)),(names[2],QRectF(left+width/2-130,bottom-width*h-45,260,34))]:
                self._text(p,rect,p.fontMetrics().elidedText(name,Qt.TextElideMode.ElideRight,int(rect.width())),axis['color'])
        legend_x=area.right()-140;legend_y=area.top()+45
        p.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold));self._text(p,QRectF(legend_x-5,legend_y-32,138,27),p.fontMetrics().elidedText(r['response_name'],Qt.TextElideMode.ElideRight,138),INK)
        p.setFont(QFont('Segoe UI',9));levels=r['levels']
        for i,color in enumerate(self.band_colors):
            y=legend_y+i*min(29,(area.height()-80)/len(self.band_colors));p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(color));p.drawRect(QRectF(legend_x,y,22,21))
            label=(_fmt(r['value_range'][0])+' (constant)') if not levels else ('< '+_fmt(levels[0])) if i==0 else ('≥ '+_fmt(levels[-1])) if i==len(levels) else _fmt(levels[i-1])+' – '+_fmt(levels[i])
            self._text(p,QRectF(legend_x+29,y,108,21),label,INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        if r['hold_values'] or r.get('conditioning'):
            descriptions=[item['name']+' = '+_fmt(item['value']) for item in r['hold_values']]
            if r.get('conditioning'):descriptions.append(r['conditioning']['summary'])
            held='Held: '+'; '.join(descriptions)
            self._text(p,QRectF(area.left()+10,area.top()-5,area.width()-20,26),p.fontMetrics().elidedText(held,Qt.TextElideMode.ElideRight,int(area.width()-20)),INK)

    def _optimum(self,p,area):
        r=self.result;prediction=r['prediction'];names=r['component_names'];amounts=r['components'];bounds=r['component_bounds']
        p.setFont(QFont('Segoe UI',12,QFont.Weight.DemiBold))
        heading=r['response_name']+': '+_fmt(prediction['fit'])+'    Goal: '+r['goal']
        if r['target'] is not None:heading+=' '+_fmt(r['target'])
        self._text(p,QRectF(area.left()+24,area.top(),area.width()-48,30),heading,INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        p.setFont(QFont('Segoe UI',10))
        interval='Mean confidence interval: '+_fmt(prediction['ci_low'])+' to '+_fmt(prediction['ci_high']) if prediction['ci_low'] is not None else 'Mean confidence interval unavailable for this fit'
        self._text(p,QRectF(area.left()+24,area.top()+32,area.width()-48,25),interval,INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        if r.get('conditioning'):
            fixed=p.fontMetrics().elidedText(r['conditioning']['summary'],Qt.TextElideMode.ElideRight,int(area.width()-48))
            self._text(p,QRectF(area.left()+24,area.top()+60,area.width()-48,25),fixed,INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        left=area.left()+170;right=area.right()-210;top=area.top()+(110 if r.get('conditioning') else 95);bottom=area.bottom()-55
        scale=lambda value:left+(value/r['total'])*(right-left)
        axis=self.graph_style('axis',color='#52616d',line_width=1,line_style='solid',visible=True)
        grid=self.graph_style('grid',color='#e6ebef',line_width=1,line_style='solid',visible=True)
        for t in (0.,.25,.5,.75,1.):
            x=scale(t*r['total'])
            if grid.get('visible',True) and getattr(self,'annotation_grid',True):p.setPen(style_pen(grid));p.drawLine(QPointF(x,top-10),QPointF(x,bottom));self.remember_path('grid',[QPointF(x,top-10),QPointF(x,bottom)])
            if axis.get('visible',True):self._text(p,QRectF(x-35,bottom+7,70,22),_fmt(t*r['total']),axis['color'])
        style=self.graph_style('bars',fill='#79add8',edge='#466a85',opacity=1,line_width=1,line_style='solid',visible=True)
        row_height=(bottom-top)/len(names)
        for i,(name,amount,bound) in enumerate(zip(names,amounts,bounds)):
            y=top+i*row_height+row_height/2
            p.setPen(QPen(QColor('#98a6b1'),1));p.setBrush(QColor('#eef1f3'));p.drawRect(QRectF(scale(bound['low']),y-15,scale(bound['high'])-scale(bound['low']),30))
            if style.get('visible',True):
                p.setPen(style_pen(style));p.setBrush(style_color(style['fill'],style.get('opacity',1)));rect=QRectF(left,y-10,scale(amount)-left,20);p.drawRect(rect);self.remember_rect('bars',rect)
            if axis.get('visible',True):
                self._text(p,QRectF(area.left()+8,y-13,145,26),p.fontMetrics().elidedText(name,Qt.TextElideMode.ElideRight,145),axis['color'],Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                self._text(p,QRectF(right+14,y-13,195,26),_fmt(amount)+'  ['+_fmt(bound['low'])+', '+_fmt(bound['high'])+']',axis['color'],Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        if axis.get('visible',True):
            p.setPen(style_pen(axis));p.drawLine(QPointF(left,bottom),QPointF(right,bottom));self.remember_path('axis',[QPointF(left,bottom),QPointF(right,bottom)])
            self._text(p,QRectF(left,bottom+31,right-left,22),'Component amount',axis['color'])
