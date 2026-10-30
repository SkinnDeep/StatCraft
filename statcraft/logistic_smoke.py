"""Source and frozen-package binary logistic regression & prediction acceptance."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem
from .model import Column, Worksheet
from .logistic_dialogs import BinaryLogisticDialog, LogisticSettingsDialog
from .glm_dialogs import ModelTermsDialog
from .prediction_dialogs import PredictDialog, PredictOptionsDialog, PredictResultsDialog
from .modern_charts import ChartWidget
from .app import format_entry


def fixture():
    return Worksheet('Binary logistic study', [
        Column('Inspection', 'text', [
            'Fail', 'Fail', 'Pass', 'Fail', 'Fail', 'Pass',
            'Pass', 'Fail', 'Pass', 'Pass', 'Fail', 'Pass',
        ]),
        Column('Temperature', 'number', [10., 11., 13., 14., 15., 16., 17., 18., 19., 20., 21., 24.]),
        Column('Supplier', 'text', ['North', 'South', 'North', 'South', 'North', 'South', 'North', 'South', 'North', 'South', 'South', 'North']),
        Column('Defective', 'number', [2, 4, 6, 9, 12, 15, 3, 5, 8, 11, 14, 17]),
        Column('Inspected', 'number', [20]*12),
        Column('Candidate temp', 'number', [12.5, None, 21.]),
        Column('Candidate supplier', 'text', ['North', 'South', 'South']),
    ])


def verify_binary_logistic(app, p, w, temp, checkpoint):
    checkpoint('Binary logistic individual/grouped fits, child dialogs, 4-panel ROC/diagnostics, brushing, Predict, MPX and column moves')
    p.new(); p.worksheet = fixture(); w.page = 0; w.refresh()
    assert not w.predict_actions['fit_binary_logistic'].isEnabled()
    d = BinaryLogisticDialog(w)
    d.controls['response_index'].setText('C1')
    d.controls['continuous_indices'].setText('C2')
    d.controls['categorical_indices'].setText('C3')
    d.select_event('Pass')
    errors = []

    def child(section):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: child(section)); return
        try:
            if section == 'Model':
                assert isinstance(c, ModelTermsDialog)
                c.validate()
            elif section == 'Options':
                assert isinstance(c, LogisticSettingsDialog)
                c.controls['confidence'].setValue(90.)
                c.controls['threshold'].setValue(.55)
                c.validate(); assert not c.error.text()
            elif section == 'Graphs':
                assert isinstance(c, LogisticSettingsDialog)
                c.controls['graphs'].setCurrentIndex(c.controls['graphs'].findData('four'))
                c.validate(); assert not c.error.text()
            elif section == 'Results':
                assert isinstance(c, LogisticSettingsDialog)
                c.controls['diagnostics'].setCurrentIndex(c.controls['diagnostics'].findData('all'))
                c.validate(); assert not c.error.text()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for section in ('Model', 'Options', 'Graphs', 'Results'):
        QTimer.singleShot(0, lambda section=section: child(section))
        d.option_buttons[section].click()
        assert not errors, errors

    d.validate(); assert not d.error.text(), d.error.text()
    entry = d.entry
    assert entry['result']['event'] == 'Pass' and entry['result']['n'] == 12
    assert w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Graph'
    chart = w._active_chart_widget
    assert isinstance(chart, ChartWidget) and chart.error is None and len(chart.panels) == 4 and chart.panel_columns == 2
    chart.resize(1200, 960); assert not chart.grab().isNull()
    assert {row for row, _ in chart.brush_regions} == set(range(1, 13))
    text = format_entry(entry)
    assert 'Likelihood Ratio Test' in text and 'Odds Ratios' in text and '90% Wald Lower' in text
    assert w.predict_actions['fit_binary_logistic'].isEnabled()

    # Grouped event/trial fit without graphs opens on Report
    g = BinaryLogisticDialog(w)
    g.response_format.setCurrentIndex(1)
    g.controls['response_index'].setText('C4')
    g.controls['trials_index'].setText('C5')
    g.controls['continuous_indices'].setText('C2')
    g.controls['categorical_indices'].clear()
    g.options['graphs'] = 'none'
    g.validate(); assert not g.error.text(), g.error.text()
    grouped_entry = g.entry
    assert grouped_entry['result']['grouped'] and w.result_tabs.tabText(w.result_tabs.currentIndex()) == 'Report'
    restored_grouped = BinaryLogisticDialog(w)
    assert restored_grouped.response_format.currentData() == 'grouped'
    restored_grouped.reject()

    # Predict from binary logistic model (manual + column modes)
    pred_dialog = PredictDialog(w, 'logistic')
    assert pred_dialog.model_selector.count() == 2
    pred_dialog.model_selector.setCurrentIndex(0)
    assert pred_dialog.model_recipe['action'] == 'fit_binary_logistic'
    pred_dialog.values_grid.cellWidget(0, 0).setCurrentIndex(pred_dialog.values_grid.cellWidget(0, 0).findData('North'))
    pred_dialog.values_grid.setItem(0, 1, QTableWidgetItem('15'))
    pred_dialog.values_grid.cellWidget(1, 0).setCurrentIndex(pred_dialog.values_grid.cellWidget(1, 0).findData('South'))
    pred_dialog.values_grid.setItem(1, 1, QTableWidgetItem('30'))

    def pred_child(kind):
        c = QApplication.activeModalWidget()
        if c is None:
            QTimer.singleShot(10, lambda: pred_child(kind)); return
        try:
            if kind == 'options':
                assert isinstance(c, PredictOptionsDialog)
                assert [c.intervals.itemData(i) for i in range(c.intervals.count())] == ['confidence', 'none']
                c.confidence.setText('90'); c.validate(); assert not c.error.text()
            elif kind == 'results':
                assert isinstance(c, PredictResultsDialog)
                assert 'logistic' in c.equation.text().lower()
                c.validate()
            else:
                assert isinstance(c, QDialog) and 'Binary Logistic Regression' in pred_dialog.model_description()
                c.reject()
        except Exception as exc:
            errors.append(str(exc)); c.reject()

    for kind, btn in [('options', pred_dialog.options_button), ('results', pred_dialog.results_button), ('model', pred_dialog.model_button)]:
        QTimer.singleShot(0, lambda kind=kind: pred_child(kind))
        btn.click()
        assert not errors, errors

    pred_dialog.validate(); assert not pred_dialog.error.text(), pred_dialog.error.text()
    pred_entry = pred_dialog.entry
    assert pred_entry['result']['analysis'] == 'logistic_prediction' and pred_entry['result']['rows'][1]['extrapolated']
    assert 'Probability Predictions' in format_entry(pred_entry)

    pred_col = PredictDialog(w, 'logistic')
    pred_col.model_selector.setCurrentIndex(0)
    pred_col.input_mode.setCurrentIndex(pred_col.input_mode.findData('columns'))
    pred_col.columns_grid.setItem(0, 0, QTableWidgetItem('C7'))
    pred_col.columns_grid.setItem(0, 1, QTableWidgetItem('C6'))
    pred_col.validate(); assert not pred_col.error.text(), pred_col.error.text()
    col_entry = pred_col.entry
    assert col_entry['result']['missing'] == 1

    path = Path(temp) / 'binary-logistic.mpx'
    w.save_path(path); w.load_path(path); app.processEvents()
    fit_loaded = next(e for e in p.history if e.get('recipe', {}).get('action') == 'fit_binary_logistic' and not e['result']['grouped'])
    pred_loaded = next(e for e in reversed(p.history) if e.get('recipe', {}).get('action') == 'predict_model')
    w.show_result(fit_loaded); w.rerun_selected()
    assert not p.result_stale(w.selected_entry)
    p.move_columns([0], destination='after_last')
    assert p.rerun_result(fit_loaded)['result']['probabilities'] == fit_loaded['result']['probabilities']
    assert p.rerun_result(pred_loaded)['result']['rows'] == pred_loaded['result']['rows']
    snapshot = w._office_snapshot(fit_loaded)
    assert snapshot.png and 'Likelihood Ratio Test' in snapshot.report
    restored = BinaryLogisticDialog(w)
    assert restored.response_format.currentData() == 'individual' and restored.event.currentData() == 'Pass'
    restored.reject()
    p.dirty = False; p._results_dirty = False
