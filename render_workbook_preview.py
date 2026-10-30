from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]);p=Presenter();p.worksheet=Worksheet('Process data',[
    Column('Temperature',values=[150,160,170,180,190]),Column('Yield',values=[68,72,75,74,80])])
w=ModernWindow(p);w.show();app.processEvents();entry=p.describe_columns([0,1]);w.show_result(entry)
p.add_worksheet('Inspection');p.rename_column(0,'Sample')
for row,value in enumerate([1,2,3]):p.set_cell(row,0,str(value))
p.select_worksheet(0);w.refresh();w.show_result(entry);app.processEvents()
w.grab().save(str(out/'StatCraft-workbook-tabs.png'))
p.save(out/'StatCraft-workbook-demo.mpx');p.dirty=False;p._results_dirty=False;w.close()
