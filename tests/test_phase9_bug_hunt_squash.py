"""Phase 9 Regression Tests: Systematic Bug Hunt & Squash (v116.4.0)."""
from __future__ import annotations

import os
import sys
import unittest
import warnings
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from statcraft.app import Presenter
from statcraft.calculator import evaluate_advanced
from statcraft.mixed_reml import fit_mixed_reml
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.monte_carlo import monte_carlo_simulation
from statcraft.phase6_charts import _draw_barh, prepare as prepare_phase6_chart
from statcraft.printing import PrintController
from statcraft.run_comparator import compare_runs
from statcraft.survival_advanced import warranty_analysis

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestPhase9BugHuntSquash(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_01_reml_collinear_fixed_predictors_no_crash(self):
        sheet = Worksheet("REML_Collinear", [
            Column("Y", "number", [10.1, 12.2, 14.0, 15.8, 18.1, 20.3, 21.9, 24.2, 26.0, 27.9]),
            Column("X1", "number", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]),
            Column("X2", "number", [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]),
            Column("Batch", "text", ["B1", "B1", "B2", "B2", "B3", "B3", "B4", "B4", "B5", "B5"]),
        ])
        res = fit_mixed_reml(sheet, response_index=0, fixed_indices=[1, 2], random_indices=[3])
        self.assertEqual(res["analysis"], "mixed_reml")
        self.assertEqual(len(res["fixed_effects"]), 3)
        for fe in res["fixed_effects"]:
            self.assertTrue(np.isfinite(fe["coef"]))
            self.assertTrue(np.isfinite(fe["se_coef"]))
        for vc in res["variance_components"]:
            self.assertTrue(np.isfinite(vc["var_comp"]))

    def test_02_modern_window_call_catches_runtime_and_linalg_error(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        try:
            def _boom():
                raise RuntimeError("Solver failed to converge")

            with patch.object(QMessageBox, "warning") as mock_warn:
                out = win._call(_boom, result=False)
                self.assertIsNone(out)
                mock_warn.assert_called_once()
        finally:
            win.close()

    def test_03_session_let_creates_new_column_and_is_undoable(self):
        p = Presenter()
        p.worksheet = Worksheet("LetTest", [
            Column("X", "number", [1.0, 2.0, 3.0, 4.0]),
            Column("Y", "number", [10.0, 20.0, 30.0, 40.0]),
        ])
        p.execute_session_command("LET C3 = C1 * 2")
        self.assertEqual(len(p.worksheet.columns), 3)
        self.assertEqual(p.worksheet.columns[2].values, [2.0, 4.0, 6.0, 8.0])

        # Sparse expansion to C5
        p.execute_session_command("LET C5 = C1 + C2")
        self.assertEqual(len(p.worksheet.columns), 5)
        self.assertEqual(p.worksheet.columns[4].values, [11.0, 22.0, 33.0, 44.0])

        # Must be undoable
        self.assertTrue(p.undo())
        self.assertEqual(len(p.worksheet.columns), 3)
        self.assertTrue(p.undo())
        self.assertEqual(len(p.worksheet.columns), 2)

        # SET must also be undoable
        p.execute_session_command("SET C3; 1:4.")
        self.assertEqual(len(p.worksheet.columns), 3)
        self.assertEqual(p.worksheet.columns[2].values, [1.0, 2.0, 3.0, 4.0])
        self.assertTrue(p.undo())
        self.assertEqual(len(p.worksheet.columns), 2)

    def test_04_run_command_line_preserves_editor_on_error(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = Worksheet("CmdErr", [Column("X", "number", [1.0, 2.0, 3.0])])
        try:
            win.command_editor.setPlainText("REGRESS C99 C1")
            with patch.object(QMessageBox, "warning") as mock_warn:
                win.run_command_line()
                mock_warn.assert_called_once()
            self.assertEqual(win.command_editor.toPlainText(), "REGRESS C99 C1")

            win.command_editor.setPlainText("LET K1 = MEAN(C1)")
            win.run_command_line()
            self.assertEqual(win.command_editor.toPlainText(), "")
        finally:
            win.close()

    def test_05_run_comparator_cross_model_canonical_metrics(self):
        rf_run = {
            "title": "Random Forests (Reg)",
            "result": {"oob_metrics": {"r2": 0.78, "rmse": 2.40, "mae": 1.90}},
        }
        tn_run = {
            "title": "TreeNet Gradient Boosting",
            "result": {"val_metrics": {"r2": 0.91, "rmse": 1.55, "mae": 1.15}},
        }
        diff = compare_runs(rf_run, tn_run)
        names = {d.name: d for d in diff["deltas"]}
        self.assertIn("Canonical R2", names)
        self.assertIn("Canonical Rmse", names)
        self.assertIn("Canonical Mae", names)
        self.assertAlmostEqual(names["Canonical R2"].delta, 0.13, places=6)
        self.assertTrue(names["Canonical R2"].is_improved)
        self.assertAlmostEqual(names["Canonical Rmse"].delta, -0.85, places=6)
        self.assertTrue(names["Canonical Rmse"].is_improved)
        self.assertEqual(diff["improvements"], 3)

    def test_06_warranty_duplicate_ages_no_rank_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with self.assertRaisesRegex(ValueError, "2 distinct"):
                warranty_analysis([3, 3, 3], [2, 1, 4], at_risk_total=100)
            self.assertEqual([w for w in caught if "RankWarning" in str(w.category.__name__) or "Polyfit" in str(w.message)], [])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res = warranty_analysis([3, 3, 6, 6, 12], [2, 1, 3, 2, 5], at_risk_total=100)
            self.assertEqual(len(res["age_points"]), 3)
            self.assertEqual(res["age_points"][0]["failures"], 3)
            self.assertEqual(res["age_points"][1]["failures"], 5)
            self.assertEqual([w for w in caught if "RankWarning" in str(w.category.__name__)], [])

    def test_07_monte_carlo_constant_output_no_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res = monte_carlo_simulation(
                [{"name": "X1", "distribution": "Normal", "params": [10.0, 1.0]}],
                "42",
                n_sims=500,
                seed=7,
            )
        self.assertEqual(res["summary"]["mean"], 42.0)
        self.assertEqual(res["sensitivity"][0]["variance_contribution_pct"], 0.0)
        const_warns = [w for w in caught if "ConstantInputWarning" in str(w.category.__name__)]
        self.assertEqual(const_warns, [])

    def test_08_print_controller_snapshot_flushes_events_on_entry_switch(self):
        dummy_win = MagicMock()
        dummy_win.selected_entry = {"title": "Old"}
        other_entry = {"title": "NewGraph"}
        dummy_frame = MagicMock()
        dummy_win._active_graph_frame = dummy_frame

        events = []
        dummy_win.show_result.side_effect = lambda e: events.append(("show", e["title"]))
        dummy_frame.capture.side_effect = lambda: (events.append(("capture", None)), QPixmap(QImage(20, 20, QImage.Format.Format_ARGB32)))[1]

        ctrl = PrintController(dummy_win)
        with patch("PySide6.QtWidgets.QApplication.processEvents", side_effect=lambda: events.append(("processEvents", None))):
            job = ctrl.snapshot(other_entry, "Graph")

        self.assertIsNotNone(job)
        self.assertEqual([e[0] for e in events], ["show", "processEvents", "capture"])

    def test_09_phase6_leaderboard_chart_preserves_negative_r2_label(self):
        chart = QWidget()
        chart.panels = []
        result = {
            "analysis": "discover_best_model",
            "task": "regression",
            "champion_model": "Ridge",
            "leaderboard": [
                {"model": "Ridge", "val_r2": 0.85},
                {"model": "BadPoly", "val_r2": -0.25},
            ],
        }
        prepare_phase6_chart(chart, result)
        panel = chart.panels[0]
        self.assertEqual(panel["values"], [85.0, -25.0])

        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainter
        img = QImage(500, 320, QImage.Format.Format_ARGB32)
        painter = QPainter(img)
        drawn_texts = []
        orig_draw_text = painter.drawText
        try:
            with patch.object(painter, "drawText", side_effect=lambda *args: drawn_texts.append(args[-1]) or orig_draw_text(*args)):
                _draw_barh(chart, painter, QRectF(0, 0, 500, 320), panel)
        finally:
            painter.end()
        self.assertIn("-25%", drawn_texts)
        self.assertNotIn("0%", drawn_texts)

    def test_10_calculator_zscore_standardize_lag_and_constant_stdev(self):
        sheet = Worksheet("CalcNew", [
            Column("X", "number", [10.0, 20.0, None, 30.0]),
            Column("Const", "number", [5.0, 5.0, 5.0, 5.0]),
        ])
        zs = evaluate_advanced("ZSCORE(C1)", sheet)
        # mean=20, sample sd=10 -> [-1.0, 0.0, None, 1.0]
        self.assertAlmostEqual(zs[0], -1.0, places=6)
        self.assertAlmostEqual(zs[1], 0.0, places=6)
        self.assertIsNone(zs[2])
        self.assertAlmostEqual(zs[3], 1.0, places=6)

        std_vals = evaluate_advanced("STANDARDIZE(C1)", sheet)
        self.assertEqual(std_vals, zs)

        # Zero stdev constant column returns None safely instead of ZeroDivisionError
        self.assertEqual(evaluate_advanced("ZSCORE(C2)", sheet), [None, None, None, None])

        # LAG default k=1, k=2, and negative lead k=-1
        self.assertEqual(evaluate_advanced("LAG(C1)", sheet), [None, 10.0, 20.0, None])
        self.assertEqual(evaluate_advanced("LAG(C1, 2)", sheet), [None, None, 10.0, 20.0])
        self.assertEqual(evaluate_advanced("LAG(C1, -1)", sheet), [20.0, None, 30.0, None])


if __name__ == "__main__":
    unittest.main()
