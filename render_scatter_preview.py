from pathlib import Path
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.variable_dialogs import ScatterTypeDialog,ScatterDialog
out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]); p=Presenter()
x=list(range(1,11))*2
y=[2*i+.5*(-1)**i for i in range(1,11)]+[.9*i+8+.3*(-1)**i for i in range(1,11)]
p.worksheet=Worksheet('Process data',[Column('Setting',values=x),Column('Yield',values=y),Column('Batch',kind='text',values=['A']*10+['B']*10)])
w=ModernWindow(p); w.show(); app.processEvents()
gallery=ScatterTypeDialog(w); gallery.show(); app.processEvents(); gallery.grab().save(str(out/'StatCraft-scatterplot-gallery.png')); gallery.close()
dialog=ScatterDialog(w,p.worksheet,'regression_groups')
dialog.roles.setItem(0,0,QTableWidgetItem('C2')); dialog.roles.setItem(0,1,QTableWidgetItem('C1')); dialog.group_entry.setText('C3')
dialog.show(); app.processEvents(); dialog.grab().save(str(out/'StatCraft-grouped-scatter-selection.png')); dialog.close()
w.show_result(p.scatter_plot(0,1,'regression_groups',2,title='Yield by batch'))
w.result_tabs.setCurrentIndex(1); w.work_splitter.setSizes([1000,0]); app.processEvents()
w.grab().save(str(out/'StatCraft-grouped-regression.png'))
p.dirty=False; p._results_dirty=False; w.close()
