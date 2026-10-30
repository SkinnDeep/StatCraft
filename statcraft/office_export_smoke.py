"""Packaged Office export acceptance without installed Word or PowerPoint."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from xml.etree import ElementTree as ET
from .model import Worksheet, Column
from .office_export import png_size


def verify_office_export(app,p,w,temp,checkpoint):
    checkpoint('Native DOCX/PPTX exports, clicked output, full graph frame, cancel and report text')
    p.new();p.worksheet=Worksheet('Export samples',[Column('Run',values=list(range(1,13))),Column('Strength',values=[12,14,13,15,17,16,19,21,18,23,22,24])])
    w.page=0;w._show_welcome();w.refresh()
    graph=p.graph_builder('scatter',[1],0,options={'title':'Strength versus run'})
    report=p.describe_columns([1]);w.show_result(report);app.processEvents()
    history=len(p.history);dirty=p.dirty
    for kind,suffix,method,member in [('Word','.docx',w.send_output_to_word,'word/document.xml'),('PowerPoint','.pptx',w.send_output_to_powerpoint,'ppt/presentation.xml')]:
        path=Path(temp)/('clicked-output'+suffix)
        with patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=(str(path),'Preferred')):method(graph)
        assert w.selected_entry is graph and path.exists()
        with ZipFile(path) as z:
            ET.fromstring(z.read(member))
            image=z.read('word/media/graph.png' if kind=='Word' else 'ppt/media/graph.png')
            assert png_size(image)==(w._active_graph_frame.capture().width(),w._active_graph_frame.capture().height())
            text=''.join(z.read(name).decode('utf-8') for name in z.namelist() if name.endswith('.xml'))
            assert 'Strength versus run' in text and 'Strength' in text
        with patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=('', '')):method(graph)
        assert p.dirty==dirty and len(p.history)==history
    other=p.graph_builder('histogram',[1])
    layout=p.graph_layout([graph,other],1,2);w.show_result(layout);app.processEvents()
    snapshot=w._office_snapshot(layout)
    assert png_size(snapshot.png)[0]>=w._active_graph_frame.minimumWidth()
    w.show_result(report);app.processEvents();snapshot=w._office_snapshot(report);assert not snapshot.png
    path=Path(temp)/'text-only.docx'
    with patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=(str(path),'Word')):w.send_output_to_word(report)
    with ZipFile(path) as z:assert 'word/media/graph.png' not in z.namelist()
