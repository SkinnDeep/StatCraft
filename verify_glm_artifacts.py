"""Original GLM demo and screenshots for independent review."""
import os,json,hashlib
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.modern_app import ModernWindow
from statcraft.glm import settings
from statcraft.glm_smoke import model_fixture
from statcraft.glm_dialogs import GeneralLinearModelDialog,ModelTermsDialog
from statcraft.verification_fonts import load_verification_fonts
root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication.instance() or QApplication([]);load_verification_fonts(app);app.setQuitOnLastWindowClosed(False)
p=Presenter();p.worksheet=model_fixture();w=ModernWindow(p);w.resize(1440,1000);w.show();app.processEvents()
terms=[[0],[1],[2],[0,1],[0,2],[1,2]]
report=p.general_linear_model(0,[1,2],[3],terms);w.show_result(report);app.processEvents()
w.grab().save(str(out/'StatCraft-glm-report.png'))
graph=p.general_linear_model(0,[1,2],[3],terms,dict(settings(),graphs='four',standardize='center'));w.show_result(graph);app.processEvents()
assert w._active_chart_widget.error is None and len(w._active_chart_widget.panels)==4
w._active_graph_frame.capture().save(str(out/'StatCraft-glm-residuals.png'))
snapshot=w._office_snapshot();assert snapshot.png and 'Analysis of Variance' in snapshot.report
d=GeneralLinearModelDialog(w);d.show();app.processEvents();d.grab().save(str(out/'StatCraft-glm-dialog.png'));d.close()
model=ModelTermsDialog(w,['Material','Temperature','Dose'],terms);model.show();app.processEvents();model.grab().save(str(out/'StatCraft-glm-model-dialog.png'));model.close()
path=out/'StatCraft-glm-demo.mpx';w.save_path(path);w.load_path(path);assert len(p.history)==2
for entry in p.history:assert not p.result_stale(entry) and len(entry['result']['anova_terms'])==6
text=format_entry(p.history[0]);assert 'Factor Information' in text and 'Analysis of Variance' in text
(out/'StatCraft-glm-report.txt').write_text(text,encoding='utf-8')
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();app.processEvents()
proof={'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'models':2,'observations':20,'terms':6,'residual_panels':4,'mpx_roundtrip':True,'office_snapshot_has_graph_and_readable_anova':True,'screenshots':['StatCraft-glm-report.png','StatCraft-glm-residuals.png','StatCraft-glm-dialog.png','StatCraft-glm-model-dialog.png']}
(root/'work/glm-artifacts-verified.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof,indent=2))
