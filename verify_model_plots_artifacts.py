"""Review examples for Model-Driven Factorial Plots, Contour Plot, Surface Plot, and Two-Level Factorial Predict."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter, format_entry
from statcraft.model import Column
from statcraft.model_plot_dialogs import (
    ContourLevelsDialog,
    ContourOptionsDialog,
    FactorialPlotsDialog,
    FactorialPlotsGraphsDialog,
    FactorialPlotsOptionsDialog,
    HoldSettingsDialog,
    ModelContourPlotDialog,
    ModelSurfacePlotDialog,
    SurfaceOptionsDialog,
)
from statcraft.model_plots import (
    contour_plot_settings,
    factorial_plots_settings,
    surface_plot_settings,
)
from statcraft.model_plots_smoke import fixture
from statcraft.modern_app import ModernWindow
from statcraft.office_export import export_docx, export_pptx
from statcraft.prediction_dialogs import PredictDialog
from statcraft.verification_fonts import load_verification_fonts

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
load_verification_fonts(app)

p = Presenter()
p.worksheet = fixture()
p._owned_project()

m_rsm = p.analyze_response_surface(4, [0, 1, 2])
m_reg = p.multiple_regression(4, [0, 1, 2])
m_glm = p.general_linear_model(4, [3], [0, 1], terms=[[0], [1], [2]])
m_log = p.fit_binary_logistic(5, [0, 1], [3], event='Pass')

fp_opts = factorial_plots_settings(dict(
    terms_to_display='model',
    show_main_effects=True,
    show_interaction_plot=True,
    matrix_display='lower_left',
    hold_continuous='mean',
    hold_categorical='first',
    hold_values=[dict(index=2, value=48.0)],
    title='Factorial Plots for Yield (RSM)',
))
fp_entry = p.factorial_plots(m_rsm['recipe'], selected_indices=[0, 1, 2], options=fp_opts)

cp_opts = contour_plot_settings(dict(
    pair_mode='single',
    level_mode='number',
    level_count=7,
    show_area=True,
    show_lines=True,
    show_design_points=True,
    hold_continuous='mean',
    hold_categorical='first',
    hold_values=[dict(index=2, value=48.0)],
    title='Contour Plot of Yield vs Pressure, Temperature',
))
cp_entry = p.model_contour_plot(m_rsm['recipe'], x_index=0, y_index=1, options=cp_opts)

sp_opts = surface_plot_settings(dict(
    pair_mode='single',
    surface_style='shaded',
    hold_continuous='mean',
    hold_categorical='first',
    hold_values=[dict(index=2, value=48.0)],
    title='Surface Plot of Yield vs Pressure, Temperature',
))
sp_entry = p.model_surface_plot(m_rsm['recipe'], x_index=0, y_index=1, options=sp_opts)

log_cp_entry = p.model_contour_plot(
    m_log['recipe'],
    x_index=0,
    y_index=1,
    options=contour_plot_settings(dict(
        pair_mode='single',
        level_mode='auto',
        show_area=True,
        show_lines=True,
        hold_categorical='custom',
        hold_values=[dict(index=3, value='CatA')],
    )),
)

w = ModernWindow(p)
w.resize(1500, 1050)
w.show()

# 1. Factorial Plots Graph
w.show_result(fp_entry)
app.processEvents()
assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
for name in ('StatCraft-factorial-plots-graph-preview-45.png', 'StatCraft-factorial-plots-graph.png'):
    w.grab().save(str(out / name))

# 2. Model Contour Plot Graph
w.show_result(cp_entry)
app.processEvents()
assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
for name in ('StatCraft-model-contour-graph-preview-45.png', 'StatCraft-model-contour-graph.png'):
    w.grab().save(str(out / name))

# 3. Model Surface Plot Graph
w.show_result(sp_entry)
app.processEvents()
assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
for name in ('StatCraft-model-surface-graph-preview-45.png', 'StatCraft-model-surface-graph.png'):
    w.grab().save(str(out / name))

# 4. Report view
for idx in range(w.result_tabs.count()):
    if w.result_tabs.tabText(idx) == 'Report':
        w.result_tabs.setCurrentIndex(idx)
        break
app.processEvents()
for name in ('StatCraft-model-plots-report-preview-45.png', 'StatCraft-model-plots-report.png'):
    w.grab().save(str(out / name))

# 5. Dialog screenshots
fp_dlg = FactorialPlotsDialog(w, 'response_surface')
fp_dlg.show()
app.processEvents()
for name in ('StatCraft-factorial-plots-dialog-preview-45.png', 'StatCraft-factorial-plots-dialog.png'):
    fp_dlg.grab().save(str(out / name))
fp_dlg.reject()

cp_dlg = ModelContourPlotDialog(w, 'response_surface')
cp_dlg.show()
app.processEvents()
for name in ('StatCraft-model-contour-dialog-preview-45.png', 'StatCraft-model-contour-dialog.png'):
    cp_dlg.grab().save(str(out / name))
cp_dlg.reject()

sp_dlg = ModelSurfacePlotDialog(w, 'response_surface')
sp_dlg.show()
app.processEvents()
for name in ('StatCraft-model-surface-dialog-preview-45.png', 'StatCraft-model-surface-dialog.png'):
    sp_dlg.grab().save(str(out / name))
sp_dlg.reject()

path = out / 'StatCraft-model-plots-demo.mpx'
w.save_path(path)
w.load_path(path)
assert len(p.history) == 8
for entry in p.history:
    assert not p.result_stale(entry)
    assert p.rerun_result(entry)['result'] == entry['result']

fp_loaded = p.history[4]
cp_loaded = p.history[5]
sp_loaded = p.history[6]
log_cp_loaded = p.history[7]
report_text = '\n\n'.join([
    format_entry(fp_loaded),
    format_entry(cp_loaded),
    format_entry(sp_loaded),
    format_entry(log_cp_loaded),
])
(out / 'StatCraft-model-plots-report.txt').write_text(report_text, encoding='utf-8')

w.show_result(cp_loaded)
snapshot = w._office_snapshot(cp_loaded)
assert snapshot.png and 'Contour Plot of Yield vs Pressure, Temperature' in snapshot.report
for ext, writer in [('docx', export_docx), ('pptx', export_pptx)]:
    target = out / f'StatCraft-model-plots-example.{ext}'
    writer(target, snapshot)
    with ZipFile(target) as z:
        assert any(n.endswith('.xml') for n in z.namelist())

proof = dict(
    fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    worksheets=1,
    fitted_models=4,
    model_plot_runs=4,
    factorial_plots_main_and_interaction=True,
    model_contour_filled_bands_isolines_design_points=True,
    model_surface_3d_shaded_wireframe=True,
    two_level_factorial_predict_and_model_plots=True,
    mpx_roundtrip=True,
    rerun_unchanged=True,
    office_readable_report_and_graph=True,
)
(root / 'work/model-plots-artifacts-verified.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps(proof, indent=2))
p.dirty = False
p._results_dirty = False
w.close()
w.deleteLater()
app.processEvents()
