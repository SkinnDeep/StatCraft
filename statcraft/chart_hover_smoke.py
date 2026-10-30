"""Packaged graph data tips exercised by real Qt pointer events."""
from PySide6.QtCore import QEvent,QPointF,Qt
from PySide6.QtGui import QMouseEvent
from .graph_hover import histogram_info
from .modern_charts import ChartWidget
from .native_output_chart import NativeOutputChart
from .graph_frame import GraphFrame
from .graph_composite import GraphCompositeWidget
from .graph_layouts import build_layout
from .histogram_graphs import build_histograms
from .model import Worksheet,Column


def histogram_entry():
    return {'title':'Histogram','result':{'graph':'histogram','graph_data':[[0.,1.,2.],[3.,3.]],'histogram_source':[0.,.1,.9,1.,1.9,2.],'xlabel':'Strength','ylabel':'Frequency'}}


def move(app,chart,position):
    event=QMouseEvent(QEvent.Type.MouseMove,position,QPointF(chart.mapToGlobal(position.toPoint())),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
    app.sendEvent(chart,event)


def verify_chart_hover(app,p,w,temp,checkpoint):
    checkpoint('Real graph hover data: histogram counts/boundaries, normalized groups, native gallery, points, layout children and export')
    widgets=[]
    try:
        chart=ChartWidget(histogram_entry());widgets.append(chart);chart.resize(900,600);chart.show();app.processEvents();chart.grab()
        path,info=chart.hover_regions[0];position=path.boundingRect().center();move(app,chart,position)
        assert chart._hover_text and chart.hover_info_at(position)['count']==3
        assert 'Frequency: 3' in chart._hover_text and 'Lower boundary: 0' in chart._hover_text
        move(app,chart,QPointF(2,2));assert chart._hover_text==''
        source=Worksheet(columns=[Column('Strength',values=[0.,.1,1.8,2.]),Column('Group','text',['A','A','B','B'])])
        r=build_histograms(source,[0],variant='groups',group_index=1,settings={'bins':2,'scale':'Density'})
        grouped=ChartWidget({'title':'Grouped density','result':r});widgets.append(grouped);grouped.resize(900,600);grouped.show();app.processEvents();grouped.grab()
        path,info=next((path,data) for path,data in grouped.hover_regions if data['series']=='A');move(app,grouped,path.boundingRect().center())
        assert info['measure']=='Density' and info['count']==2 and 'Density:' in grouped._hover_text
        scatter=ChartWidget({'title':'Scatter','result':{'graph':'scatter','xlabel':'Temp','ylabel':'Yield','series':[{'x':[1.,2.],'y':[3.,4.],'label':'A','connect':False,'fit':None,'row_indices':[5,9]}]}})
        widgets.append(scatter);scatter.resize(900,600);scatter.show();app.processEvents();scatter.grab()
        path,info=scatter.hover_regions[0];move(app,scatter,path.boundingRect().center());assert 'Row: 5' in scatter._hover_text and 'Temp: 1' in scatter._hover_text
        native=NativeOutputChart({'title':'Native saved','origin':'native','result':{'analysis':'native_saved_output','graphs':[
            {'title':'Saved histogram','panels':[{'kind':'histogram','x_label':'Residual','y_label':'Frequency','series':[{'kind':'histogram','x':[.5,2.5],'y':[3.,7.],'edges':[0.,1.,4.]}]}]},
            {'title':'Saved points','panels':[{'kind':'scatter','series':[{'kind':'scatter','x':[1.,2.],'y':[3.,4.]}]}]}]}})
        widgets.append(native);native.resize(900,600);native.show();app.processEvents();native.grab()
        path,info=native.hover_regions[-1];move(app,native,path.boundingRect().center());assert info['interval']==(1.,4.) and info['value']==7. and 'rows' not in info
        native.select_graph(1);assert native.hover_regions==[];app.processEvents();native.grab();assert all(info['kind']=='point' for _,info in native.hover_regions)
        composition=GraphCompositeWidget({'title':'Layout','result':build_layout([histogram_entry()],1,1)})
        widgets.append(composition);composition.resize(1000,700);composition.show();app.processEvents();composition.grab();child=composition.frames[0].chart
        assert not child.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        path,info=child.hover_regions[0];move(app,child,path.boundingRect().center());assert 'Frequency: 3' in child._hover_text
        frame=GraphFrame(chart,histogram_entry());widgets.append(frame);frame.resize(900,650);frame.show();app.processEvents();chart.grab()
        path,info=chart.hover_regions[0];move(app,chart,path.boundingRect().center());assert chart._hover_text
        assert not frame.capture().isNull() and chart._hover_text==''
    finally:
        from PySide6.QtWidgets import QToolTip
        QToolTip.hideText()
        for widget in reversed(widgets):widget.close();widget.deleteLater()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
