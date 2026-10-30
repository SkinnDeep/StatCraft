"""Review examples for supported model predictions and persisted source setups."""
import os,json,hashlib
from pathlib import Path
from zipfile import ZipFile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from statcraft.app import Presenter,format_entry
from statcraft.modern_app import ModernWindow
from statcraft.prediction_smoke import fixture
from statcraft.prediction import settings
from statcraft.prediction_dialogs import PredictDialog,PredictOptionsDialog,PredictResultsDialog
from statcraft.verification_fonts import load_verification_fonts
from statcraft.office_export import export_docx,export_pptx
from statcraft.glm_smoke import model_fixture
from statcraft.response_surface import create
from statcraft.response_surface_smoke import add_measurements

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False);load_verification_fonts(app)
p=Presenter();p.worksheet=fixture();p._owned_project()
model=p.inference('linear_regression',[0,1]);manual=p.predict_model(model['recipe'],values=[[2.5],[7.]])
column=p.predict_model(model['recipe'],input_mode='columns',new_indices=[2],options=dict(settings(),confidence=.9,side='lower'))
sheet=p.add_worksheet('GLM predictions');sheet.columns=model_fixture().columns
model=p.general_linear_model(0,[1,2],[3],[[0],[1],[2],[0,2]])
glm=p.predict_model(model['recipe'],values=[['A','Low',2.5],['B','High',4.]])
sheet=p.add_worksheet('Surface predictions');template=create([dict(name='Heat',low=100.,high=140.),dict(name='Time',low=20.,high=40.)],alpha_mode='face',randomize=False);add_measurements(template)
sheet.columns=template.columns;sheet.metadata=template.metadata
model=p.analyze_response_surface(6,[4,5]);surface=p.predict_model(model['recipe'],values=[[120.,30.],[130.,35.]])
p.select_worksheet(0)
w=ModernWindow(p);w.resize(1500,1050);w.show();w.show_result(manual);app.processEvents()
w.grab().save(str(out/'StatCraft-prediction-report.png'))
d=PredictDialog(w,'regression');d.input_mode.setCurrentIndex(d.input_mode.findData('values'));d.clear_row();d.values_grid.setItem(0,0,QTableWidgetItem('2.5'));d.values_grid.setItem(1,0,QTableWidgetItem('7'))
d.show();app.processEvents();d.grab().save(str(out/'StatCraft-prediction-dialog.png'));d.reject()
for cls,name in [(PredictOptionsDialog,'options'),(PredictResultsDialog,'results')]:
    child=cls(w,settings());child.show();app.processEvents();child.grab().save(str(out/('StatCraft-prediction-'+name+'.png')));child.reject()
path=out/'StatCraft-prediction-demo.mpx';w.save_path(path);w.load_path(path)
predictions=[e for e in p.history if e.get('recipe',{}).get('action')=='predict_model'];assert len(predictions)==4 and len(p.native_project.worksheets)==3
for entry in predictions:
    assert not p.result_stale(entry)
    assert p.rerun_result(entry)['result']==entry['result']
manual=predictions[0];w.show_result(manual)
(out/'StatCraft-prediction-report.txt').write_text(format_entry(manual),encoding='utf-8')
snapshot=w._office_snapshot(manual);assert not snapshot.png and 'Regression Equation' in snapshot.report and 'Predictions' in snapshot.report
for ext,writer in [('docx',export_docx),('pptx',export_pptx)]:
    target=out/('StatCraft-prediction-example.'+ext);writer(target,snapshot)
    with ZipFile(target) as z:assert any(n.endswith('.xml') for n in z.namelist())
proof=dict(fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),worksheets=3,predictions=4,model_families=3,manual_and_column_inputs=True,mpx_roundtrip=True,rerun_unchanged=True,office_readable_equation_and_prediction_report=True)
(root/'work/prediction-artifacts-verified.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof,indent=2))
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();app.processEvents()
