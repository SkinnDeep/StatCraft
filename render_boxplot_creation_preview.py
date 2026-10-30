"""Synthetic boxplot workbook and visual QA; no user dataset is redistributed."""
from pathlib import Path
from statistics import NormalDist
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.boxplot_dialogs import BoxplotDialog,BoxplotTypeDialog

out=Path(__file__).resolve().parents[2]/'outputs'
values=[round(560+(i//12)*9+((i//6)%2)*4+3*NormalDist().inv_cdf(((i%6)+.5)/6),2) for i in range(24)];values[-1]=592
p=Presenter();p.worksheet=Worksheet('Boxplot examples',[
    Column('Strength (N)',values=values),Column('Adjusted',values=[round(v+3+(i%3)*.4,2) for i,v in enumerate(values)]),
    Column('Batch','text',['A']*12+['B']*12),Column('Shift','text',(['Day']*6+['Night']*6)*2)]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(5,17)])
one=p.boxplot_graphs([0]);grouped=p.boxplot_graphs([0],'one_groups',[2,3],display={'individual':True,'mean_symbol':True})
multiple=p.boxplot_graphs([0,1],'multiple')
combined=p.boxplot_graphs([0,1],'multiple_groups',[2,3],variable_position='inner',display={'mean_symbol':True})
panels=p.boxplot_graphs([0,1],'multiple_groups',[2],layout='panels',display={'individual':True,'mean_symbol':True})
app=QApplication([]);w=ModernWindow(p);w.show();w.show_result(combined);w.work_splitter.setSizes([600,240]);app.processEvents()
assert w._active_chart_widget.error is None
w.save_path(out/'StatCraft-boxplot-variants-demo.mpx');w.grab().save(str(out/'StatCraft-boxplot-variants-preview.png'))
w._active_graph_frame.capture().save(str(out/'StatCraft-grouped-boxplots-export.png'))
gallery=BoxplotTypeDialog(w);gallery.show();app.processEvents();gallery.grab().save(str(out/'StatCraft-boxplot-type-chooser.png'));gallery.close();gallery.deleteLater()
dialog=BoxplotDialog(w,p.worksheet,parameters=combined['recipe']['parameters']);dialog.show();app.processEvents();dialog.grab().save(str(out/'StatCraft-boxplot-variable-dialog.png'));dialog.close();dialog.deleteLater()
w.show_result(grouped);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-boxplot-points-export.png'))
w.show_result(panels);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-boxplot-panels-export.png'))
layout=p.graph_layout([grouped,multiple],1,2);w.show_result(layout);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-boxplot-layout-export.png'))
assert w._active_chart_widget.error is None
w.save_path(out/'StatCraft-boxplot-variants-demo.mpx')
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
