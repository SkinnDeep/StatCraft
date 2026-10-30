"""Synthetic category-order and overflowing worksheet-tab demonstration."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow

out=Path(__file__).resolve().parents[2]/'outputs'
p=Presenter();p.worksheet=Worksheet('Production grades',[
    Column('Sample',values=list(range(1,13))),Column('Strength',values=[50,60,55,58,65,62,64,57,56,70,69,60]),
    Column('Grade','text',['Standard','Premium','Standard','Basic','Premium','Standard','Basic','Premium','Standard','Basic','Standard','Premium'])]+
    [Column('C'+str(i),metadata={'auto_type':True}) for i in range(4,17)])
p.set_column_value_order(2,'custom',['Premium','Standard','Basic'])
entry=p.expanded_graph('bar_chart',[2])
for number in range(1,13):p.add_worksheet('Trial worksheet '+str(number))
p.select_worksheet(0)
app=QApplication([]);window=ModernWindow(p);window.show();window.show_result(entry)
app.processEvents();window.save_path(out/'StatCraft-value-order-demo.mpx')
window.grab().save(str(out/'StatCraft-value-order-and-tabs.png'))
p.dirty=False;p._results_dirty=False;window.close();window.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
