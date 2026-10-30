"""Output zoom preserves worksheet geometry, edit targets and graph captures."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from PySide6.QtCore import QEvent,Qt,QPointF,QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from .model import Worksheet,Column
from .graph_presentation import graph_presentation


def verify_startup_zoom(app,p,w,temp,checkpoint):
    checkpoint('Output zoom, preserved worksheet widths, object events and real heatmap Office exports')
    p.new();p.worksheet=Worksheet('Zoom measurements',[Column('Run',values=[1,2,3,4,5,6]),Column('Strength',values=[12,15,13,18,17,20])])
    w.page=0;w._show_welcome();w.refresh();w.table.setColumnWidth(0,183)
    w.set_zoom(150);w.set_zoom(100);assert w.table.columnWidth(0)==183
    graph=p.graph_builder('scatter',[1],0,options={'title':'Strength over run'})
    w.show_result(graph);app.processEvents();assert graph_presentation(graph)['title']=='Strength over run'
    widths=[w.table.columnWidth(i) for i in range(w.table.columnCount())]
    frame=w._active_graph_frame;before=frame.capture().toImage();dirty=p.dirty;count=len(p.history)
    for percent in (50,75,150,200,500,100):
        w.set_zoom(percent);app.processEvents()
        assert w.result_tabs.currentWidget().transform().m11()==percent/100
        assert [w.table.columnWidth(i) for i in range(w.table.columnCount())]==widths
        assert frame.capture().size()==before.size()
    w.set_zoom(150);w.show_result(graph);app.processEvents();assert w._zoom_percent==150
    w.fit_output_window();assert w.result_tabs.currentWidget().fit_mode
    assert p.dirty==dirty and len(p.history)==count
    report=p.describe_columns([1]);w.show_result(report);app.processEvents();w.set_zoom(125)
    assert w.result_tabs.currentWidget().transform().m11()==1.25
    heat=p.expanded_graph('heatmap',[1]);w.show_result(heat);app.processEvents()
    for suffix,method,member in [('.docx',w.send_output_to_word,'word/media/graph.png'),('.pptx',w.send_output_to_powerpoint,'ppt/media/graph.png')]:
        path=Path(temp)/('heatmap'+suffix)
        with patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=(str(path),'')):method(heat)
        with ZipFile(path) as z:
            assert z.read(member).startswith(b'\x89PNG')
            xml=''.join(z.read(name).decode('utf-8') for name in z.namelist() if name.endswith('.xml'))
            assert 'Rows: 6' in xml and 'native-product' not in xml and 'values=[[' not in xml
