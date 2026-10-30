from pathlib import Path
from statistics import NormalDist
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.recipes import run

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]);p=Presenter()
strength=[round(570+5.5*NormalDist().inv_cdf((i+.5)/120),2) for i in range(120)]
p.worksheet=Worksheet('Worksheet 1',[Column('Test No.',values=list(range(1,121))),
    Column('Strength (N)',values=strength),Column('Result','text',['PASS']*120)]+
    [Column('C'+str(i),metadata={'auto_type':True}) for i in range(4,17)])
entry=run(p,{'action':'graph','parameters':{'method':'histogram','indices':[1],'bins':12}})
w=ModernWindow(p);w.show();w.show_result(entry);w.edit_graph_dialog(entry)
pane=w.graph_options_pane
for key,value in (('subtitle','Production sample'),('footnote','Synthetic demonstration data')):
    pane.controls[key].setText(value);pane.controls[key].textEdited.emit(value)
pane.flush();w.work_splitter.setSizes([570,270]);w.table.setColumnWidth(1,95)
app.processEvents();w.save_path(out/'StatCraft-graph-options-demo.mpx')
w.grab().save(str(out/'StatCraft-graph-options-pane.png'))
assert w._active_chart_widget.error is None
w._active_graph_frame.capture().save(str(out/'StatCraft-edited-histogram.png'))
p.dirty=False;p._results_dirty=False;w.close()
w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
