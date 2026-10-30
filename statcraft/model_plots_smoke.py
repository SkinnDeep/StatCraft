"""Source and frozen-package Model-Driven Factorial/Contour/Surface Plots and Factorial Predict acceptance."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem
from .app import format_entry
from .model import Column, Worksheet
from .model_plot_dialogs import (
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
from .modern_charts import ChartWidget
from .prediction_dialogs import PredictDialog, PredictOptionsDialog, PredictResultsDialog


def fixture():
    pts = [
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (-1.0, 1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.682, 0.0, 0.0),
        (1.682, 0.0, 0.0),
        (0.0, -1.682, 0.0),
        (0.0, 1.682, 0.0),
        (0.0, 0.0, -1.682),
        (0.0, 0.0, 1.682),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    ]
    x1 = [p[0] for p in pts]
    x2 = [p[1] for p in pts]
    x3 = [p[2] for p in pts]
    y = [
        84.0 + 5.0 * a - 3.5 * b + 2.0 * c - 4.0 * a * a - 5.0 * b * b - 1.5 * c * c + 3.0 * a * b - 1.2 * a * c
        + (0.4 if i % 2 == 0 else -0.4)
        for i, (a, b, c) in enumerate(pts)
    ]
    cat = ['CatA' if i % 2 == 0 else 'CatB' for i in range(len(pts))]
    pass_fail = ['Pass' if v >= 78.0 else 'Fail' for v in y]
    return Worksheet('Model plots study', [
        Column('Temperature', 'number', [150.0 + 20.0 * a for a in x1]),
        Column('Pressure', 'number', [50.0 + 10.0 * b for b in x2]),
        Column('Time', 'number', [45.0 + 15.0 * c for c in x3]),
        Column('Catalyst', 'text', cat),
        Column('Yield', 'number', y),
        Column('Quality', 'text', pass_fail),
    ])


def verify_model_plots(app, p, w, temp, checkpoint):
    checkpoint('Model-driven Factorial Plots, Contour Plot, Surface Plot, and Two-Level Factorial Predict across fitted model families, child dialogs, MPX and column moves')
    p.new(); p.worksheet = fixture(); w.page = 0; w.refresh()
    for act in w.factorial_plot_actions.values():
        assert not act.isEnabled()
    for act in w.contour_plot_actions.values():
        assert not act.isEnabled()
    for act in w.surface_plot_actions.values():
        assert not act.isEnabled()
    assert not w.predict_actions['analyze_factorial'].isEnabled()

    # Fit GLM with 1 factor + 1 covariate -> Factorial Plots enabled, Contour/Surface disabled (<2 continuous predictors)
    p.general_linear_model(4, [3], [0], terms=[[0], [1]])
    w.refresh()
    assert w.factorial_plot_actions['general_linear_model'].isEnabled()
    assert not w.contour_plot_actions['general_linear_model'].isEnabled()
    assert not w.surface_plot_actions['general_linear_model'].isEnabled()

    # Fit RSM, Regression, GLM (with 2 covariates), Binary Logistic, and Two-Level Factorial
    p.analyze_response_surface(4, [0, 1, 2])
    p.multiple_regression(4, [0, 1, 2])
    p.general_linear_model(4, [3], [0, 1], terms=[[0], [1], [2]])
    p.fit_binary_logistic(5, [0, 1], [3], event='Pass')
    w.refresh()
    for key in ('analyze_response_surface', 'multiple_regression', 'general_linear_model', 'fit_binary_logistic'):
        assert w.factorial_plot_actions[key].isEnabled()
        assert w.contour_plot_actions[key].isEnabled()
        assert w.surface_plot_actions[key].isEnabled()

    # 1. FactorialPlotsDialog + Graphs + Options + Model child dialogs
    fp_dlg = FactorialPlotsDialog(w, 'response_surface')
    assert fp_dlg.selected.count() == 3
    errors = []

    def fp_child(kind):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: fp_child(kind)); return
        try:
            if kind == 'graphs':
                assert isinstance(c, FactorialPlotsGraphsDialog)
                c.matrix_mode.setCurrentIndex(c.matrix_mode.findData('full'))
                c.validate()
            elif kind == 'options':
                assert isinstance(c, FactorialPlotsOptionsDialog)
                c.title_edit.setText('RSM Factorial Plots')
                c.table.item(2, 2).setText('48')
                c.validate(); assert not c.error.text()
            else:
                assert isinstance(c, QDialog) and 'Response Surface Regression' in fp_dlg.model_description()
                c.reject()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for kind, btn in [('graphs', fp_dlg.graphs_button), ('options', fp_dlg.options_button), ('model', fp_dlg.model_button)]:
        QTimer.singleShot(0, lambda kind=kind: fp_child(kind))
        btn.click()
        assert not errors, errors

    fp_dlg.validate(); assert not fp_dlg.error.text(), fp_dlg.error.text()
    fp_entry = fp_dlg.entry
    assert fp_entry['result']['analysis'] == 'factorial_plots'
    assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
    chart_fp = w._active_chart_widget
    assert isinstance(chart_fp, ChartWidget) and chart_fp.error is None and len(chart_fp.panels) == 2
    chart_fp.resize(1100, 720); assert not chart_fp.grab().isNull()
    assert 'RSM Factorial Plots' in format_entry(fp_entry)

    # 2. ModelContourPlotDialog + Contours + Settings + Options + Model child dialogs
    cp_dlg = ModelContourPlotDialog(w, 'response_surface')

    def cp_child(kind):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: cp_child(kind)); return
        try:
            if kind == 'contours':
                assert isinstance(c, ContourLevelsDialog)
                c.design_points.setChecked(True)
                c.level_mode.setCurrentIndex(c.level_mode.findData('number'))
                c.level_count.setText('6')
                c.validate(); assert not c.error.text()
            elif kind == 'settings':
                assert isinstance(c, HoldSettingsDialog)
                c.table.item(2, 2).setText('50')
                c.validate(); assert not c.error.text()
            elif kind == 'options':
                assert isinstance(c, ContourOptionsDialog)
                c.title_edit.setText('RSM Yield Contours')
                c.validate()
            else:
                assert isinstance(c, QDialog)
                c.reject()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for kind, btn in [
        ('contours', cp_dlg.contours_button),
        ('settings', cp_dlg.settings_button),
        ('options', cp_dlg.options_button),
        ('model', cp_dlg.model_button),
    ]:
        QTimer.singleShot(0, lambda kind=kind: cp_child(kind))
        btn.click()
        assert not errors, errors

    cp_dlg.validate(); assert not cp_dlg.error.text(), cp_dlg.error.text()
    cp_entry = cp_dlg.entry
    assert cp_entry['result']['analysis'] == 'model_contour_plot'
    chart_cp = w._active_chart_widget
    assert isinstance(chart_cp, ChartWidget) and chart_cp.error is None and len(chart_cp.panels) == 1
    chart_cp.resize(1000, 700); assert not chart_cp.grab().isNull()
    assert 'RSM Yield Contours' in format_entry(cp_entry) and 'Pressure vs Temperature' in format_entry(cp_entry)

    # Verify CAD extrema and probing on 2D contour
    assert chart_cp._has_contour_panel()
    panel_cp = chart_cp.panels[0]
    assert 'max_pt' in panel_cp and 'min_pt' in panel_cp
    assert any(t in ('cad_peak_2d', 'cad_hud_peak_2d') for t, _ in chart_cp.hit_regions)
    plot_rect = panel_cp['plot_rect']
    chart_cp._probe_contour_click(plot_rect.center())
    assert chart_cp.active_cad_card and chart_cp.active_cad_card.get('mode') == 'probe_2d'
    assert not chart_cp.grab().isNull()

    # 3. ModelSurfacePlotDialog + Settings + Options + Model child dialogs
    sp_dlg = ModelSurfacePlotDialog(w, 'response_surface')

    def sp_child(kind):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: sp_child(kind)); return
        try:
            if kind == 'settings':
                assert isinstance(c, HoldSettingsDialog)
                c.table.item(2, 2).setText('45')
                c.validate(); assert not c.error.text()
            elif kind == 'options':
                assert isinstance(c, SurfaceOptionsDialog)
                c.style_combo.setCurrentIndex(c.style_combo.findData('shaded'))
                c.title_edit.setText('RSM 3D Surface')
                c.validate()
            else:
                assert isinstance(c, QDialog)
                c.reject()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for kind, btn in [
        ('settings', sp_dlg.settings_button),
        ('options', sp_dlg.options_button),
        ('model', sp_dlg.model_button),
    ]:
        QTimer.singleShot(0, lambda kind=kind: sp_child(kind))
        btn.click()
        assert not errors, errors

    sp_dlg.validate(); assert not sp_dlg.error.text(), sp_dlg.error.text()
    sp_entry = sp_dlg.entry
    assert sp_entry['result']['analysis'] == 'model_surface_plot'
    chart_sp = w._active_chart_widget
    assert isinstance(chart_sp, ChartWidget) and chart_sp.error is None and len(chart_sp.panels) == 1
    chart_sp.resize(1000, 700); assert not chart_sp.grab().isNull()
    assert 'RSM 3D Surface' in format_entry(sp_entry) and 'Pressure vs Temperature' in format_entry(sp_entry)

    # Verify CAD navigation, extrema and probing on 3D surface
    assert chart_sp._has_3d_panel()
    chart_sp.rotate_cad_view(10.0, -5.0)
    chart_sp.pan_cad_view(15.0, -20.0)
    chart_sp.zoom_cad_view(0.5)
    assert chart_sp.view_state['pan_x'] == 15.0
    chart_sp.reset_cad_view()
    assert chart_sp.view_state.get('pan_x', 0.0) == 0.0
    panel_sp = chart_sp.panels[0]
    assert 'max_pt' in panel_sp and 'min_pt' in panel_sp
    assert any(t in ('cad_peak_3d', 'cad_hud_peak_3d') for t, _ in chart_sp.hit_regions)

    # 4. Save/Load MPX, column move remapping, and Office snapshot
    path = Path(temp) / 'model-plots.mpx'
    w.save_path(path); w.load_path(path); app.processEvents()
    cp_loaded = next(e for e in p.history if e.get('recipe', {}).get('action') == 'model_contour_plot')
    w.show_result(cp_loaded); w.rerun_selected()
    assert not p.result_stale(w.selected_entry)
    p.move_columns([0], destination='after_last')
    rerun_cp = p.rerun_result(cp_loaded)['result']
    assert abs(rerun_cp['panels'][0]['z_max'] - cp_loaded['result']['panels'][0]['z_max']) < 1e-6
    snapshot = w._office_snapshot(cp_loaded)
    assert snapshot.png and 'RSM Yield Contours' in snapshot.report

    # 5. Two-Level Factorial Predict + Factorial/Contour/Surface Plots enablement
    p.new()
    p.create_factorial(
        [{'name': 'Temp', 'low': 150.0, 'high': 200.0}, {'name': 'Pressure', 'low': 10.0, 'high': 20.0}],
        replicates=2,
        randomize=False,
    )
    p.worksheet.columns.append(Column('Yield', 'number', [60.0, 72.0, 68.0, 84.0, 61.0, 71.0, 67.0, 85.0]))
    p.analyze_factorial(6, [4, 5], max_order=2)
    w.refresh()
    assert w.predict_actions['analyze_factorial'].isEnabled()
    assert w.factorial_plot_actions['analyze_factorial'].isEnabled()
    assert w.contour_plot_actions['analyze_factorial'].isEnabled()
    assert w.surface_plot_actions['analyze_factorial'].isEnabled()

    pred_dlg = PredictDialog(w, 'factorial')

    def pred_child(kind):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: pred_child(kind)); return
        try:
            if kind == 'options':
                assert isinstance(c, PredictOptionsDialog)
                c.confidence.setText('95')
                c.validate(); assert not c.error.text()
            elif kind == 'results':
                assert isinstance(c, PredictResultsDialog)
                c.validate()
            else:
                assert isinstance(c, QDialog)
                c.reject()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for kind, btn in [('options', pred_dlg.options_button), ('results', pred_dlg.results_button), ('model', pred_dlg.model_button)]:
        QTimer.singleShot(0, lambda kind=kind: pred_child(kind))
        btn.click()
        assert not errors, errors

    pred_dlg.values_grid.setItem(0, 0, QTableWidgetItem('175'))
    pred_dlg.values_grid.setItem(0, 1, QTableWidgetItem('15'))
    pred_dlg.validate(); assert not pred_dlg.error.text(), pred_dlg.error.text()
    assert abs(pred_dlg.entry['result']['rows'][0]['fit'] - 71.0) < 1e-4
    p.dirty = False; p._results_dirty = False
