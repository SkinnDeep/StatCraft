import copy
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem

from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget
from statcraft.office_export import export_docx, export_pptx
from statcraft.optimizer import settings
from statcraft.optimizer_dialogs import (
    OptimizerDesirabilityDialog,
    OptimizerGraphsDialog,
    OptimizerOptionsDialog,
    OptimizerResultsDialog,
    ResponseOptimizerDialog,
)
from statcraft.recipes import columns, run


def rsm_fixture():
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
    return Worksheet('Optimizer integration study', [
        Column('Temperature', 'number', [150.0 + 20.0 * a for a in x1]),
        Column('Pressure', 'number', [50.0 + 10.0 * b for b in x2]),
        Column('Yield', 'number', y1),
        Column('Cost', 'number', y2),
        Column('Batch', 'text', cat),
        Column('Quality', 'text', pass_fail),
    ])


class ResponseOptimizerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def presenter(self):
        p = Presenter()
        p.worksheet = rsm_fixture()
        return p

    def test_presenter_recipe_staleness_and_rerun(self):
        p = self.presenter()
        m_yield = p.analyze_response_surface(2, [0, 1])
        m_cost = p.multiple_regression(3, [0, 1])
        opts = settings(dict(
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
                dict(index=0, value=150.0),
                dict(index=1, value=50.0),
            ],
        ))
        entry = p.optimize_responses([
            dict(model_recipe=m_yield['recipe'], goal='maximize', lower=75.0, target=90.0, weight=1.0, importance=2.0),
            dict(model_recipe=m_cost['recipe'], goal='minimize', target=15.0, upper=28.0, weight=1.0, importance=1.0),
        ], options=opts)
        self.assertEqual(columns(entry['recipe']), [0, 1, 2, 3])
        self.assertFalse(p.result_stale(entry))
        self.assertEqual(run(p, entry['recipe'])['result'], entry['result'])
        report = format_entry(entry)
        self.assertIn('Response Optimization: Yield, Cost', report)
        self.assertIn('Parameters', report)
        self.assertIn('Variable Ranges', report)
        self.assertIn('Starting Point', report)
        self.assertIn('Solutions', report)
        self.assertIn('Multiple Response Prediction', report)
        p.set_cell(0, 2, str(p.worksheet.columns[2].values[0] + 1.5))
        self.assertTrue(p.result_stale(entry))
        again = p.rerun_result(entry)
        self.assertFalse(p.result_stale(again))
        self.assertNotEqual(again['result']['optimal_composite_desirability'], entry['result']['optimal_composite_desirability'])

    def test_column_moves_inserts_deletes_and_undo_redo(self):
        p = self.presenter()
        m_yield = p.analyze_response_surface(2, [0, 1])
        m_cost = p.general_linear_model(3, [4], [0, 1])
        opts = settings(dict(
            settings(),
            constraints=[
                dict(index=0, mode='region', value=None, lower=140.0, upper=170.0),
                dict(index=4, mode='hold', value='BatchA', lower=None, upper=None),
            ],
            starting_values=[
                dict(index=0, value=155.0),
                dict(index=4, value='BatchA'),
            ],
        ))
        entry = p.optimize_responses([
            dict(model_recipe=m_yield['recipe'], goal='maximize', lower=75.0, target=90.0),
            dict(model_recipe=m_cost['recipe'], goal='minimize', target=15.0, upper=28.0),
        ], options=opts)
        self.assertEqual(columns(entry['recipe']), [0, 1, 2, 3, 4])
        orig_comp_d = entry['result']['optimal_composite_desirability']

        # Move C1 (Temperature, index 0) after last column
        p.move_columns([0], destination='after_last')
        params = entry['recipe']['parameters']
        self.assertEqual(params['responses'][0]['model_recipe']['parameters']['factor_indices'], [5, 0])
        self.assertEqual(params['options']['constraints'][0]['index'], 5)
        self.assertEqual(params['options']['starting_values'][0]['index'], 5)
        rerun_after_move = p.rerun_result(entry)
        self.assertAlmostEqual(rerun_after_move['result']['optimal_composite_desirability'], orig_comp_d, places=6)

        # Undo and Redo column move
        p.undo()
        self.assertEqual(entry['recipe']['parameters']['options']['constraints'][0]['index'], 0)
        p.redo()
        self.assertEqual(entry['recipe']['parameters']['options']['constraints'][0]['index'], 5)
        p.undo()

        # Delete a predictor column used by the optimizer -> marks source_unavailable
        p.delete_columns([1])
        self.assertTrue(entry.get('source_unavailable'))
        with self.assertRaises(ValueError):
            p.rerun_result(entry)
        p.undo()
        self.assertFalse(entry.get('source_unavailable'))
        self.assertAlmostEqual(p.rerun_result(entry)['result']['optimal_composite_desirability'], orig_comp_d, places=6)

    def test_mpx_roundtrip_preserves_optimizer_entry_and_rerun(self):
        p = self.presenter()
        m_yield = p.analyze_response_surface(2, [0, 1])
        m_qual = p.fit_binary_logistic(5, [0, 1], [], event='Pass')
        entry = p.optimize_responses([
            dict(model_recipe=m_yield['recipe'], goal='maximize', lower=75.0, target=90.0),
            dict(model_recipe=m_qual['recipe'], goal='target', lower=0.5, target=0.85, upper=0.99),
        ])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'optimizer-roundtrip.mpx'
            p.save(path)
            q = Presenter()
            q.load(path)
            loaded_opt = next(e for e in q.history if e.get('recipe', {}).get('action') == 'optimize_responses')
            self.assertEqual(loaded_opt['result'], entry['result'])
            self.assertFalse(q.result_stale(loaded_opt))
            self.assertEqual(q.rerun_result(loaded_opt)['result'], entry['result'])

    def test_invalid_optimizer_recipes_rejected(self):
        p = self.presenter()
        m_yield = p.analyze_response_surface(2, [0, 1])
        entry = p.optimize_responses([
            dict(model_recipe=m_yield['recipe'], goal='maximize', lower=75.0, target=90.0),
        ])
        base = entry['recipe']

        # Empty responses list
        bad_empty = copy.deepcopy(base)
        bad_empty['parameters']['responses'] = []
        with self.assertRaises(ValueError):
            columns(bad_empty)

        # Duplicate response column
        bad_dup = copy.deepcopy(base)
        bad_dup['parameters']['responses'] = [
            copy.deepcopy(base['parameters']['responses'][0]),
            copy.deepcopy(base['parameters']['responses'][0]),
        ]
        with self.assertRaises(ValueError):
            columns(bad_dup)

        # Overlapping response and predictor across models
        m_overlap = p.multiple_regression(0, [1, 2])
        bad_overlap = copy.deepcopy(base)
        bad_overlap['parameters']['responses'].append(dict(
            model_recipe=m_overlap['recipe'],
            goal='minimize',
            target=140.0,
            upper=170.0,
        ))
        with self.assertRaises(ValueError):
            columns(bad_overlap)

        # Constraint referencing non-predictor column
        bad_const = copy.deepcopy(base)
        bad_const['parameters']['options']['constraints'] = [
            dict(index=4, mode='hold', value='BatchA'),
        ]
        with self.assertRaises(ValueError):
            columns(bad_const)

    def test_dialogs_modern_window_chart_and_exports(self):
        w = ModernWindow()
        try:
            p = w.presenter
            p.new()
            p.worksheet = rsm_fixture()
            w.page = 0
            w.refresh()
            for act in w.optimizer_actions.values():
                self.assertFalse(act.isEnabled())

            # Fit RSM for Yield, Regression for Cost, and Logistic for Quality
            p.analyze_response_surface(2, [0, 1])
            p.multiple_regression(3, [0, 1])
            p.fit_binary_logistic(5, [0, 1], [], event='Pass')
            w.refresh()
            self.assertTrue(w.optimizer_actions['analyze_response_surface'].isEnabled())
            self.assertTrue(w.optimizer_actions['multiple_regression'].isEnabled())
            self.assertTrue(w.optimizer_actions['fit_binary_logistic'].isEnabled())

            d = ResponseOptimizerDialog(w, 'response_surface')
            self.assertEqual(d.responses_table.rowCount(), 3)
            d.set_response_goal(0, 'maximize')
            d.set_response_goal(1, 'minimize')
            self.assertEqual(d.row_specs[0]['goal'], 'maximize')
            self.assertEqual(d.row_specs[1]['goal'], 'minimize')

            errors = []

            def handle_child(kind):
                c = QApplication.activeModalWidget()
                if c is None:
                    QTimer.singleShot(10, lambda: handle_child(kind))
                    return
                try:
                    if kind == 'setup':
                        self.assertIsInstance(c, OptimizerDesirabilityDialog)
                        self.assertEqual(c.table.rowCount(), 2)
                        c.table.selectRow(0)
                        pix = c.preview.grab()
                        self.assertFalse(pix.isNull())
                        c.table.item(0, 6).setText('2')
                        c.table.item(1, 3).setText('15')
                        c.table.item(1, 4).setText('28')
                        c.validate()
                        self.assertFalse(c.error.text())
                    elif kind == 'options':
                        self.assertIsInstance(c, OptimizerOptionsDialog)
                        self.assertEqual(c.constraints_table.rowCount(), 2)
                        mode_combo = c.constraints_table.cellWidget(0, 1)
                        mode_combo.setCurrentIndex(mode_combo.findData('region'))
                        c.constraints_table.item(0, 3).setText('135')
                        c.constraints_table.item(0, 4).setText('175')
                        c.starting_table.item(0, 1).setText('152')
                        c.starting_table.item(1, 1).setText('48')
                        c.confidence.setText('95')
                        c.validate()
                        self.assertFalse(c.error.text())
                    elif kind == 'graphs':
                        self.assertIsInstance(c, OptimizerGraphsDialog)
                        self.assertTrue(c.optimization_plot.isChecked())
                        c.validate()
                    elif kind == 'results':
                        self.assertIsInstance(c, OptimizerResultsDialog)
                        c.max_solutions.setValue(3)
                        c.validate()
                    elif kind == 'model':
                        self.assertIsInstance(c, QDialog)
                        self.assertIn('Response Surface Regression', d.model_description())
                        c.reject()
                except Exception as exc:
                    errors.append(str(exc))
                    c.reject()

            for kind, btn in [
                ('setup', d.setup_button),
                ('options', d.options_button),
                ('graphs', d.graphs_button),
                ('results', d.results_button),
                ('model', d.model_button),
            ]:
                QTimer.singleShot(0, lambda kind=kind: handle_child(kind))
                btn.click()
                self.assertEqual(errors, [])

            d.validate()
            self.assertFalse(d.error.text(), d.error.text())
            entry = d.entry
            self.assertEqual(entry['result']['analysis'], 'response_optimizer')
            self.assertEqual(w.result_tabs.tabText(w.result_tabs.currentIndex()), 'Graph')
            chart = w._active_chart_widget
            self.assertIsInstance(chart, ChartWidget)
            self.assertIsNone(chart.error)
            chart.resize(1100, 720)
            self.assertFalse(chart.grab().isNull())

            # Verify dialog state restoration
            restored = ResponseOptimizerDialog(w, 'response_surface')
            self.assertEqual(restored.row_specs[0]['goal'], 'maximize')
            self.assertEqual(restored.row_specs[1]['goal'], 'minimize')
            self.assertEqual(restored.options['max_solutions'], 3)
            restored.reject()

            # Verify Office exports (DOCX and PPTX)
            snapshot = w._office_snapshot(entry)
            self.assertTrue(snapshot.png)
            self.assertIn('Response Optimization: Yield, Cost', snapshot.report)
            with tempfile.TemporaryDirectory() as td:
                docx_path = Path(td) / 'optimizer.docx'
                pptx_path = Path(td) / 'optimizer.pptx'
                export_docx(docx_path, snapshot)
                export_pptx(pptx_path, snapshot)
                self.assertTrue(docx_path.exists() and docx_path.stat().st_size > 2000)
                self.assertTrue(pptx_path.exists() and pptx_path.stat().st_size > 2000)
        finally:
            w.presenter.dirty = False
            w.presenter._results_dirty = False
            w.close()


if __name__ == '__main__':
    unittest.main()
