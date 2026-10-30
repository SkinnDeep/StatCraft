"""Actual chooser, named roles, styles, MPX and similar-graph acceptance."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QTableWidgetItem
from .model import Worksheet,Column


def verify_histogram_creation(app,p,w,temp,checkpoint):
    checkpoint('histogram variant gallery, named responses and grouped fit overlays')
    p.new();p.worksheet=Worksheet('Histogram groups',[
        Column('Strength (N)',values=[1,2,4,5,7,8,3,4,6,9,10,12]),
        Column('Adjusted strength',values=[2,4,5,7,8,9,4,6,9,11,12,15]),
        Column('Batch name','text',['A']*6+['B']*6)])
    w.page=0;w._show_welcome();w.refresh()
    def configure():
        dialog=QApplication.activeModalWidget();assert dialog.mode=='fit_groups'
        dialog.variables.setText('C1 C2');dialog.group.setText('C3')
        dialog.histogram_settings.update(bins=6,scale='Percent')
        dialog.labels['title']='Strength distributions by batch'
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    def choose():
        chooser=QApplication.activeModalWidget();assert len(chooser.mode_buttons)==4
        chooser.mode_buttons['fit_groups'].click();QTimer.singleShot(0,configure);chooser.accept()
    QTimer.singleShot(0,choose);w.graph('histogram');app.processEvents()
    entry=p.history[-1];assert entry['recipe']['action']=='histogram_graphs'
    chart=w._active_chart_widget;chart.grab();assert chart.error is None and len(chart.panels)==2
    for panel in chart.panels:
        assert len(panel['series'])==2
        assert all(abs(sum(series['counts'])-100)<1e-8 and len(series['curves'])==1 for series in panel['series'])
    targets={item['target'] for item in chart.editable_objects()};assert {'p0:s0','p0:s1','p0:fit0','p0:axis'}.issubset(targets)
    p.update_graph_styles(entry,{'p0:s1':{'fill':'#d000a4','opacity':1}});w.refresh();app.processEvents()
    image=chart.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    assert bytes((208,0,164,255)) in bytes(image.bits())
    assert w._active_graph_frame.title_label.text()=='Strength distributions by batch'
    capture=w._active_graph_frame.capture();assert not capture.isNull()
    assert capture.height()/capture.devicePixelRatio()>=chart.height()
    checkpoint('histogram tracked MPX, column identity, similar mapping and panels')
    p.insert_columns(0);w.refresh();assert entry['recipe']['parameters']['response_indices']==[1,2]
    assert not p.result_stale(entry)
    path=Path(temp)/'histogram-variants.mpx';w.save_path(path);w.load_path(path)
    saved=next(e for e in p.history if e['recipe']['action']=='histogram_graphs')
    rerun=p.rerun_result(saved);w.show_result(rerun);app.processEvents();assert w._active_chart_widget.error is None
    def similar():
        dialog=QApplication.activeModalWidget();assert dialog.roles.rowCount()==3
        dialog.roles.setItem(0,2,QTableWidgetItem('C3'))
        dialog.roles.setItem(1,2,QTableWidgetItem('C2'))
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,similar);w.make_similar_graph(saved);app.processEvents()
    assert p.history[-1]['recipe']['parameters']['response_indices']==[2,1]
    assert w._active_chart_widget.error is None
    def panels():
        dialog=QApplication.activeModalWidget();dialog.variables.setText('C2');dialog.group.setText('C4')
        dialog.arrangement.setCurrentIndex(dialog.arrangement.findData('panels'))
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    def panel_type():
        dialog=QApplication.activeModalWidget();dialog.mode_buttons['groups'].click()
        QTimer.singleShot(0,panels);dialog.accept()
    QTimer.singleShot(0,panel_type);w.graph('histogram');app.processEvents()
    assert len(w._active_chart_widget.panels)==2 and w._active_chart_widget.error is None
    assert [panel['series'][0]['color_index'] for panel in w._active_chart_widget.panels]==[0,1]
    layout=p.graph_layout([saved,p.history[-1]],1,2);w.show_result(layout);app.processEvents()
    assert len(w._active_chart_widget.frames)==2 and not w._active_graph_frame.capture().isNull()
