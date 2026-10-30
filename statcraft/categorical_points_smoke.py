"""Source/frozen GUI acceptance for the two categorical point/interval families."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QTableWidgetItem
from .model import Column,Worksheet
from .boxplot_graphs import VARIANTS


def verify_categorical_points(app,p,w,temp,checkpoint):
    checkpoint('individual/interval galleries, grouped variable roles and Data View')
    p.new();p.worksheet=Worksheet('Categorical measurements',[
        Column('Strength',values=[1,2,3,3,4,5,5,6,7,7,8,9]),Column('Adjusted',values=[2,4,6,4,6,8,6,8,10,8,10,12]),
        Column('Batch','text',['A']*6+['B']*6),Column('Shift','text',['Day']*3+['Night']*3+['Day']*3+['Night']*3)])
    w.page=0;w._show_welcome();w.refresh()
    def configure():
        d=QApplication.activeModalWidget();d.variables.setText('C1 C2');d.group.setText('C3 C4');d.scale_order.setCurrentIndex(1)
        def view():
            child=QApplication.activeModalWidget();child.controls['interval'].setChecked(True);child.controls['individual'].setChecked(True);child.controls['mean_symbol'].setChecked(True);child.controls['median_symbol'].setChecked(True);child.controls['mean_connect'].setChecked(True)
            def options():
                interval=QApplication.activeModalWidget();interval.pooled.setChecked(True);interval.bonferroni.setChecked(True);interval.confidence.setValue(90);interval.validate()
            QTimer.singleShot(0,options);d.edit_interval();child.accept()
        QTimer.singleShot(0,view);d.edit_data_view();d.validate()
    def choose():
        d=QApplication.activeModalWidget();assert len(d.mode_buttons)==4;d.mode_buttons['multiple_groups'].click();QTimer.singleShot(0,configure);d.accept()
    QTimer.singleShot(0,choose);w.graph_actions['individual_value'].trigger();app.processEvents();e=p.history[-1];chart=w._active_chart_widget;chart.grab()
    assert chart.error is None and e['recipe']['action']=='categorical_points' and e['recipe']['parameters']['plot_type']=='individual'
    assert len(chart.panels[0]['items'])==8 and len(chart.brush_regions)==24
    assert {'p0:s0','p0:mean0','p0:median0','p0:int0','p0:ref1'}.issubset({obj['target'] for obj in chart.editable_objects()})
    assert e['recipe']['parameters']['interval_options']['confidence']==.9 and e['recipe']['parameters']['interval_options']['bonferroni']
    chart.set_brushing(True);assert chart.is_brushing;chart.set_brushing(False)
    p.update_graph_styles(e,{'p0:int0':{'color':'#d000a4','line_width':4},'p0:s0':{'fill':'#d000a4','edge':'#d000a4','marker_size':10}});w.refresh();app.processEvents()
    image=chart.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888);assert bytes((208,0,164,255)) in bytes(image.bits())
    capture=w._active_graph_frame.capture();assert capture.width()/capture.devicePixelRatio()>=chart.width() and capture.height()/capture.devicePixelRatio()>=chart.height()
    checkpoint('eight categorical variants, one-sided intervals, MPX binding and similar roles')
    for family in ('individual','interval'):
        for variant in VARIANTS:
            result=p.categorical_points([0,1] if variant.startswith('multiple') else [0],family,variant,[2,3] if variant.endswith('groups') else [])
            w.show_result(result);app.processEvents();w._active_chart_widget.grab();assert w._active_chart_widget.error is None,(family,variant)
    for side in ('upper','lower'):
        bounds=p.categorical_points([0],plot_type='interval',interval_options={'side':side});w.show_result(bounds);app.processEvents();w._active_chart_widget.grab();assert w._active_chart_widget.error is None
    p.insert_columns(0);w.refresh();assert e['recipe']['parameters']['group_indices']==[3,4] and not p.result_stale(e)
    path=Path(temp)/'individual-interval.mpx';w.save_path(path);w.load_path(path);saved=p.history[0]
    rerun=p.rerun_result(saved);w.show_result(rerun);app.processEvents();assert w._active_chart_widget.error is None
    def similar():
        d=QApplication.activeModalWidget();assert d.roles.rowCount()==4;d.roles.setItem(0,2,QTableWidgetItem('C3'));d.roles.setItem(1,2,QTableWidgetItem('C2'));d.validate()
    QTimer.singleShot(0,similar);w.make_similar_graph(saved);app.processEvents();assert p.history[-1]['recipe']['parameters']['response_indices']==[2,1]
    panel=p.categorical_points([1,2],plot_type='interval',variant='multiple_groups',group_indices=[3],layout='panels',interval_options={'method':'standard_error','multiple':2})
    w.show_result(panel);app.processEvents();assert len(w._active_chart_widget.panels)==2
    layout=p.graph_layout([saved,panel],1,2);w.show_result(layout);app.processEvents();assert all(frame.chart.error is None for frame in w._active_chart_widget.frames)
    assert not w._active_graph_frame.capture().isNull()
