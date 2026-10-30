from PySide6.QtWidgets import QApplication, QTableWidgetItem
from statcraft.modern_app import ModernWindow, ProcedureDialog, selector, numeric
from statcraft.variable_dialogs import ScatterDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from pathlib import Path
out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]); p=Presenter()
p.worksheet=Worksheet('Measurements',[Column('Length mm',values=[10,12,14,16,18]),Column('Mass g',values=[20,25,27,34,35])])
w=ModernWindow(p); w.show(); app.processEvents()
w.grab().save(str(out/'StatCraft-column-name-row.png'))
d=ScatterDialog(w,p.worksheet)
d.roles.setItem(0,0,QTableWidgetItem('C2')); d.roles.setItem(0,1,QTableWidgetItem('C1'))
d.show(); app.processEvents(); d.grab().save(str(out/'StatCraft-variable-selection.png')); d.close()
e=ProcedureDialog(w,'Correlation',p.worksheet,[selector('indices','Variables',True,2)],
    [{'key':'method','label':'Method','choices':['Pearson','Spearman']},numeric('confidence','Confidence level',.95)])
e.controls['indices'].setText('C1 C2'); e.show(); app.processEvents()
e.grab().save(str(out/'StatCraft-analysis-selection.png')); e.close()
p.dirty=False; p._results_dirty=False; w.close()
