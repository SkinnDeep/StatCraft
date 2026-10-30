"""Source/frozen acceptance of result-document and persistent report workflows."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from .model import Worksheet,Column
from .workspace_state import REPORT,MEMBER


def verify_output_workspace(app,p,w,temp,checkpoint):
    checkpoint('Output-document tabs, close/reopen/reorder, report editing and MPX restoration')
    p.new();p.worksheet=Worksheet('Workspace measurements',[Column('Run',values=list(range(1,9))),Column('Strength',values=[12,15,13,18,17,20,22,21])])
    w.page=0;w._show_welcome();w.refresh();ws=w._workspace
    a=p.scatter_plot(0,1);w.show_result(a);app.processEvents();w.set_zoom(150)
    b=p.histogram_graphs([1]);w.show_result(b);app.processEvents()
    assert ws.tabs.count()==2 and not w.result_tabs.tabBar().isVisible()
    ws.close_current();assert len(p.history)==2 and ws.tabs.count()==1 and w.selected_entry is a
    ws.reopen();assert w.selected_entry is b and ws.tabs.count()==2
    before=list(ws.state['open_ids'])
    with patch.object(w.graph_options_pane,'flush',return_value=False):ws.close_current()
    assert ws.state['open_ids']==before
    ws.tabs.moveTab(0,1);assert ws.state['open_ids']==before[::-1]
    w.show_result(a);app.processEvents();assert w._zoom_percent==150
    w.send_output_to_report(a);ws.pad.appendPlainText('Operator review: keep this result. Ω <literal>')
    w.set_zoom(125);assert ws.state['active']==REPORT and p.dirty
    snapshot=w._office_snapshot();assert not snapshot.png and 'Operator review:' in snapshot.report
    job=w._printing().snapshot(kind='ReportPad');assert 'Operator review:' in job.documents[0]
    w.show_result(b);ws.show_pad();assert 'Operator review:' in ws.pad.toPlainText()
    path=Path(temp)/'output-workspace.mpx';w.save_path(path);w.load_path(path);app.processEvents()
    assert ws.state['active']==REPORT and w._zoom_percent==125 and 'Operator review:' in ws.pad.toPlainText()
    assert ws.tabs.count()==3 and len(p.history)==2
    with ZipFile(path) as z:assert MEMBER in z.namelist()
    ws.close_all();assert len(p.history)==2 and ws.tabs.count()==0
    w.show_result(p.history[0]);app.processEvents();assert w._zoom_percent==150
    text=ws.pad.toPlainText();ws.append(p.history[0]);ws.pad.undo();assert ws.pad.toPlainText()==text
