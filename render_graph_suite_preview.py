from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QWidget,QGridLayout
from statcraft.app import Presenter
from statcraft.model import Column,Matrix,Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_expanded_charts import ExpandedChartWidget
from statcraft.expanded_graphs import METHODS

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]);p=Presenter()
x=[0,1,2]*3;y=[0,0,0,1,1,1,2,2,2]
p.worksheet=Worksheet('Graph examples',[Column('Setting A',values=x),Column('Setting B',values=y),
    Column('Response',values=[3+2*a+3*b+.5*a*b for a,b in zip(x,y)]),
    Column('Batch','text',['A','A','A','B','B','B','C','C','C']),
    Column('Measured at','date',[46310+i/4 for i in range(9)])])
p.replace_stored_data([Column('Scale',values=[2])],[Matrix('Weights',2,3,[1,2,3,4,None,6])])
entries={}
for method,meta in METHODS.items():
    indices=[] if method=='distribution_plot' else [0,1,2] if meta['minimum']==3 else [0,2] if meta['minimum']==2 else [3] if method in ('bar_chart','pie_chart') else [2]
    entries[method]=p.expanded_graph(method,indices,3 if method=='interval_plot' else None)
p.add_worksheet('Inspection');p.select_worksheet(0)
p.save(out/'StatCraft-graph-suite-demo.mpx')
w=ModernWindow(p);w.show();w.work_splitter.setSizes([550,320]);w.show_result(entries['contour']);app.processEvents()
w.grab().save(str(out/'StatCraft-graph-suite.png'))
gallery=QWidget();layout=QGridLayout(gallery)
for i,method in enumerate(['bubble','correlogram','interval_plot','area_graph','contour','surface3d']):
    chart=ExpandedChartWidget(entries[method]);chart.setMinimumSize(520,350);layout.addWidget(chart,i//3,i%3)
gallery.resize(1680,850);gallery.show();app.processEvents()
for chart in gallery.findChildren(ExpandedChartWidget):
    chart.grab();assert chart.error is None,chart.error
gallery.grab().save(str(out/'StatCraft-graph-gallery.png'))
p.dirty=False;p._results_dirty=False;w.close();gallery.close()
w.deleteLater();gallery.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
