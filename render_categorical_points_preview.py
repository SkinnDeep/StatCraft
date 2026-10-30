"""Synthetic individual-value/interval examples and visual QA."""
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts
from statcraft.categorical_points_dialogs import CategoricalPlotDialog,CategoricalTypeDialog
out=Path(__file__).resolve().parents[2]/'outputs'
values=[round(560+(i//12)*8+((i//6)%2)*4+((i%6)-2.5)*1.3,2) for i in range(24)]
p=Presenter();p.worksheet=Worksheet('Individual and interval examples',[
 Column('Strength (N)',values=values),Column('Adjusted',values=[round(v+2+(i%3)*.4,2) for i,v in enumerate(values)]),
 Column('Batch','text',['A']*12+['B']*12),Column('Shift','text',(['Day']*6+['Night']*6)*2)]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(5,17)])
entries=[]
for family in ('individual','interval'):
 for variant in ('one','one_groups','multiple','multiple_groups'):
  entries.append(p.categorical_points([0,1] if variant.startswith('multiple') else [0],family,variant,[2,3] if variant.endswith('groups') else []))
combined=p.categorical_points([0,1],'interval','multiple_groups',[2,3],variable_position='inner',display={'individual':True,'mean_connect':True},interval_options={'pooled':True,'bonferroni':True})
panels=p.categorical_points([0,1],'interval','multiple_groups',[2],layout='panels',interval_options={'method':'standard_error','multiple':2})
upper=p.categorical_points([0],'interval','one_groups',[2],interval_options={'side':'upper'})
app=QApplication([]);load_verification_fonts(app);w=ModernWindow(p);w.show();w.show_result(combined);w.work_splitter.setSizes([640,240]);app.processEvents()
assert w._active_chart_widget.error is None
w.grab().save(str(out/'StatCraft-individual-interval-preview.png'));w._active_graph_frame.capture().save(str(out/'StatCraft-interval-groups-export.png'))
for family in ('individual','interval'):
 gallery=CategoricalTypeDialog(family,w);gallery.show();app.processEvents();gallery.grab().save(str(out/('StatCraft-'+family+'-type-chooser.png')));gallery.close();gallery.deleteLater()
dialog=CategoricalPlotDialog(w,p.worksheet,parameters=combined['recipe']['parameters']);dialog.show();app.processEvents();dialog.grab().save(str(out/'StatCraft-individual-interval-variable-dialog.png'));dialog.close();dialog.deleteLater()
w.show_result(entries[3]);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-individual-groups-export.png'))
w.show_result(panels);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-interval-panels-export.png'))
w.show_result(upper);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-interval-upper-bound-export.png'))
layout=p.graph_layout([entries[1],entries[5]],1,2);w.show_result(layout);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-individual-interval-layout-export.png'))
w.save_path(out/'StatCraft-individual-interval-demo.mpx');p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
