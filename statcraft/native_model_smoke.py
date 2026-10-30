"""Smoke verification for reconstructed native response-surface models."""
from pathlib import Path
import hashlib
from PySide6.QtWidgets import QTableWidgetItem
from .app import Presenter, format_entry
from .modern_app import ModernWindow
from .prediction_dialogs import PredictDialog
from .model_plot_dialogs import FactorialPlotsDialog, ModelContourPlotDialog, ModelSurfacePlotDialog
from .optimizer_dialogs import ResponseOptimizerDialog


def verify_native_model_reconstruction(app, p, w, temp, checkpoint):
    checkpoint('Native model reconstruction: discoverable and runnable across Predict, Factorial, Contour, Surface, and Response Optimizer')
    
    fixture_path = Path('C:/Users/funny/Downloads/MFGEN 401 Lecture 22 - Example Response Surface Design PP pyrolysis yield.mpx')
    assert fixture_path.exists(), f"Fixture missing: {fixture_path}"
    source_bytes = fixture_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    q = Presenter()
    q.load(fixture_path)

    viewer = ModernWindow(q)
    viewer.show()
    viewer.refresh()
    app.processEvents()

    # 1. Action enablement
    assert viewer.predict_actions['analyze_response_surface'].isEnabled()
    assert viewer.optimizer_actions['analyze_response_surface'].isEnabled()
    assert viewer.factorial_plot_actions['analyze_response_surface'].isEnabled()
    assert viewer.contour_plot_actions['analyze_response_surface'].isEnabled()
    assert viewer.surface_plot_actions['analyze_response_surface'].isEnabled()

    # 2. PredictDialog
    d_predict = PredictDialog(viewer)
    assert d_predict.model_selector.count() >= 1
    w_combo = d_predict.values_grid.cellWidget(0, 0)
    if w_combo is not None and w_combo.count() > 1:
        w_combo.setCurrentIndex(1)
    else:
        d_predict.values_grid.setItem(0, 0, QTableWidgetItem('1.0'))
    d_predict.values_grid.setItem(0, 1, QTableWidgetItem('500.0'))
    d_predict.values_grid.setItem(0, 2, QTableWidgetItem('0.5'))
    d_predict.validate()
    assert d_predict.entry is not None, d_predict.error.text()
    e_pred = d_predict.entry
    assert e_pred['origin'] == 'statcraft'
    assert 'rows' in e_pred['result'] and len(e_pred['result']['rows']) >= 1

    # 3. FactorialPlotsDialog
    d_fact = FactorialPlotsDialog(viewer)
    assert d_fact.model_selector.count() >= 1
    d_fact.add_all()
    d_fact.validate()
    assert d_fact.entry is not None, d_fact.error.text()
    e_fact = d_fact.entry
    assert e_fact['origin'] == 'statcraft'

    # 4. ModelContourPlotDialog
    d_contour = ModelContourPlotDialog(viewer)
    assert d_contour.model_selector.count() >= 1
    d_contour.validate()
    assert d_contour.entry is not None, d_contour.error.text()
    e_contour = d_contour.entry
    assert e_contour['origin'] == 'statcraft'

    # 5. ModelSurfacePlotDialog
    d_surface = ModelSurfacePlotDialog(viewer)
    assert d_surface.model_selector.count() >= 1
    d_surface.validate()
    assert d_surface.entry is not None, d_surface.error.text()
    e_surface = d_surface.entry
    assert e_surface['origin'] == 'statcraft'

    # 6. ResponseOptimizerDialog
    d_opt = ResponseOptimizerDialog(viewer)
    assert d_opt.responses_table.rowCount() >= 1
    goal_combo = d_opt.responses_table.cellWidget(0, 1)
    if goal_combo is not None:
        goal_combo.setCurrentIndex(1) # Maximize
    d_opt.validate()
    assert d_opt.entry is not None, d_opt.error.text()
    e_opt = d_opt.entry
    assert e_opt['origin'] == 'statcraft'
    assert 'solutions' in e_opt['result']

    # Show results and check graph rendering
    for entry in (e_pred, e_fact, e_contour, e_surface, e_opt):
        viewer.show_result(entry)
        app.processEvents()

    # MPX Save / Reopen cycle
    save_path = Path(temp) / 'native-reconstruction-smoke.mpx'
    q.save(save_path)
    restored = Presenter()
    restored.load(save_path)
    restored_entries = [e for e in restored.history if e.get('origin') == 'statcraft']
    assert len(restored_entries) >= 5

    # Verify original fixture invariance
    assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == source_sha

    # Teardown viewer
    viewer.presenter.dirty = False
    viewer.presenter._results_dirty = False
    viewer.close()
    viewer.deleteLater()
    d_predict.deleteLater()
    d_fact.deleteLater()
    d_contour.deleteLater()
    d_surface.deleteLater()
    d_opt.deleteLater()
