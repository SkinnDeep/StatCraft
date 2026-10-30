from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.modern_app import ModernWindow
from statcraft.doe_dialogs import CreateFactorialDialog
from statcraft.doe_terms_dialog import FactorialTermsDialog

out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]);p=Presenter();w=ModernWindow(p);w.show();app.processEvents()
d=CreateFactorialDialog(w);d.factor_count.setCurrentText('4');d.design_types[1].setChecked(True);d.generators={'D':'ABC'}
def grab_generators():
    child=QApplication.activeModalWidget();app.processEvents();child.grab().save(str(out/'StatCraft-fractional-generators.png'));child.reject()
QTimer.singleShot(0,grab_generators);d.generator_settings()
p.create_factorial([dict(name=x,low=-1,high=1) for x in 'ABCD'],generators={'D':'ABC'},replicates=2,randomize=False)
terms=FactorialTermsDialog(w,p.worksheet,[4,5,6,7],2,[[0],[1],[2],[3],[0,1]])
terms.show();app.processEvents();terms.grab().save(str(out/'StatCraft-factorial-terms.png'));terms.close()
w.show_result(p.history[-1]);w.work_splitter.setSizes([1000,0]);app.processEvents();w.grab().save(str(out/'StatCraft-fractional-aliases.png'))
p.dirty=False;p._results_dirty=False;w.close()
