"""Interactive, closure-preserving multi-response mixture optimizer profiles."""
import copy
from PySide6.QtCore import Qt,QRectF,Signal
from .modern_charts import ChartWidget
from . import optimizer_chart


class MixtureMultiChart(ChartWidget):
    settingSelected=Signal(list)

    def _prepare(self):
        r=self.result
        adapted=copy.deepcopy(r)
        adapted['predictions']=[dict(row,fit=row['prediction']['fit']) for row in r['responses']]
        adapted['optimal_composite_desirability']=r['composite_desirability']
        for profile in adapted['profiles']:
            profile['role']='continuous';profile['name']=profile['name']+' ↔ '+profile['balance_name']
        optimizer_chart.prepare(self,adapted)
        self.panels[0]['setting_label']='Search Result' if r['analysis']=='mixture_multi_optimization' else 'Selected Setting'
        self.setMinimumSize(max(820,190+len(adapted['profiles'])*180),max(610,170+(1+len(r['responses']))*130))
        self.note='Click a profile to transfer amount to/from its paired component; other amounts stay fixed. Adjusted settings are saved separately.'
        self.profile_cells=[];self.setMouseTracking(True)

    def _draw_panel(self,painter,area,panel):
        optimizer_chart.draw_panel(self,painter,area,panel)
        self.profile_cells=[]
        profiles=panel['profiles'];nrows=1+len(panel['predictions']);ncols=len(profiles)
        left=min(190.,max(145.,area.width()*.23));top=area.top()+80
        grid_left=area.left()+left+8;grid_width=max(80.,area.width()-left-22)
        cell_width=grid_width/ncols;cell_height=max(80.,area.height()-98)/nrows
        for column,profile in enumerate(profiles):
            if profile['high']<=profile['low']:continue
            for row in range(nrows):
                rect=QRectF(grid_left+column*cell_width+13,top+row*cell_height+13,cell_width-26,cell_height-26)
                self.profile_cells.append((rect,profile))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and not self.is_brushing:
            for rect,profile in self.profile_cells:
                if rect.contains(event.position()):
                    value=profile['low']+(event.position().x()-rect.left())/rect.width()*(profile['high']-profile['low'])
                    components=list(self.result['components']);position=profile['position'];balance=profile['balance_position']
                    delta=value-components[position];components[position]=value;components[balance]-=delta
                    self.settingSelected.emit(components);event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if not self.is_brushing:self.setCursor(Qt.CursorShape.PointingHandCursor if any(rect.contains(event.position()) for rect,unused in self.profile_cells) else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:event.accept();return
        super().mouseDoubleClickEvent(event)
