"""Source and frozen acceptance of worksheet-linked brushing and compositions."""
import copy
from pathlib import Path
from PySide6.QtCore import Qt,QEvent,QPointF,QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from .model import Worksheet,Column
from .compositions import appearance_from_entry


def verify_compositions(app,p,w,temp,checkpoint):
    checkpoint('interactive brushing, original rows and worksheet navigation')
    p.new();p.worksheet=Worksheet('Linked rows',[
        Column('Time',values=list(range(1,321))),
        Column('Response',values=[None if i==2 else i*2+(i%7) for i in range(1,321)]),
        Column('Batch','text',['A' if i%2 else 'B' for i in range(1,321)])])
    w.page=0;w.refresh();source=p.scatter_plot(0,1,'groups',2)
    p.update_graph_styles(source,{'p0:s0':{'color':'#aa2244'},'p0:s1':{'color':'#227744'}})
    w.show_result(source);app.processEvents();chart=w._active_chart_widget;chart.grab()
    before=copy.deepcopy(p.worksheet)
    w.brush_points_dialog(source);assert chart.is_brushing
    def mouse(kind,pos,ctrl=False):
        modifiers=Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
        event=QMouseEvent(kind,pos,QPointF(chart.mapToGlobal(pos.toPoint())),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,modifiers)
        QApplication.sendEvent(chart,event);app.processEvents()
    def click(row,ctrl=False):
        point=next(region.center() for linked,region in chart.brush_regions if linked==row)
        mouse(QEvent.Type.MouseButtonPress,point,ctrl);mouse(QEvent.Type.MouseButtonRelease,point,ctrl)
    click(1);assert 1 in w._brushed_rows and 2 not in w._brushed_rows
    click(320,True);assert {1,320}.issubset(set(w._brushed_rows))
    w._receive_brushed_rows(source,[1,320]);w.go_to_brushed_row(1)
    assert w.page==1
    w.go_to_brushed_row(-1);assert w.page==0
    assert p.worksheet==before
    chart.grab();points=[region.center() for row,region in chart.brush_regions]
    first=QPointF(min(point.x() for point in points)-1,min(point.y() for point in points)-1)
    last=QPointF(max(point.x() for point in points)+1,max(point.y() for point in points)+1)
    mouse(QEvent.Type.MouseButtonPress,first);mouse(QEvent.Type.MouseMove,last);mouse(QEvent.Type.MouseButtonRelease,last)
    assert len(w._brushed_rows)==319 and 2 not in w._brushed_rows
    brushed=set(chart.brushed_rows);assert not w._active_graph_frame.capture().isNull()
    assert chart.brushed_rows==brushed
    checkpoint('BY panels, shared scales and inherited group styles')
    def panel_dialog():
        dialog=QApplication.activeModalWidget();control=dialog.controls['by_index']
        control.setCurrentIndex(control.findData(2));dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,panel_dialog);w.panel_graph_dialog(source);app.processEvents()
    panels=p.history[-1];composite=w._active_chart_widget
    assert panels['result']['graph']=='panel_graph' and len(composite.frames)==2
    assert all(frame.chart.error is None for frame in composite.frames)
    assert composite.frames[0].chart.panel_annotation_limits==composite.frames[1].chart.panel_annotation_limits
    assert panels['result']['graphs'][0]['graph_styles']['p0:s0']['color']=='#aa2244'
    assert panels['result']['graphs'][1]['graph_styles']['p0:s0']['color']=='#227744'
    assert p.worksheet==before and not w._active_graph_frame.capture().isNull()
    checkpoint('ordered layout dialog, edit undo and MPX snapshots')
    other=p.expanded_graph('bar_chart',[2]);w.show_result(source)
    def layout_dialog():
        dialog=QApplication.activeModalWidget()
        for i in range(dialog.available.count()):dialog.available.item(i).setSelected(True)
        dialog.add_button.click();dialog.rows.setValue(1);dialog.columns.setValue(3)
        dialog.title.setText('Selected graphs');dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,layout_dialog);w.layout_tool_dialog(source);app.processEvents()
    layout=p.history[-1];assert layout['result']['graph']=='graph_layout'
    assert len(w._active_chart_widget.frames)==2 and layout['result']['columns']==3
    p.update_graph_layout(layout,[other,source],2,1,'Reordered');w.refresh();app.processEvents()
    assert w._active_chart_widget.entry['result']['rows']==2
    w.undo();app.processEvents();assert w._active_chart_widget.entry['result']['columns']==3
    w.redo();app.processEvents();assert w._active_chart_widget.entry['result']['columns']==1
    assert not w._active_graph_frame.capture().isNull()
    target=Path(temp)/'brushing-panels-layout.mpx';w.save_path(target);w.load_path(target)
    restored=next(e for e in p.history if e['result'].get('graph')=='graph_layout')
    w.show_result(restored);app.processEvents();assert len(w._active_chart_widget.frames)==2
    restored_panel=next(e for e in p.history if e['result'].get('graph')=='panel_graph')
    rerun=p.rerun_result(restored_panel);w.show_result(rerun);app.processEvents()
    assert len(w._active_chart_widget.frames)==2 and not w._active_graph_frame.capture().isNull()
