"""Original P/U chart, cumulative rate, size diagnostic and capability summary."""
import math
from PySide6.QtCore import QPointF,QRectF,QSize,Qt,Signal
from PySide6.QtGui import QColor,QFont,QPainter,QPen,QPainterPath
from PySide6.QtWidgets import QWidget,QSizePolicy
from .graph_interaction import GraphInteractionMixin,draw_marker,style_pen
from .attribute_capability_report import _fmt


class AttributeCapabilityChartWidget(GraphInteractionMixin,QWidget):
    objectSelected=Signal(str)
    objectActivated=Signal(str)
    brushRowsSelected=Signal(list)

    def __init__(self,entry,parent=None):
        super().__init__(parent);self.entry=entry;self.result=entry.get('result',{})
        self.panels=[{'kind':'xy'} for _ in range(3)]
        self._init_graph_interaction();self.setMinimumSize(760,560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)

    def sizeHint(self):return QSize(940,640)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('white'));self.hit_regions=[];self.brush_regions=[]
        result=self.result;binomial=result.get('method')=='binomial'
        title=result.get('title') or result.get('method','').title()+' Capability Analysis'
        p.setPen(QColor('#202020'));p.setFont(QFont('Segoe UI',14,QFont.Weight.DemiBold))
        title_rect=QRectF(20,8,self.width()-40,30);p.drawText(title_rect,Qt.AlignmentFlag.AlignCenter,title)
        self._panel_index=0
        width=(self.width()-110)/2;height=(self.height()-120)/2
        panels=[QRectF(38,68,width,height),QRectF(width+98,68,width,height),
                QRectF(38,height+104,width,height),QRectF(width+98,height+104,width,height)]
        rows=result.get('rows',[]);rates=result.get('rates',[])
        self._plot(p,panels[0],'P Chart' if binomial else 'U Chart',rows,rates,
                   'Sample','Proportion' if binomial else 'DPU',
                   [('LCL',result.get('lcl',[]),'#b13b36'),('UCL',result.get('ucl',[]),'#b13b36'),('Center',result.get('center_line',[]),'#3c7c47')])
        self._panel_index=1
        self._plot(p,panels[1],'Cumulative % Defective' if binomial else 'Cumulative DPU',rows,
                   [v*100 if binomial else v for v in result.get('cumulative_rates',[])],
                   'Sample','Percent' if binomial else 'DPU')
        self._panel_index=2
        self._plot(p,panels[2],'Rate vs Sample Size',result.get('sample_sizes',[]),rates,
                   'Sample Size','Proportion' if binomial else 'DPU',connect=False)
        self._summary(p,panels[3],binomial)
        self.draw_selection(p);p.end()

    def _plot(self,p,box,title,xs,ys,xlabel,ylabel,limits=(),connect=True):
        p.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold));p.setPen(QColor('#202020'))
        p.drawText(QRectF(box.left(),box.top()-22,box.width(),22),Qt.AlignmentFlag.AlignCenter,title)
        plot=box.adjusted(20,4,-10,-38);self.remember_axes(plot)
        sequences=[ys]+[v for _,v,_ in limits]
        all_y=[float(v) for seq in sequences for v in seq if v is not None and math.isfinite(v)]
        if not xs or not all_y:return
        xmin=min(xs);xmax=max(xs);ymin=min(0,min(all_y));ymax=max(all_y)
        if xmax==xmin:xmin-=.5;xmax+=.5
        if ymax==ymin:ymax=ymin+1
        span=ymax-ymin;ymin=max(0,ymin-span*.06);ymax+=span*.08
        point=lambda x,y:QPointF(plot.left()+(x-xmin)/(xmax-xmin)*plot.width(),plot.bottom()-(y-ymin)/(ymax-ymin)*plot.height())
        p.setFont(QFont('Segoe UI',8))
        for i in range(4):
            value=ymin+(ymax-ymin)*i/3;y=point(xmin,value).y()
            p.setPen(QPen(QColor('#e5e5e5'),1));p.drawLine(QPointF(plot.left(),y),QPointF(plot.right(),y))
            p.setPen(QColor('#505050'));p.drawText(QRectF(box.left()-25,y-8,42,16),Qt.AlignmentFlag.AlignRight,f'{value:.4g}')
        p.setPen(QPen(QColor('#777777'),1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(plot)
        for x in (xmin,(xmin+xmax)/2,xmax):p.drawText(QRectF(point(x,ymin).x()-30,plot.bottom()+4,60,15),Qt.AlignmentFlag.AlignCenter,_fmt(x))
        p.drawText(QRectF(plot.left(),plot.bottom()+20,plot.width(),18),Qt.AlignmentFlag.AlignCenter,xlabel)
        p.save();p.translate(box.left()-28,plot.center().y());p.rotate(-90);p.drawText(QRectF(-70,-10,140,18),Qt.AlignmentFlag.AlignCenter,ylabel);p.restore()
        p.save();p.setClipRect(plot.adjusted(-3,-3,3,3))
        for index,(label,values,color) in enumerate(limits):
            points=[point(x,y) for x,y in zip(xs,values) if y is not None]
            style=self.graph_style('ref'+str(index),color=color,line_width=1,line_style='dash')
            if style.get('visible',True):
                p.setPen(style_pen(style));self._line(p,points);self.remember_path('ref'+str(index),points)
        points=[point(x,y) for x,y in zip(xs,ys)]
        line_style=self.graph_style('s1',color='#3875a5',line_width=1.3)
        if connect and line_style.get('visible',True):
            p.setPen(style_pen(line_style));self._line(p,points);self.remember_path('s1',points)
        marker_style=self.graph_style('s0',color='#3875a5')
        for index,point_value in enumerate(points):
            selected_style=dict(marker_style)
            if self._panel_index==0 and xs[index] in self.result.get('violations',[]):selected_style.update(color='#b13b36',fill='#b13b36')
            draw_marker(p,point_value,selected_style);self.remember_marker('s0',point_value,row=self.result['rows'][index] if self._panel_index in (0,2) else None)
        p.restore()

    @staticmethod
    def _line(p,points):
        if not points:return
        path=QPainterPath(points[0])
        for point in points[1:]:path.lineTo(point)
        p.drawPath(path)

    def _summary(self,p,box,binomial):
        result=self.result;p.setPen(QColor('#202020'));p.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold))
        p.drawText(box.adjusted(20,0,-10,0),Qt.AlignmentFlag.AlignTop,'Summary Statistics')
        stats=[('Samples',result.get('n_samples')),('Total count',result.get('total_count'))]
        if binomial:
            stats += [('% Defective',result.get('percent_defective')),('PPM Defective',result.get('ppm_defective')),
                      ('Process Z',result.get('process_z_label') or result.get('process_z'))]
        else:stats += [('Mean DPU',result.get('mean_dpu')),('Min DPU',result.get('min_dpu')),('Max DPU',result.get('max_dpu'))]
        ci=result.get('percent_ci') if binomial else result.get('rate_ci')
        if ci:stats.append((f"{result.get('confidence',95):g}% interval",' to '.join(_fmt(v) for v in ci)))
        stats.append(('Beyond limits',len(result.get('violations',[]))))
        p.setFont(QFont('Segoe UI',9))
        for index,(label,value) in enumerate(stats):
            y=box.top()+30+index*22
            p.drawText(QRectF(box.left()+20,y,box.width()*.49,22),Qt.AlignmentFlag.AlignLeft,label)
            p.drawText(QRectF(box.left()+box.width()*.48,y,box.width()*.50-10,22),Qt.AlignmentFlag.AlignRight,_fmt(value))

    def editable_objects(self):
        objects=[]
        for panel in range(3):
            for name,label,caps,defaults in [
                ('s0','Data symbols',['color','fill','edge','marker','marker_size','opacity','visible'],{'color':'#3875a5','marker':'circle','marker_size':6.4,'visible':True}),
                ('s1','Data line',['color','line_width','line_style','opacity','visible'],{'color':'#3875a5','line_width':1.3,'visible':True})]:
                if panel==2 and name=='s1':continue
                objects.append({'target':f'p{panel}:{name}','label':f'Panel {panel+1} — {label}','capabilities':caps,'defaults':defaults})
        for index,label in enumerate(('Lower control limit','Upper control limit','Center line')):
            objects.append({'target':f'p0:ref{index}','label':label,'capabilities':['color','line_width','line_style','opacity','visible'],'defaults':{'color':'#3c7c47' if index==2 else '#b13b36','line_width':1,'line_style':'dash','visible':True}})
        return objects

