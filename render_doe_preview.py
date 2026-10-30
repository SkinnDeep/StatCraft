from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column
from statcraft.modern_app import ModernWindow
from statcraft.doe_dialogs import CreateFactorialDialog,AnalyzeFactorialDialog

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]); p=Presenter(); w=ModernWindow(p); w.show(); app.processEvents()
d=CreateFactorialDialog(w); d.show(); app.processEvents(); d.grab().save(str(out/'StatCraft-factorial-create.png')); d.close()
p.create_factorial([dict(name='Temperature',low=150,high=200),dict(name='Pressure',low=10,high=20)],replicates=2,randomize=False)
p.add_column('Yield')
for row in range(8):
    a=(p.worksheet.columns[4].values[row]-175)/25; b=(p.worksheet.columns[5].values[row]-15)/5
    p.set_cell(row,6,str(70+2*a-3*b+1.5*a*b+(1 if row<4 else -1)))
w.refresh(); d=AnalyzeFactorialDialog(w,p.worksheet); d.response.setText('C7'); d.show(); app.processEvents()
d.grab().save(str(out/'StatCraft-factorial-analyze.png')); d.close()
w.show_result(p.analyze_factorial(6,[4,5])); w.result_tabs.setCurrentIndex(0); app.processEvents()
w.grab().save(str(out/'StatCraft-factorial-results.png')); p.dirty=False; p._results_dirty=False; w.close()
