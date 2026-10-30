"""Review examples for binary logistic regression fits, diagnostic plots, probability predictions and MPX roundtrips."""
import os, json, hashlib
from pathlib import Path
from zipfile import ZipFile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter, format_entry
from statcraft.modern_app import ModernWindow
from statcraft.logistic import settings
from statcraft.logistic_dialogs import BinaryLogisticDialog, LogisticSettingsDialog
from statcraft.logistic_smoke import fixture
from statcraft.prediction import settings as prediction_settings
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

fit_opts = dict(settings(), graphs='four', diagnostics='all')
individual = p.fit_binary_logistic(0, [1], [2], event='Pass', terms=[[0], [1]], options=fit_opts)
grouped = p.fit_binary_logistic(3, [1], [2], trials_index=4, terms=[[0], [1]], options=dict(settings(), graphs='none'))
pred_manual = p.predict_model(
    individual['recipe'],
    values=[['North', 14.], ['South', 20.]],
    options=dict(prediction_settings(), intervals='confidence', confidence=.95),
)
pred_columns = p.predict_model(
    individual['recipe'],
    input_mode='columns',
    new_indices=[6, 5],
    options=dict(prediction_settings(), intervals='confidence', confidence=.90, side='lower'),
)

w = ModernWindow(p)
w.resize(1500, 1050)
w.show()
w.show_result(individual)
app.processEvents()
assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
w.grab().save(str(out / 'StatCraft-logistic-diagnostic-plots.png'))

for idx in range(w.result_tabs.count()):
    if w.result_tabs.tabText(idx) == 'Report':
        w.result_tabs.setCurrentIndex(idx)
        break
app.processEvents()
w.grab().save(str(out / 'StatCraft-logistic-report.png'))

d = BinaryLogisticDialog(w)
d.response_format.setCurrentIndex(0)
d.controls['response_index'].setText('C1')
d.controls['continuous_indices'].setText('C2')
d.controls['categorical_indices'].setText('C3')
d.select_event('Pass')
d.show()
app.processEvents()
d.grab().save(str(out / 'StatCraft-logistic-dialog.png'))
d.reject()

for section, slug in [('Options', 'options'), ('Graphs', 'graphs'), ('Results', 'results')]:
    child = LogisticSettingsDialog(w, section, fit_opts)
    child.show()
    app.processEvents()
    child.grab().save(str(out / f'StatCraft-logistic-{slug}.png'))
    child.reject()

path = out / 'StatCraft-logistic-demo.mpx'
w.save_path(path)
w.load_path(path)
assert len(p.history) == 4
for entry in p.history:
    assert not p.result_stale(entry)
    assert p.rerun_result(entry)['result'] == entry['result']

fit_loaded = p.history[0]
pred_loaded = p.history[2]
report_text = format_entry(fit_loaded) + '\n\n' + format_entry(pred_loaded)
(out / 'StatCraft-logistic-report.txt').write_text(report_text, encoding='utf-8')

w.show_result(fit_loaded)
snapshot = w._office_snapshot(fit_loaded)
assert snapshot.png and 'Likelihood Ratio Test' in snapshot.report and 'Odds Ratios' in snapshot.report
for ext, writer in [('docx', export_docx), ('pptx', export_pptx)]:
    target = out / f'StatCraft-logistic-example.{ext}'
    writer(target, snapshot)
    with ZipFile(target) as z:
        assert any(n.endswith('.xml') for n in z.namelist())

proof = dict(
    fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    worksheets=1,
    fits=2,
    predictions=2,
    individual_and_grouped_formats=True,
    four_panel_roc_and_residual_dashboard=True,
    mpx_roundtrip=True,
    rerun_unchanged=True,
    office_readable_report_and_graph=True,
)
(root / 'work/logistic-artifacts-verified.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps(proof, indent=2))
p.dirty = False
p._results_dirty = False
w.close()
w.deleteLater()
app.processEvents()
