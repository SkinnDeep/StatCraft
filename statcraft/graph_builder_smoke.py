"""Source/frozen acceptance of the original live Graph Builder workspace."""
from pathlib import Path
import json
from PySide6.QtCore import Qt,QTimer,QMimeData,QPoint,QPointF
from PySide6.QtGui import QDragEnterEvent,QDropEvent
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from .model import Worksheet,Column
from .graph_builder_dialog import MIME
from .graph_builder import TYPES


def verify_graph_builder(app,p,w,temp,checkpoint):
    checkpoint('Graph Builder named drops, isolated live previews, cancel and Create')
    p.new();p.worksheet=Worksheet('Builder measurements',[
        Column('Time',values=list(range(1,13))),Column('Strength',values=[1,2,3,3,4,5,5,6,7,7,8,9]),
        Column('Adjusted',values=[2,4,6,4,6,8,6,8,10,8,10,12]),Column('Batch','text',['A']*6+['B']*6)])
    w.page=0;w._show_welcome();w.refresh();before=len(p.history);dirty=p.dirty
    def cancel():
        d=QApplication.activeModalWidget()
        for kind in TYPES:
            d.clear_mappings();d.set_graph_type(kind);d.assign_columns('response_indices',[3] if kind=='bar_chart' else [1,2] if kind=='matrix_plot' else [1])
            if kind in ('scatter','time_series'):d.assign_columns('x_index',[0])
            assert d.update_preview() and d.preview_chart.error is None,kind
            assert not d.preview_frame.capture().isNull()
        assert len(p.history)==before and p.dirty==dirty;d.reject()
    QTimer.singleShot(0,cancel);w.graph_actions['builder'].trigger();app.processEvents();assert len(p.history)==before
    def create():
        d=QApplication.activeModalWidget();d.set_graph_type('scatter');role=d.roles['response_indices'];mime=QMimeData();mime.setData(MIME,json.dumps([1]).encode())
        enter=QDragEnterEvent(QPoint(10,10),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier);QApplication.sendEvent(role.viewport(),enter)
        drop=QDropEvent(QPointF(10,10),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier);QApplication.sendEvent(role.viewport(),drop)
        assert d.mapping['response_indices']==[1];d.assign_columns('x_index',[0]);d.assign_columns('group_indices',[3]);d.fit.setChecked(True);d.title.setText('Strength versus time')
        assert d.update_preview() and d.preview_chart.error is None and len(p.history)==before
        assert not d.preview_frame.capture().isNull();d.validate()
    QTimer.singleShot(0,create);w.graph_actions['builder'].trigger();app.processEvents();assert len(p.history)==before+1
    e=p.history[-1];assert e['recipe']['action']=='graph_builder' and e['result']['scatter_mode']=='regression_groups'
    chart=w._active_chart_widget;chart.grab();assert chart.error is None and len(chart.brush_regions)==12;chart.set_brushing(True);chart.set_brushing(False)
    p.update_graph_styles(e,{'p0:s0':{'fill':'#d000a4','marker':'diamond'}});w.refresh();app.processEvents()
    checkpoint('Graph Builder MPX source identity, rerun, similar options and layout')
    p.insert_columns(0);w.refresh();assert e['recipe']['parameters']['x_index']==1 and e['recipe']['parameters']['response_indices']==[2] and not p.result_stale(e)
    path=Path(temp)/'graph-builder.mpx';w.save_path(path);w.load_path(path);saved=p.history[0]
    rerun=p.rerun_result(saved);w.show_result(rerun);app.processEvents();assert w._active_chart_widget.error is None
    def similar():
        d=QApplication.activeModalWidget();assert d.roles.rowCount()==3;d.roles.setItem(0,2,QTableWidgetItem('C4'))
        def options():
            child=QApplication.activeModalWidget();assert not child.gallery.isEnabled();child.fit.setChecked(False);child.validate()
        QTimer.singleShot(0,options);d.edit_options();d.validate()
    QTimer.singleShot(0,similar);w.make_similar_graph(saved);app.processEvents();copy=p.history[-1]
    assert copy['recipe']['parameters']['response_indices']==[3] and not copy['recipe']['parameters']['options']['fit']
    assert copy['result']['scatter_mode']=='groups'
    layout=p.graph_layout([saved,copy],1,2);w.show_result(layout);app.processEvents();assert all(frame.chart.error is None for frame in w._active_chart_widget.frames)
    assert not w._active_graph_frame.capture().isNull()
