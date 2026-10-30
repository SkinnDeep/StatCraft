"""Source/frozen acceptance of categorical boxplots and their editable recipes."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QTableWidgetItem
from .model import Column,Worksheet


def verify_boxplot_creation(app,p,w,temp,checkpoint):
    checkpoint('boxplot gallery, categorical roles, inner scale and data display')
    p.new();p.worksheet=Worksheet('Grouped measurements',[
        Column('Strength',values=[1,2,4,5,7,8,3,4,6,9,10,12]),
        Column('Adjusted',values=[2,4,5,7,8,9,4,6,9,11,12,15]),
        Column('Batch','text',['A']*6+['B']*6),Column('Shift','text',['Day']*3+['Night']*3+['Day']*3+['Night']*3)])
    w.page=0;w._show_welcome();w.refresh()
    def configure():
        dialog=QApplication.activeModalWidget();dialog.variables.setText('C1 C2');dialog.group.setText('C3 C4');dialog.scale_order.setCurrentIndex(1)
        def data_view():
            child=QApplication.activeModalWidget();child.controls['mean_symbol'].setChecked(True);child.controls['individual'].setChecked(True);child.controls['mean_connect'].setChecked(True);child.accept()
        QTimer.singleShot(0,data_view);dialog.edit_data_view()
        dialog.labels['title']='Strength by batch and shift';dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    def choose():
        dialog=QApplication.activeModalWidget();assert len(dialog.mode_buttons)==4
        dialog.mode_buttons['multiple_groups'].click();QTimer.singleShot(0,configure);dialog.accept()
    QTimer.singleShot(0,choose);w.graph('boxplot');app.processEvents()
    entry=p.history[-1];assert entry['recipe']['action']=='boxplot_graphs'
    chart=w._active_chart_widget;chart.grab();assert chart.error is None
    items=chart.panels[0]['items'];assert len(items)==8 and [item['response_index'] for item in items]==[0,1,0,1,0,1,0,1]
    assert chart.panels[0]['display']['individual'] and chart.panels[0]['display']['mean_connect']
    assert {'p0:s0','p0:s7','p0:ref1','p0:axis'}.issubset({obj['target'] for obj in chart.editable_objects()})
    p.update_graph_styles(entry,{'p0:s0':{'fill':'#d000a4','opacity':1}});w.refresh();app.processEvents()
    image=chart.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    assert bytes((208,0,164,255)) in bytes(image.bits())
    capture=w._active_graph_frame.capture();assert capture.height()/capture.devicePixelRatio()>=chart.height() and capture.width()/capture.devicePixelRatio()>=chart.width()
    checkpoint('boxplot column binding, MPX reopen, similar roles and complete layout export')
    p.insert_columns(0);w.refresh();assert entry['recipe']['parameters']['group_indices']==[3,4] and not p.result_stale(entry)
    path=Path(temp)/'boxplot-variants.mpx';w.save_path(path);w.load_path(path)
    saved=p.history[0];rerun=p.rerun_result(saved);w.show_result(rerun);app.processEvents();assert w._active_chart_widget.error is None
    def similar():
        dialog=QApplication.activeModalWidget();assert dialog.roles.rowCount()==4
        dialog.roles.setItem(0,2,QTableWidgetItem('C3'));dialog.roles.setItem(1,2,QTableWidgetItem('C2'))
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,similar);w.make_similar_graph(saved);app.processEvents();copied=p.history[-1]
    assert copied['recipe']['parameters']['response_indices']==[2,1] and w._active_chart_widget.error is None
    separate=p.boxplot_graphs([1,2],'multiple_groups',[3],layout='panels',display={'median_symbol':True})
    w.show_result(separate);app.processEvents();assert len(w._active_chart_widget.panels)==2 and w._active_chart_widget.error is None
    layout=p.graph_layout([saved,separate],1,2);w.show_result(layout);app.processEvents()
    chart=w._active_chart_widget;assert len(chart.frames)==2 and all(frame.chart.error is None for frame in chart.frames)
    capture=w._active_graph_frame.capture();assert capture.width()/capture.devicePixelRatio()>=chart.width()
