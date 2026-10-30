"""Synthetic demonstration and visual QA for graph editing preview 26."""
from pathlib import Path
from statistics import NormalDist
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.recipes import run
from statcraft.modern_app import ModernWindow
from statcraft.graph_presentation import graph_presentation
from statcraft.graph_object_dialog import GraphObjectDialog

out=Path(__file__).resolve().parents[2]/'outputs'
p=Presenter();values=[round(570+5.5*NormalDist().inv_cdf((i+.5)/120),2) for i in range(120)]
p.worksheet=Worksheet('Graph editing',[Column('Test No.',values=list(range(1,121))),Column('Strength (N)',values=values),
    Column('Batch','text',['A' if i%2 else 'B' for i in range(120)])]+[Column('C'+str(i),metadata={'auto_type':True}) for i in range(4,17)])
scatter=p.scatter_plot(0,1,'regression_groups',2)
p.update_graph_styles(scatter,{'p0:s0':{'color':'#276b9b','marker':'diamond','marker_size':8},
    'p0:s1':{'color':'#cf672b','marker':'square','marker_size':8},'p0:fit0':{'color':'#276b9b','line_width':2,'line_style':'dash'},'p0:fit1':{'color':'#cf672b','line_width':2}})
hist=run(p,{'action':'graph','parameters':{'method':'histogram','indices':[1],'bins':12}})
p.update_histogram_settings(hist,{'bins':12,'scale':'Percent','fit':'Normal'})
p.update_graph_styles(hist,{'p0:bars':{'fill':'#80a8d4','edge':'#647c96','line_width':.6},'p0:fit0':{'color':'#bb2211','line_width':1.6}})
settings=graph_presentation(hist);settings.update(subtitle='Normal',subtitle_enabled=True)
p.update_graph_presentation(hist,settings)
app=QApplication([]);w=ModernWindow(p);w.show();w.show_result(hist);w.edit_graph_dialog(hist)
w.work_splitter.setSizes([570,270]);w.table.setColumnWidth(1,95);app.processEvents()
w.save_path(out/'StatCraft-graph-editing-demo.mpx')
w.grab().save(str(out/'StatCraft-graph-editing-preview.png'))
w._active_graph_frame.capture().save(str(out/'StatCraft-edited-histogram-preview.png'))
dialog=GraphObjectDialog(w._active_chart_widget.editable_objects(),hist['graph_styles'],'p0:bars',w)
dialog.show();app.processEvents();dialog.grab().save(str(out/'StatCraft-object-properties-preview.png'));dialog.reject()
w.close_graph_options();w.show_result(scatter);app.processEvents()
w._active_graph_frame.capture().save(str(out/'StatCraft-edited-scatter-preview.png'))
assert w._active_chart_widget.error is None
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
