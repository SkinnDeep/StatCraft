"""Source/frozen acceptance of all dotplot variants and editable source recipes."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QTableWidgetItem
from .model import Column,Worksheet
from .dotplot_graphs import VARIANTS
from .brushing import brushable_rows


def verify_dotplot_creation(app,p,w,temp,checkpoint):
    checkpoint('dotplot gallery, stacked groups, named roles, Data View and Scale')
    p.new();p.worksheet=Worksheet('Dotplot samples',[
        Column('Strength',values=[1,1,2,2,3,3,4,4,5,5,6,6]),Column('Adjusted',values=[2,2,3,3,4,4,5,5,6,6,7,7]),
        Column('Batch','text',['A']*6+['B']*6),Column('Shift','text',['Day']*3+['Night']*3+['Day']*3+['Night']*3)])
    w.page=0;w._show_welcome();w.refresh()
    def configure():
        d=QApplication.activeModalWidget();d.variables.setText('C1 C2');d.group.setText('C3 C4');d.scale_order.setCurrentIndex(1)
        def view():
            child=QApplication.activeModalWidget();child.controls[0].setChecked(False);child.accept()
        QTimer.singleShot(0,view);d.edit_data_view()
        def scale():
            child=QApplication.activeModalWidget();child.intervals.setValue(3);child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        QTimer.singleShot(0,scale);d.edit_scale();d.labels['title']='Stacked dots by shift';d.validate()
    def choose():
        d=QApplication.activeModalWidget();assert len(d.mode_buttons)==7;d.mode_buttons['multiple_stack_groups'].click();QTimer.singleShot(0,configure);d.accept()
    QTimer.singleShot(0,choose);w.graph_actions['dotplot'].trigger();app.processEvents()
    e=p.history[-1];assert e['recipe']['action']=='dotplot_graphs';chart=w._active_chart_widget;image=chart.grab()
    assert chart.error is None and not image.isNull() and len(chart.panels[0]['lanes'])==4
    assert e['recipe']['parameters']['color_levels']==[1] and e['recipe']['parameters']['intervals']==3
    assert len(chart.brush_regions)==24 and brushable_rows(e)==list(range(1,13))
    chart.set_brushing(True);assert chart.is_brushing;chart.set_brushing(False)
    assert 'p0:s7' in {obj['target'] for obj in chart.editable_objects()}
    p.update_graph_styles(e,{'p0:s0':{'fill':'#d000a4','edge':'#d000a4','marker':'square','marker_size':10}});w.refresh();app.processEvents()
    image=chart.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    assert bytes((208,0,164,255)) in bytes(image.bits())
    capture=w._active_graph_frame.capture();assert capture.height()/capture.devicePixelRatio()>=chart.height()
    checkpoint('dotplot variants, MPX column binding, Make Similar and layouts')
    for variant in VARIANTS:
        entry=p.dotplot_graphs([0,1] if variant.startswith('multiple') else [0],variant,[2,3] if variant.endswith('groups') else [],intervals=3)
        w.show_result(entry);app.processEvents();w._active_chart_widget.grab();assert w._active_chart_widget.error is None,variant
    p.insert_columns(0);w.refresh();assert e['recipe']['parameters']['group_indices']==[3,4] and not p.result_stale(e)
    path=Path(temp)/'dotplot-variants.mpx';w.save_path(path);w.load_path(path);saved=p.history[0]
    rerun=p.rerun_result(saved);w.show_result(rerun);app.processEvents();assert w._active_chart_widget.error is None
    def similar():
        d=QApplication.activeModalWidget();assert d.roles.rowCount()==4;d.roles.setItem(0,2,QTableWidgetItem('C3'));d.roles.setItem(1,2,QTableWidgetItem('C2'));d.validate()
    QTimer.singleShot(0,similar);w.make_similar_graph(saved);app.processEvents()
    assert p.history[-1]['recipe']['parameters']['response_indices']==[2,1]
    separate=p.dotplot_graphs([1,2],'multiple_groups',[3],layout='panels');w.show_result(separate);app.processEvents();assert len(w._active_chart_widget.panels)==2
    layout=p.graph_layout([saved,separate],1,2);w.show_result(layout);app.processEvents()
    assert all(frame.chart.error is None for frame in w._active_chart_widget.frames);assert not w._active_graph_frame.capture().isNull()
