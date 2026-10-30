from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]);p=Presenter();p.worksheet=Worksheet('Dated measurements',[
    Column('Measured at','date',[46310,46310.5,None,46311.5,46312,46312.5]),
    Column('Temperature',values=[150,160,170,180,190,200]),
    Column('Yield',values=[68,72,75,74,80,82]),
    Column('Batch','text',['A','A','B','B',None,''])])
w=ModernWindow(p);w.show();app.processEvents()
entry=p.describe_columns([1,2]);w.show_result(entry)
p.add_worksheet('Inspection');p.select_worksheet(0);w.refresh();w.show_result(entry)
w.work_splitter.setSizes([320,550]);app.processEvents()
p.save(out/'StatCraft-date-workbook-demo.mpx');w.refresh();app.processEvents()
w.grab().save(str(out/'StatCraft-date-workbook.png'))
p.dirty=False;p._results_dirty=False;w.close()
w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
