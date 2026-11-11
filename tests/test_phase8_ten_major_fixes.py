import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QTableWidget

from statcraft.app import Presenter
from statcraft.connect_workflow import create_workflow_from_entry, replay_workflow
from statcraft.model import Column, Worksheet
from statcraft.modern_charts import ChartWidget
from statcraft.phase6_reports import PHASE6_REPORT_ANALYSES, sections
from statcraft.run_comparator import compare_runs
from statcraft.svg_html_export import export_session_to_html


class Phase8TenMajorFixesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_presenter(self):
        ws = Worksheet(
            columns=[
                Column("Y", "number", [10.0, 12.0, 15.0, 18.0, 20.0, 11.0, 13.0, 17.0, 19.0, 22.0, 9.5, 24.0]),
                Column("X1", "number", [1.0, 2.0, 3.0, 4.0, 5.0, 1.5, 2.5, 3.5, 4.5, 5.5, 0.8, 6.0]),
                Column("Grp", "text", ["  A1 ", "A1", "A2", "A2", "A1", "A1", "A2", "A2", "A1", "A1", "A2", "A2"]),
                Column("Time", "number", [2, 3, 5, 6, 8, 9, 11, 14, 15, 18, 20, 24]),
                Column("Event", "number", [1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0]),
            ]
        )
        p = Presenter()
        p.worksheet = ws
        return p

    def test_fix1_guidance_chips_invoke_real_handlers(self):
        from statcraft.modern_app import ModernWindow

        win = ModernWindow(sandbox_mode=True)
        called = []
        target_methods = [
            "johnson_dialog",
            "capability_nonparametric_dialog",
            "oneway_anova_dialog",
            "stepwise_regression_dialog",
            "cause_and_effect_dialog",
            "discover_best_model_dialog",
            "random_forest_dialog",
        ]
        for m in target_methods:
            setattr(win, m, lambda name=m: called.append(name))

        for action in (
            "johnson_transformation",
            "capability_nonparametric",
            "tukey_comparisons",
            "stepwise_regression",
            "fishbone_diagram",
            "discover_best_model",
            "random_forest",
        ):
            win._on_guidance_action_triggered(action, {})
        self.assertEqual(called, target_methods)
        win.close()

    def test_fix2_and_fix10_report_tables_and_dark_mode_styling(self):
        from statcraft.modern_app import ModernWindow

        p = self._make_presenter()
        rf = p.random_forest(0, [1, 2], n_trees=15)
        tn = p.treenet_gbm(0, [1, 2], n_trees=20)
        mc = p.monte_carlo_simulation("X1: Normal(10, 0.5)", "X1 + 2", lsl=8, usl=12, n_sims=600)
        cox = p.cox_ph_regression(3, 4, [1])
        reml = p.fit_mixed_reml(0, fixed_indices=[1], random_indices=[2])

        for e in (rf, tn, mc, cox, reml):
            self.assertIn(e["result"]["analysis"], PHASE6_REPORT_ANALYSES)
            secs = sections(e["result"])
            self.assertGreaterEqual(len(secs), 2)

        win = ModernWindow(sandbox_mode=True)
        win._dark_mode = True
        win.show_result(tn)
        self.app.processEvents()
        # Check Report tab contains structured QTableWidgets & dark-mode brief card
        report_widget = win.result_tabs.widget(0).content
        tables = report_widget.findChildren(QTableWidget)
        self.assertGreaterEqual(len(tables), 2)
        from PySide6.QtWidgets import QFrame
        brief = report_widget.findChild(QFrame, "executiveBriefCard")
        self.assertIsNotNone(brief)
        self.assertIn("#052e16", brief.styleSheet())

        # Check multi-series legend chart paints cleanly without error
        w = ChartWidget(tn)
        w.resize(760, 480)
        pix = w.grab()
        self.assertFalse(pix.isNull())
        self.assertIsNone(w.error)
        w.close()
        win.close()

    def test_fix3_and_fix4_undoable_stored_cols_and_data_doctor(self):
        p = self._make_presenter()
        p._reset_edits()

        # Data Doctor autofix should be undoable & mark dirty
        fixes = p.autofix_worksheet()
        self.assertGreaterEqual(fixes, 1)
        self.assertEqual(p.worksheet.columns[2].values[0], "A1")
        self.assertTrue(p.dirty)
        self.assertTrue(p.undo())
        self.assertEqual(p.worksheet.columns[2].values[0], "  A1 ")

        # Stored MC / RF / Bootstrap columns should revert cleanly on Undo
        base_cols = len(p.worksheet.columns)
        p.monte_carlo_simulation("X1: Normal(10, 0.5)", "X1", n_sims=300, store_column=True)
        self.assertEqual(len(p.worksheet.columns), base_cols + 1)
        p.undo()
        self.assertEqual(len(p.worksheet.columns), base_cols)
        p.redo()
        self.assertEqual(len(p.worksheet.columns), base_cols + 1)

        p.random_forest(0, [1], n_trees=15, store_fits=True)
        self.assertEqual(len(p.worksheet.columns), base_cols + 3)
        p.undo()
        self.assertEqual(len(p.worksheet.columns), base_cols + 1)

        p.bootstrap_1sample(0, n_resamples=200, store_replicates=True)
        self.assertEqual(len(p.worksheet.columns), base_cols + 2)
        p.undo()
        self.assertEqual(len(p.worksheet.columns), base_cols + 1)

    def test_fix5_edit_last_dialog_records_dialog_calls(self):
        from statcraft.modern_app import ModernWindow

        win = ModernWindow(sandbox_mode=True)
        with patch("statcraft.modern_app.ProcedureDialog") as mock_dlg:
            mock_dlg.return_value.exec.return_value = 0  # Rejected
            win.monte_carlo_dialog()
            self.assertEqual(mock_dlg.call_args.args[1], "Monte Carlo Process & Tolerance Simulation")
            win.edit_last_dialog()
            self.assertEqual(mock_dlg.call_count, 2)
            self.assertEqual(mock_dlg.call_args.args[1], "Monte Carlo Process & Tolerance Simulation")
        win.close()

    def test_fix6_and_fix9_html_svg_and_batch_graph_export(self):
        from statcraft.modern_app import ModernWindow

        p = self._make_presenter()
        rf = p.random_forest(0, [1], n_trees=15)
        gb = p.graph_builder("scatter", [0], x_index=1)
        w = ChartWidget(rf)
        w.resize(640, 400)
        html_doc = export_session_to_html([rf], "Process", chart_widgets={0: w})
        self.assertIn("Relative Variable Importance", html_doc)
        self.assertIn("<svg", html_doc)
        w.close()

        win = ModernWindow(sandbox_mode=True)
        win.presenter = p
        self.assertTrue(win._is_chart_entry(rf))
        self.assertTrue(win._is_chart_entry(gb))
        with tempfile.TemporaryDirectory() as tmp:
            with patch("statcraft.modern_app.QFileDialog.getExistingDirectory", return_value=tmp):
                win.export_all_graphs_dialog()
            pngs = list(Path(tmp).glob("*.png"))
            self.assertEqual(len(pngs), 2)
            self.assertTrue(all(f.stat().st_size > 200 for f in pngs))
        win.close()

    def test_fix7_connected_workflow_restores_worksheet_and_maps_phase3_roles(self):
        p = self._make_presenter()
        orig_ws = p.worksheet
        cox = p.cox_ph_regression(3, 4, [1])
        wf = create_workflow_from_entry(cox, orig_ws)
        self.assertEqual(wf.steps[0].role_bindings["time"], "Time")
        self.assertEqual(wf.steps[0].role_bindings["event"], "Event")
        self.assertEqual(wf.steps[0].role_bindings["covariate_0"], "X1")

        reordered = Worksheet(
            "OtherSheet",
            [
                Column("X1", "number", orig_ws.columns[1].values),
                Column("Event", "number", orig_ws.columns[4].values),
                Column("Time", "number", orig_ws.columns[3].values),
            ],
        )
        res = replay_workflow(wf, reordered, p, overwrite=False)
        self.assertIs(p.worksheet, orig_ws)
        self.assertEqual(len(res["entries"]), 1)

    def test_fix8_run_comparator_nested_metrics_and_directions(self):
        run_a = {"title": "RF v1", "result": {"oob_metrics": {"r2": 0.65, "rmse": 2.40}}}
        run_b = {"title": "RF v2", "result": {"oob_metrics": {"r2": 0.85, "rmse": 1.15}}}
        diff = compare_runs(run_a, run_b)
        self.assertEqual(diff["improvements"], 2)
        self.assertEqual(diff["degradations"], 0)
        rmse_delta = next(d for d in diff["deltas"] if "Rmse" in d.name)
        self.assertTrue(rmse_delta.is_improved)


if __name__ == "__main__":
    unittest.main()
