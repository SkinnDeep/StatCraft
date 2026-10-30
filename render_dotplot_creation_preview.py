"""Synthetic dotplot examples and full-image visual QA."""
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.dotplot_dialogs import DotplotDialog,DotplotTypeDialog
from statcraft.dotplot_graphs import VARIANTS
out=Path(__file__).resolve().parents[2]/'outputs'
values=[round(560+(i//12)*7+((i//6)%2)*3+((i%6)//2)*1.5,1) for i in range(24)]
p=Presenter();p.worksheet=Worksheet('Dotplot examples',[
 Column('Strength (N)',values=values),Column('Adjusted',values=[round(v+2+(i%3)*.5,1) for i,v in enumerate(values)]),
 Column('Batch','text',['A']*12+['B']*12),Column('Shift','text',(['Day']*6+['Night']*6)*2)]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(5,17)])
entries=[]
for variant in VARIANTS:entries.append(p.dotplot_graphs([0,1] if variant.startswith('multiple') else [0],variant,[2,3] if variant.endswith('groups') else [],intervals=12))
panels=p.dotplot_graphs([0,1],'multiple_stack_groups',[2,3],layout='panels',intervals=12,color_levels=[1])
app=QApplication([])
from statcraft.verification_fonts import load_verification_fonts
load_verification_fonts(app)
w=ModernWindow(p);w.show();w.show_result(entries[-1]);w.work_splitter.setSizes([640,240]);app.processEvents()
assert w._active_chart_widget.error is None
w.grab().save(str(out/'StatCraft-dotplot-variants-preview.png'));w._active_graph_frame.capture().save(str(out/'StatCraft-stacked-dotplots-export.png'))
gallery=DotplotTypeDialog(w);gallery.show();app.processEvents();gallery.grab().save(str(out/'StatCraft-dotplot-type-chooser.png'));gallery.close();gallery.deleteLater()
dialog=DotplotDialog(w,p.worksheet,parameters=entries[-1]['recipe']['parameters']);dialog.show();app.processEvents();dialog.grab().save(str(out/'StatCraft-dotplot-variable-dialog.png'));dialog.close();dialog.deleteLater()
w.show_result(entries[4]);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-dotplot-stack-y-export.png'))
w.show_result(panels);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-dotplot-panels-export.png'))
layout=p.graph_layout([entries[1],entries[2]],1,2);w.show_result(layout);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-dotplot-layout-export.png'))
w.save_path(out/'StatCraft-dotplot-variants-demo.mpx');p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
