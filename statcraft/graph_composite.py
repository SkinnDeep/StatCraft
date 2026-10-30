"""Live Qt composition of detached graph snapshots, independent of native files."""
import math
from PySide6.QtCore import Signal,Qt,QEvent
from PySide6.QtWidgets import QWidget,QGridLayout,QSizePolicy
from .compositions import validate_composition
from .graph_frame import GraphFrame


def _ranges(chart,panel):
    if '_xb' in panel and '_yb' in panel:return panel['_xb'],panel['_yb']
    kind=panel.get('kind')
    if kind=='categorical_points':
        from .categorical_points_chart import plot_values
        return (.25,len(panel['items'])+.75),chart._bounds(plot_values(panel))
    if kind=='dotplot_groups':return chart._bounds(panel['value_range']),(0,len(panel['lanes']))
    if kind=='boxplot_groups':return (.25,len(panel['items'])+.75),chart._bounds([value for item in panel['items'] for value in item['source']])
    if kind=='histogram_groups':
        ys=[count for series in panel['series'] for count in series['counts']]+[value for series in panel['series'] for _,_,values,_ in series['curves'] for value in values]
        return chart._bounds(panel['edges']),chart._bounds(ys,True)
    if kind in ('bars','intervals') and '_yb' in panel:
        count=len(panel.get('categories',panel.get('items',[])))
        return (.25,count+.75),panel['_yb']
    if kind=='histogram':
        ys=panel['counts']+[v for _,_,values,_ in panel.get('curves',[]) for v in values]
        return chart._bounds(panel['edges']),chart._bounds(ys,True)
    if kind=='boxplot':return chart._bounds(list(panel['box'].values())+panel['outliers']),(0,1)
    if kind in ('scatter','multi_scatter','normal_probability','line'):
        return chart._bounds(panel['x']),chart._bounds(panel['y']+[v for _,values,_ in panel.get('lines',[]) for v in values])
    return None


class GraphCompositeWidget(QWidget):
    objectSelected=Signal(str);objectActivated=Signal(str);brushRowsSelected=Signal(list)

    def __init__(self,entry,parent=None):
        super().__init__(parent);self.entry=entry;self.title='';self.error=None
        self.graph_styles={};self.selected_object=None;self.panels=[];self.frames=[];self._result=None;self._hover_charts=set()
        self.grid=QGridLayout(self);self.grid.setContentsMargins(6,6,6,6);self.grid.setSpacing(10)
        self.refresh_composition()

    def editable_objects(self):return []

    def eventFilter(self,watched,event):
        if watched in self._hover_charts and event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease,QEvent.Type.MouseButtonDblClick):
            event.ignore();return True
        return super().eventFilter(watched,event)


    def refresh_composition(self):
        result=self.entry['result']
        if result is self._result:return
        validate_composition(result)
        from .modern_charts import ChartWidget
        from .modern_expanded_charts import ExpandedChartWidget
        while self.grid.count():
            item=self.grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for index in range(9):self.grid.setRowMinimumHeight(index,0);self.grid.setColumnMinimumWidth(index,0);self.grid.setRowStretch(index,0);self.grid.setColumnStretch(index,0)
        columns=result['columns'];rows=result.get('rows',math.ceil(len(result['graphs'])/columns))
        self.frames=[];self._hover_charts=set();row_heights=[220]*rows;column_widths=[280]*columns
        for index,child in enumerate(result['graphs']):
            chart=ExpandedChartWidget(child) if child['result'].get('graph')=='expanded' else ChartWidget(child)
            if chart.error:raise ValueError('Graph '+str(index+1)+': '+chart.error)
            height=len(chart.panels)*max(200,max((len(panel.get('series',[]))*42+100 for panel in chart.panels if panel['kind']=='histogram_groups'),default=0))+60
            if child['result'].get('graph')=='dotplot_graphs':
                from .dotplot_chart import panel_height
                height=sum(panel_height(panel) for panel in chart.panels)+60
                column_widths[index%columns]=max(column_widths[index%columns],650)
            if child['result'].get('graph') in ('categorical_points','boxplot_graphs'):
                height=len(chart.panels)*330+60
                column_widths[index%columns]=max(column_widths[index%columns],max(len(panel['items']) for panel in chart.panels)*70+180)
            row_heights[index//columns]=max(row_heights[index//columns],height)
            frame=GraphFrame(chart,child,self)
            chart.setMinimumSize(0,0);chart.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored)
            frame.apply_appearance()
            # Let the child receive pointer movement and tooltip requests while
            # retaining the layout's existing read-only editing contract.
            chart.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,False)
            chart.installEventFilter(self);self._hover_charts.add(chart)
            frame.setToolTip('Edit the source graph, then rebuild the layout or panels.')
            frame.title_label.setStyleSheet('font-size: 10pt; font-weight: 600;')
            self.grid.addWidget(frame,index//columns,index%columns);self.frames.append(frame)
        for index in range(rows):self.grid.setRowMinimumHeight(index,row_heights[index]);self.grid.setRowStretch(index,1)
        for index in range(columns):self.grid.setColumnMinimumWidth(index,column_widths[index]);self.grid.setColumnStretch(index,1)
        self.setMinimumSize(max(520,sum(column_widths)+12+(columns-1)*10),max(300,sum(row_heights)+12+(rows-1)*10))
        self.panels=[{'kind':'composite'} for _ in self.frames]
        if result['graph']=='panel_graph':self._share_scales(result)
        self._result=result;self.updateGeometry();self.update()

    def _share_scales(self,result):
        ranges={}
        for frame in self.frames:
            for index,panel in enumerate(frame.chart.panels):
                bounds=_ranges(frame.chart,panel)
                if bounds:
                    item=ranges.setdefault(index,{'x':[],'y':[]})
                    item['x'].append(bounds[0]);item['y'].append(bounds[1])
        combined={index:{axis:(min(pair[0] for pair in pairs),max(pair[1] for pair in pairs)) for axis,pairs in item.items() if result['shared_'+axis] and pairs} for index,item in ranges.items()}
        for frame in self.frames:frame.chart.panel_annotation_limits=combined
