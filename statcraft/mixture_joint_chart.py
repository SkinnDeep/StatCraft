"""Conditional profile plots for the joint mixture/process search result."""
import math
from PySide6.QtCore import Qt,QRectF,QPointF,QSize
from PySide6.QtGui import QColor,QFont,QPainter,QPen,QPainterPath
from .snapshot_chart import SnapshotChartWidget
from .graph_hover import point_info
from .plot_ticks import tick_values


def _fmt(v):return '*' if v is None else format(v,'.5g')


class MixtureJointChart(SnapshotChartWidget):
    def __init__(self,entry,parent=None):
        super().__init__(entry,parent);self.result=self.entry.get('result',self.entry);self.error=None;self.title=self.entry.get('title','')
        self.panels=[{'kind':'joint_profiles'}];self.setMinimumSize(880,max(510,150+math.ceil(len(self.result['profiles'])/3)*240));self.setFont(QFont('Segoe UI',9))
    def sizeHint(self):return QSize(1100,self.minimumHeight())
    def paintEvent(self,event):
        self.reset_hover_regions();p=QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor('white'));r=self.result;prediction=r['prediction']
            p.setPen(QColor('#263440'));p.setFont(QFont('Segoe UI',11,QFont.Weight.DemiBold));p.drawText(QRectF(15,5,self.width()-30,28),Qt.AlignmentFlag.AlignCenter,'Predicted '+r['response_name']+' = '+_fmt(prediction['fit']))
            p.setFont(QFont('Segoe UI',9));p.drawText(QRectF(15,35,self.width()-30,22),Qt.AlignmentFlag.AlignCenter,f"{100*r['confidence']:g}% CI: {_fmt(prediction['ci_low'])} to {_fmt(prediction['ci_high'])}     PI: {_fmt(prediction['prediction_low'])} to {_fmt(prediction['prediction_high'])}")
            holds=['Covariate '+n+' = '+_fmt(v) for n,v in zip(r['covariate_names'],r['covariate_values'])]
            if r['block_name']:holds.append(r['block_name']+' = '+str(r['block_value']))
            p.drawText(QRectF(15,58,self.width()-30,35),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,'Fixed: '+('; '.join(holds) if holds else 'none')+' · Red line: selected joint setting')
            profiles=r['profiles'];columns=min(3,max(1,len(profiles)));rows=math.ceil(len(profiles)/columns);area=QRectF(4,102,self.width()-8,self.height()-130)
            for index,profile in enumerate(profiles):
                cell=QRectF(area.left()+index%columns*area.width()/columns,area.top()+index//columns*area.height()/rows,area.width()/columns,area.height()/rows)
                self._profile(p,cell,profile,r['response_name'])
            p.setPen(QColor('#65727e'));p.drawText(QRectF(15,self.height()-24,self.width()-30,22),Qt.AlignmentFlag.AlignCenter,'Profiles vary one process or transfer amount between paired components; other settings stay fixed.')
            self.error=None
        except (ValueError,TypeError,KeyError,IndexError,ZeroDivisionError,OverflowError) as e:
            self.error=str(e);p.setPen(QColor('#9f3131'));p.drawText(QRectF(self.rect()),Qt.TextFlag.TextWordWrap,str(e))
        finally:p.end()
    def _profile(self,p,cell,profile,response):
        xs=profile['x'];ys=profile['fits'];lo,hi=min(ys),max(ys);pad=max(.1,(hi-lo)*.08);lo-=pad;hi+=pad
        left,right=profile['low'],profile['high'];right=right if right>left else left+1.
        plot=QRectF(cell.left()+60,cell.top()+38,max(25,cell.width()-78),max(25,cell.height()-90));self._current_plot=plot
        tx=lambda x:plot.left()+(x-left)/(right-left)*plot.width();ty=lambda y:plot.bottom()-(y-lo)/(hi-lo)*plot.height()
        p.setFont(QFont('Segoe UI',9,QFont.Weight.DemiBold));p.setPen(QColor('#263440'));p.drawText(QRectF(cell.left()+5,cell.top()+3,cell.width()-10,30),Qt.AlignmentFlag.AlignCenter,profile['name']+' = '+_fmt(profile['current']))
        p.setFont(QFont('Segoe UI',8));p.fillRect(plot,QColor('#fafafa'))
        for y in tick_values(lo,hi,count=4):
            p.setPen(QPen(QColor('#e3e7eb'),.8));p.drawLine(QPointF(plot.left(),ty(y)),QPointF(plot.right(),ty(y)));p.setPen(QColor('#5b6770'));p.drawText(QRectF(plot.left()-57,ty(y)-9,50,18),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,_fmt(y))
        for x in tick_values(left,right,count=4):
            p.setPen(QColor('#5b6770'));p.drawText(QRectF(tx(x)-27,plot.bottom()+4,54,19),Qt.AlignmentFlag.AlignCenter,_fmt(x))
        path=QPainterPath()
        for index,(x,y) in enumerate(zip(xs,ys)):
            point=QPointF(tx(x),ty(y))
            if index:path.lineTo(point)
            else:path.moveTo(point)
            self.remember_point_hover(point,point_info(x,y,profile['name'],response),clip=plot)
        p.save();p.setClipRect(plot);p.setPen(QPen(QColor('#056eb2'),1.7));p.drawPath(path);p.setPen(QPen(QColor('#c03944'),1.2,Qt.PenStyle.DashLine));p.drawLine(QPointF(tx(profile['current']),plot.top()),QPointF(tx(profile['current']),plot.bottom()));p.restore()
        p.setPen(QPen(QColor('#939ea8'),.8));p.drawRect(plot);p.setPen(QColor('#65727e'));p.drawText(QRectF(cell.left()+10,plot.bottom()+26,cell.width()-20,20),Qt.AlignmentFlag.AlignCenter,'Amount transfer' if profile['role']=='component' else 'Worksheet process units')
