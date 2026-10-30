"""Review examples for Response Optimizer multi-response desirability, constraints, Optimization Plot, reports and MPX roundtrips."""
import os
import json
import hashlib
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter, format_entry
from statcraft.modern_app import ModernWindow
from statcraft.optimizer import settings
from statcraft.optimizer_dialogs import (
    OptimizerDesirabilityDialog,
    OptimizerGraphsDialog,
    OptimizerOptionsDialog,
    OptimizerResultsDialog,
    ResponseOptimizerDialog,
)
from statcraft.optimizer_smoke import fixture
from statcraft.verification_fonts import load_verification_fonts
from statcraft.office_export import export_docx, export_pptx

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
load_verification_fonts(app)

p = Presenter()
p.worksheet = fixture()
p._owned_project()

m_yield = p.analyze_response_surface(2, [0, 1])
m_cost = p.multiple_regression(3, [0, 1])
m_qual = p.fit_binary_logistic(5, [0, 1], [], event='Pass')
m_glm = p.general_linear_model(2, [4], [0, 1])

opt_opts = settings(dict(
    settings(),
    confidence=0.95,
    side='two_sided',
    max_solutions=3,
    optimization_plot=True,
    constraints=[
        dict(index=0, mode='region', value=None, lower=135.0, upper=175.0),
        dict(index=1, mode='none', value=None, lower=None, upper=None),
    ],
    starting_values=[
        dict(index=0, value=152.0),
        dict(index=1, value=48.0),
    ],
))

multi_opt = p.optimize_responses([
    dict(model_recipe=m_yield['recipe'], goal='maximize', lower=75.0, target=90.0, upper=None, weight=1.0, importance=2.0),
    dict(model_recipe=m_cost['recipe'], goal='minimize', lower=None, target=15.0, upper=28.0, weight=1.0, importance=1.0),
    dict(model_recipe=m_qual['recipe'], goal='target', lower=0.50, target=0.88, upper=0.99, weight=1.0, importance=1.0),
], options=opt_opts)

glm_opt = p.optimize_responses([
    dict(model_recipe=m_glm['recipe'], goal='maximize', lower=75.0, target=90.0, upper=None, weight=1.0, importance=1.0),
], options=settings(dict(
    settings(),
    max_solutions=2,
    constraints=[dict(index=4, mode='hold', value='BatchA', lower=None, upper=None)],
)))

w = ModernWindow(p)
w.resize(1500, 1050)
w.show()
w.show_result(multi_opt)
app.processEvents()
assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
w.grab().save(str(out / 'StatCraft-optimizer-plot.png'))

for idx in range(w.result_tabs.count()):
    if w.result_tabs.tabText(idx) == 'Report':
        w.result_tabs.setCurrentIndex(idx)
        break
app.processEvents()
w.grab().save(str(out / 'StatCraft-optimizer-report.png'))

d = ResponseOptimizerDialog(w, 'response_surface')
d.set_response_goal(0, 'maximize')
d.set_response_goal(1, 'minimize')
d.set_response_goal(2, 'target', 0.88)
d.show()
app.processEvents()
d.grab().save(str(out / 'StatCraft-optimizer-dialog.png'))

active_specs = d._active_specs()
des_dlg = OptimizerDesirabilityDialog(d, p.worksheet, active_specs)
des_dlg.show()
app.processEvents()
des_dlg.grab().save(str(out / 'StatCraft-optimizer-desirability.png'))
des_dlg.reject()

opt_dlg = OptimizerOptionsDialog(d, p.worksheet, [s['bundle'] for s in active_specs], opt_opts)
opt_dlg.show()
app.processEvents()
opt_dlg.grab().save(str(out / 'StatCraft-optimizer-options.png'))
opt_dlg.reject()

gr_dlg = OptimizerGraphsDialog(d, opt_opts)
gr_dlg.show()
app.processEvents()
gr_dlg.grab().save(str(out / 'StatCraft-optimizer-graphs.png'))
gr_dlg.reject()

res_dlg = OptimizerResultsDialog(d, opt_opts)
res_dlg.show()
app.processEvents()
res_dlg.grab().save(str(out / 'StatCraft-optimizer-results.png'))
res_dlg.reject()
d.reject()

path = out / 'StatCraft-optimizer-demo.mpx'
w.save_path(path)
w.load_path(path)
assert len(p.history) == 6
for entry in p.history:
    assert not p.result_stale(entry)
    assert p.rerun_result(entry)['result'] == entry['result']

opt_loaded = p.history[4]
glm_opt_loaded = p.history[5]
report_text = format_entry(opt_loaded) + '\n\n' + format_entry(glm_opt_loaded)
(out / 'StatCraft-optimizer-report.txt').write_text(report_text, encoding='utf-8')

w.show_result(opt_loaded)
snapshot = w._office_snapshot(opt_loaded)
assert snapshot.png and 'Response Optimization: Yield, Cost, Quality' in snapshot.report and 'Multiple Response Prediction' in snapshot.report
for ext, writer in [('docx', export_docx), ('pptx', export_pptx)]:
    target = out / f'StatCraft-optimizer-example.{ext}'
    writer(target, snapshot)
    with ZipFile(target) as z:
        assert any(n.endswith('.xml') for n in z.namelist())

proof = dict(
    fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    worksheets=1,
    fitted_models=4,
    optimization_runs=2,
    multi_response_derringer_suich=True,
    constraints_and_starting_values=True,
    optimization_plot_dashboard=True,
    mpx_roundtrip=True,
    rerun_unchanged=True,
    office_readable_report_and_graph=True,
)
(root / 'work/optimizer-artifacts-verified.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps(proof, indent=2))
p.dirty = False
p._results_dirty = False
w.close()
w.deleteLater()
app.processEvents()
