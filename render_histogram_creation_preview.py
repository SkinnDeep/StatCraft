"""Synthetic workbook and visual QA for histogram creation variants."""
from pathlib import Path
from statistics import NormalDist
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.histogram_dialogs import HistogramDialog,HistogramTypeDialog

out=Path(__file__).resolve().parents[2]/'outputs'
values=[round(566+(i%2)*6+4*NormalDist().inv_cdf((i//2+.5)/60),3) for i in range(120)]
p=Presenter();p.worksheet=Worksheet('Histogram examples',[
    Column('Strength (N)',values=values),Column('Adjusted strength',values=[round(v+2+(i%5)*.3,3) for i,v in enumerate(values)]),
    Column('Batch','text',['A' if i%2==0 else 'B' for i in range(120)])]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(4,17)])
simple=p.histogram_graphs([0]);fitted=p.histogram_graphs([0],'fit',settings={'bins':12})
groups=p.histogram_graphs([0],'groups',2,layout='panels',settings={'bins':12,'scale':'Percent'})
overlay=p.histogram_graphs([0,1],'fit_groups',2,settings={'bins':12,'scale':'Percent'})
app=QApplication([]);w=ModernWindow(p);w.show();w.show_result(overlay);w.work_splitter.setSizes([650,200]);app.processEvents()
assert w._active_chart_widget.error is None
w.save_path(out/'StatCraft-histogram-variants-demo.mpx')
w.grab().save(str(out/'StatCraft-histogram-variants-preview.png'))
w._active_graph_frame.capture().save(str(out/'StatCraft-grouped-histograms-export.png'))
chooser=HistogramTypeDialog(w);chooser.show();app.processEvents();chooser.grab().save(str(out/'StatCraft-histogram-type-chooser.png'));chooser.close();chooser.deleteLater()
dialog=HistogramDialog(w,p.worksheet,parameters=overlay['recipe']['parameters']);dialog.show();app.processEvents()
dialog.grab().save(str(out/'StatCraft-histogram-variable-dialog.png'));dialog.close();dialog.deleteLater()
w.show_result(groups);app.processEvents();w._active_graph_frame.capture().save(str(out/'StatCraft-histogram-panels-export.png'))
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
