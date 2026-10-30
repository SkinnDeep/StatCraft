"""Source and frozen-package Response Optimizer acceptance."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
from .model import Column, Worksheet
from .optimizer_dialogs import (
    OptimizerDesirabilityDialog,
    OptimizerGraphsDialog,
    OptimizerOptionsDialog,
    OptimizerResultsDialog,
    ResponseOptimizerDialog,
)
from .modern_charts import ChartWidget
from .app import format_entry


def fixture():
    x1 = [-1.0, 1.0, -1.0, 1.0, -1.414, 1.414, 0.0, 0.0, 0.0, 0.0, 0.0]
    x2 = [-1.0, -1.0, 1.0, 1.0, 0.0, 0.0, -1.414, 1.414, 0.0, 0.0, 0.0]
    y1 = [
        88.0 + 4.0 * a - 3.0 * b - 5.0 * a * a - 6.0 * b * b + 2.0 * a * b
        for a, b in zip(x1, x2)
    ]
    y2 = [
        20.0 + 5.0 * a + 4.0 * b + 1.5 * a * a + 1.0 * b * b
        for a, b in zip(x1, x2)
    ]
    cat = ['BatchA' if i % 2 == 0 else 'BatchB' for i in range(len(x1))]
    pass_fail = ['Pass' if v >= 82.0 else 'Fail' for v in y1]
    return Worksheet('Response optimizer study', [
        Column('Temperature', 'number', [150.0 + 20.0 * a for a in x1]),
        Column('Pressure', 'number', [50.0 + 10.0 * b for b in x2]),
        Column('Yield', 'number', y1),
        Column('Cost', 'number', y2),
        Column('Batch', 'text', cat),
        Column('Quality', 'text', pass_fail),
    ])


def verify_response_optimizer(app, p, w, temp, checkpoint):
    checkpoint('Response optimizer multi-response desirability, constraints, starting values, child dialogs, optimization plot, MPX and column moves')
    p.new(); p.worksheet = fixture(); w.page = 0; w.refresh()
    for act in w.optimizer_actions.values():
        assert not act.isEnabled()

    p.analyze_response_surface(2, [0, 1])
    p.multiple_regression(3, [0, 1])
    p.fit_binary_logistic(5, [0, 1], [], event='Pass')
    w.refresh()
    assert w.optimizer_actions['analyze_response_surface'].isEnabled()
    assert w.optimizer_actions['multiple_regression'].isEnabled()
    assert w.optimizer_actions['fit_binary_logistic'].isEnabled()

    d = ResponseOptimizerDialog(w, 'response_surface')
    assert d.responses_table.rowCount() == 3
    d.set_response_goal(0, 'maximize')
    d.set_response_goal(1, 'minimize')
    d.set_response_goal(2, 'target', 0.85)
    errors = []

    def child(kind):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: child(kind)); return
        try:
            if kind == 'setup':
                assert isinstance(c, OptimizerDesirabilityDialog) and c.table.rowCount() == 3
                c.table.selectRow(0)
                assert not c.preview.grab().isNull()
                c.table.item(0, 6).setText('2')
                c.table.item(1, 3).setText('15')
                c.table.item(1, 4).setText('28')
                c.validate(); assert not c.error.text()
            elif kind == 'options':
                assert isinstance(c, OptimizerOptionsDialog) and c.constraints_table.rowCount() == 2
                mode_combo = c.constraints_table.cellWidget(0, 1)
                mode_combo.setCurrentIndex(mode_combo.findData('region'))
                c.constraints_table.item(0, 3).setText('135')
                c.constraints_table.item(0, 4).setText('175')
                c.starting_table.item(0, 1).setText('152')
                c.starting_table.item(1, 1).setText('48')
                c.confidence.setText('95')
                c.validate(); assert not c.error.text()
            elif kind == 'graphs':
                assert isinstance(c, OptimizerGraphsDialog) and c.optimization_plot.isChecked()
                c.validate()
            elif kind == 'results':
                assert isinstance(c, OptimizerResultsDialog)
                c.max_solutions.setValue(3)
                c.validate()
            else:
                assert isinstance(c, QDialog) and 'Response Surface Regression' in d.model_description()
                c.reject()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for kind, btn in [
        ('setup', d.setup_button),
        ('options', d.options_button),
        ('graphs', d.graphs_button),
        ('results', d.results_button),
        ('model', d.model_button),
    ]:
        QTimer.singleShot(0, lambda kind=kind: child(kind))
        btn.click()
        assert not errors, errors

    d.validate(); assert not d.error.text(), d.error.text()
    entry = d.entry
    assert entry['result']['analysis'] == 'response_optimizer'
    assert entry['result']['optimal_composite_desirability'] > 0.5
    assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
    chart = w._active_chart_widget
    assert isinstance(chart, ChartWidget) and chart.error is None and len(chart.panels) == 1
    chart.resize(1100, 720); assert not chart.grab().isNull()
    text = format_entry(entry)
    assert 'Response Optimization: Yield, Cost, Quality' in text
    assert 'Multiple Response Prediction' in text and 'Solutions' in text

    # Report-only run when optimization_plot=False opens on Report tab
    d_no_plot = ResponseOptimizerDialog(w, 'response_surface')
    assert d_no_plot.row_specs[0]['goal'] == 'maximize'
    assert d_no_plot.options['max_solutions'] == 3
    d_no_plot.options['optimization_plot'] = False
    d_no_plot.validate(); assert not d_no_plot.error.text(), d_no_plot.error.text()
    assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Report'
    d_no_plot.options['optimization_plot'] = True

    # Re-show the plotted entry, save/load MPX, and verify column move remapping
    w.show_result(entry)
    path = Path(temp) / 'response-optimizer.mpx'
    w.save_path(path); w.load_path(path); app.processEvents()
    opt_loaded = next(e for e in p.history if e.get('recipe', {}).get('action') == 'optimize_responses' and e['recipe']['parameters']['options']['optimization_plot'])
    w.show_result(opt_loaded); w.rerun_selected()
    assert not p.result_stale(w.selected_entry)
    p.move_columns([0], destination='after_last')
    rerun_res = p.rerun_result(opt_loaded)['result']
    assert abs(rerun_res['optimal_composite_desirability'] - opt_loaded['result']['optimal_composite_desirability']) < 1e-6
    snapshot = w._office_snapshot(opt_loaded)
    assert snapshot.png and 'Response Optimization:' in snapshot.report
    p.dirty = False; p._results_dirty = False
