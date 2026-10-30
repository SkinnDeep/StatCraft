from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]);p=Presenter();p.worksheet=Worksheet('Grouped measurements',[
    Column('Temperature',values=[150,160,170,180,190,200]),
    Column('Yield',values=[68,72,75,74,80,82]),
    Column('Batch','text',['A','A','B','B',None,''])])
w=ModernWindow(p);w.show();app.processEvents()
entry=p.scatter_plot(0,1,'regression_groups',2);w.show_result(entry)
p.add_worksheet('Inspection');p.select_worksheet(0);w.refresh();w.show_result(entry)
w.result_tabs.setCurrentIndex(1);app.processEvents()
w.grab().save(str(out/'StatCraft-text-workbook.png'))
p.save(out/'StatCraft-text-workbook-demo.mpx');p.dirty=False;p._results_dirty=False;w.close()
w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
