"""Original Taguchi main-effects charts with real level labels and editable series."""
import copy
import math
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QFont
from .modern_charts import ChartWidget,BLUE,GREEN,INK


class TaguchiEffectsWidget(ChartWidget):
    def _prepare(self):
        result=self.result
        self.panels=[]
        for source in result.get('panels',[]):
            panel=copy.deepcopy(source);count=len(panel['y'])
            if not any(value is not None for value in panel['y']):continue
            panel.update(kind='line',taguchi=True,x=list(range(1,count+1)),xlabel=panel['factor_name'],
                         lines=[('Grand mean',[panel['grand_mean']]*count,GREEN)] if panel.get('grand_mean') is not None else [])
            self.panels.append(panel)
        self.panel_columns=min(3,len(result.get('factor_indices',[]))) or 1
        rows=math.ceil(len(self.panels)/self.panel_columns)
        self.setMinimumSize(max(640,self.panel_columns*320),max(360,rows*300+40))
        self.note='Dashed line: grand mean. Level averages; gaps are unavailable. Higher S/N is preferred.'

    def _draw_panel(self,painter,area,panel):
        painter.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold))
        self._text(painter,QRectF(area.left()+65,area.top(),area.width()-80,23),panel['title'],INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        values=[value for candidate in self.panels if candidate['metric']==panel['metric'] for value in candidate['y'] if value is not None]
        if panel.get('grand_mean') is not None:values.append(panel['grand_mean'])
        bounds=self._bounds(values)
        plot,x,y=self._axes(painter,area,(.5,len(panel['y'])+.5),bounds,panel['xlabel'],panel['ylabel'],categories=panel['x_labels'])
        painter.save();painter.setClipRect(plot.adjusted(-1,-1,1,1))
        for index,(_,ys,color) in enumerate(panel['lines']):
            self._path(painter,panel['x'],ys,x,y,color,1.1,True,style=self.graph_style('ref'+str(index)),target='ref'+str(index))
        style=self.graph_style('s0',color=BLUE)
        if style.get('visible',True):
            self._path(painter,panel['x'],panel['y'],x,y,BLUE,1.6,style=style,target='s0')
            for at,value in zip(panel['x'],panel['y']):
                if value is not None:self._marker(painter,QPointF(x(at),y(value)),BLUE,0,style,'s0')
        painter.restore()


def prepare_mixture(chart,result):
    from .glm import residual_panels
    adjusted=copy.deepcopy(result)
    adjusted['options']={'graphs':'four' if result.get('show_graphs',True) else 'none'}
    adjusted['row_indices']=result.get('row_indices',result.get('used_rows',[]))
    chart.panels=residual_panels(adjusted)
    for panel in chart.panels:
        panel['nice_axes']=True
        panel['frequency_ticks']=panel.get('kind')=='histogram'
        panel['positive_order']=panel.get('title')=='Versus Order'
    chart.panel_columns=2;chart.setMinimumSize(760,680)
    chart.note='Residual diagnostics for '+str(result.get('response_name','Mixture response'))
