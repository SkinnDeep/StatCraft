"""Synthetic, redistributable preview 27 workbook and visual QA."""
from pathlib import Path
import math
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.compositions import appearance_from_entry
from statcraft.recipes import run

out=Path(__file__).resolve().parents[2]/'outputs'
p=Presenter();p.worksheet=Worksheet('Process trials',[
    Column('Trial',values=list(range(1,121))),
    Column('Strength (N)',values=[round(565+6*math.sin(i*.43)+(i%3)*4+i*.035,2) for i in range(120)]),
    Column('Batch','text',['A' if i%2 else 'B' for i in range(120)])]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(4,17)])
scatter=p.scatter_plot(0,1,'regression_groups',2)
p.update_graph_styles(scatter,{'p0:s0':{'color':'#276b9b','marker':'diamond'},'p0:s1':{'color':'#cf672b','marker':'square'}})
hist=run(p,{'action':'graph','parameters':{'method':'histogram','indices':[1],'bins':12}})
p.update_histogram_settings(hist,{'bins':12,'scale':'Percent','fit':'Normal'})
panels=p.panel_graph(scatter['recipe'],[2],source_appearance=appearance_from_entry(scatter))
bar=p.expanded_graph('bar_chart',[2]);layout=p.graph_layout([scatter,hist,bar],2,2,'Process overview')
app=QApplication([]);w=ModernWindow(p);w.resize(1440,960);w.show();w.work_splitter.setSizes([650,200])
w.show_result(panels);app.processEvents();w.grab().save(str(out/'StatCraft-panel-graphs-preview.png'))
w.show_result(layout);app.processEvents();w.grab().save(str(out/'StatCraft-graph-layout-preview.png'))
w._active_graph_frame.capture().save(str(out/'StatCraft-layout-export.png'))
w.show_result(scatter);app.processEvents();w.brush_points_dialog(scatter)
w._active_chart_widget.brushed_rows={1,2,3,4,5};w._receive_brushed_rows(scatter,[1,2,3,4,5]);app.processEvents()
w.grab().save(str(out/'StatCraft-brushing-preview.png'))
w.save_path(out/'StatCraft-compositions-demo.mpx')
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
