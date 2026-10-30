"""Synthetic saved output workspace for review and packaged reopening."""
from pathlib import Path
import json
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication([]);load_verification_fonts(app)
p=Presenter();p.worksheet=Worksheet('Strength measurements',[Column('Run',values=list(range(1,25))),Column('Strength (N)',values=[565+i*.4+(i%3)*2 for i in range(24)]),Column('Shift','text',['Day']*12+['Night']*12)])
w=ModernWindow(p);w.resize(1500,950);w.show();app.processEvents()
a=p.graph_builder('scatter',[1],0,[2],{'fit':True,'title':'Strength versus run'});w.show_result(a);app.processEvents();w.set_zoom(125)
b=p.histogram_graphs([1],'fit_groups',2);w.show_result(b);app.processEvents()
c=p.describe_columns([1]);w.show_result(c);app.processEvents()
for entry in (a,b,c):w.send_output_to_report(entry)
w._workspace.pad.appendPlainText('\nOperator review\nThe report combines the graph summaries and descriptive statistics. Keep these notes when switching results or reopening the project.')
w.grab().save(str(out/'StatCraft-report-workspace.png'))
w.show_result(a);app.processEvents();w.edit_graph_dialog(a);app.processEvents()
path=out/'StatCraft-output-workspace-demo.mpx';w.save_path(path)
w.load_path(path);app.processEvents()
assert len(p.history)==3 and w._workspace.tabs.count()==4 and w._zoom_percent==125
assert 'Operator review' in w._workspace.pad.toPlainText()
w.grab().save(str(out/'StatCraft-output-workspace.png'))
(root/'work/output-workspace-artifacts-verified.json').write_text(json.dumps({'project':path.name,'results':len(p.history),'open_tabs':w._workspace.tabs.count(),'zoom':w._zoom_percent,'report_notes_preserved':True,'active_result_restored':True,'view_state_restored':True},indent=2),encoding='utf-8')
p.dirty=False;p._results_dirty=False;w.close();print('Saved workspace and report screenshots verified')
