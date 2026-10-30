"""Original synthetic builder workbook and live-workspace visual verification."""
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts
from statcraft.graph_builder_dialog import GraphBuilderDialog
from statcraft.graph_builder import TYPES
out=Path(__file__).resolve().parents[2]/'outputs'
p=Presenter();values=[round(560+(i//12)*8+((i%6)-2.5)*1.3,2) for i in range(24)]
p.worksheet=Worksheet('Builder examples',[Column('Time',values=list(range(1,25))),Column('Strength (N)',values=values),Column('Adjusted',values=[round(v+2+(i%3)*.4,2) for i,v in enumerate(values)]),Column('Batch','text',['A']*12+['B']*12)]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(5,17)])
entries=[]
for kind in TYPES:
 entries.append(p.graph_builder(kind,[3] if kind=='bar_chart' else [1,2] if kind=='matrix_plot' else [1],0 if kind in ('scatter','time_series') else None,[] if kind in ('matrix_plot','bar_chart') else [3],{'fit':kind in ('scatter','histogram'),'bins':8}))
app=QApplication([]);load_verification_fonts(app);w=ModernWindow(p);w.show();w.show_result(entries[0]);app.processEvents()
d=GraphBuilderDialog(w,p.worksheet,parameters=entries[0]['recipe']['parameters']);d.show();app.processEvents();assert d.update_preview();d.grab().save(str(out/'StatCraft-graph-builder-workspace.png'));d.preview_frame.capture().save(str(out/'StatCraft-graph-builder-preview-export.png'));d.close();d.deleteLater()
w.grab().save(str(out/'StatCraft-graph-builder-result.png'))
p.graph_layout([entries[0],entries[1]],1,2);w.save_path(out/'StatCraft-graph-builder-demo.mpx');p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
