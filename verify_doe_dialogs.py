"""Exercise editable child options without modifying application source."""
import json
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QSpinBox,QCheckBox,QLineEdit,QDialogButtonBox
from statcraft.modern_app import ModernWindow
from statcraft.doe_dialogs import CreateFactorialDialog,AnalyzeFactorialDialog
from statcraft.app import Presenter

app=QApplication([]); p=Presenter(); w=ModernWindow(p); w.show(); app.processEvents()
d=CreateFactorialDialog(w); d.factor_count.setCurrentText('3')
def factors():
    child=QApplication.activeModalWidget()
    d.factor_table.item(0,0).setText('Temperature'); d.factor_table.item(0,2).setText('150'); d.factor_table.item(0,3).setText('200')
    child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
QTimer.singleShot(0,factors); d.factor_settings()
assert d.factors[0]==dict(name='Temperature',low=150,high=200)
def designs():
    child=QApplication.activeModalWidget(); centers,reps=child.findChildren(QSpinBox)
    centers.setValue(2); reps.setValue(3); child.accept()
QTimer.singleShot(0,designs); d.designs()
def options():
    child=QApplication.activeModalWidget(); child.findChildren(QCheckBox)[0].setChecked(False)
    child.findChild(QLineEdit).setText('42'); child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
QTimer.singleShot(0,options); d.options(); d.validate()
assert d.parameters['centers']==2 and d.parameters['replicates']==3 and not d.parameters['randomize'] and d.parameters['seed']==42
p.create_factorial(**d.parameters); assert p.worksheet.row_count==26
a=AnalyzeFactorialDialog(w,p.worksheet)
def graphs():
    child=QApplication.activeModalWidget(); child.findChild(QCheckBox).setChecked(False); child.accept()
QTimer.singleShot(0,graphs); a.graphs(); assert a.plot_residuals is False
QTimer.singleShot(0,graphs); a.results(); assert a.show_factor_coding is False
Path(__file__).resolve().parents[1].joinpath('doe-child-dialogs-verified.json').write_text(json.dumps(dict(factor_levels='passed',replicates_centers='passed',randomization_seed='passed',analysis_graphs_results='passed'),indent=2))
p.dirty=False; p._results_dirty=False; w.close()
