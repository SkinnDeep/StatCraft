"""Comprehensive unit tests for Minitab 22-parity Fitted Line Plot."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["STATCRAFT_TESTING"] = "1"

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.fitted_line_plot import fit_fitted_line_plot
from statcraft.fitted_line_plot_report import format_fitted_line_plot_report
from statcraft.fitted_line_plot_chart import FittedLinePlotChartWidget
from statcraft.fitted_line_plot_dialog import (
    FittedLinePlotDialog,
    FittedLinePlotOptionsDialog,
    FittedLinePlotGraphsDialog,
    FittedLinePlotStorageDialog,
    default_fitted_line_plot_options,
)


class TestFittedLinePlot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Known synthetic dataset: y = 10 + 2.5*x - 0.2*x^2 + noise
        self.x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        self.y = [12.3, 14.1, 15.8, 16.9, 17.5, 17.9, 17.8, 17.1, 16.2, 14.8]
        self.ws = Worksheet("TestFit", [
            Column("X_Val", "number", self.x),
            Column("Y_Val", "number", self.y),
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def tearDown(self):
        self.app.processEvents()

    def test_linear_fit_calculations(self):
        res = fit_fitted_line_plot(self.x, self.y, model_type="linear", confidence=0.95, x_name="X_Val", y_name="Y_Val")
        self.assertEqual(res["analysis"], "fitted_line_plot")
        self.assertEqual(res["degree"], 1)
        self.assertIn("Y_Val = ", res["equation"])
        self.assertGreater(res["r_squared"], 0.0)
        self.assertGreater(res["s"], 0.0)

        # Check ANOVA conservation: SS_Total = SS_Regression + SS_Error
        anova = res["anova"]
        ss_reg = anova["regression"]["ss"]
        ss_err = anova["error"]["ss"]
        ss_tot = anova["total"]["ss"]
        self.assertAlmostEqual(ss_tot, ss_reg + ss_err, places=5)

        # Check CI and PI intervals
        crv = res["curve"]
        self.assertEqual(len(crv["x"]), 120)
        for i in range(len(crv["x"])):
            fit_i = crv["fit"][i]
            ci_lo = crv["ci_low"][i]
            ci_hi = crv["ci_high"][i]
            pi_lo = crv["pi_low"][i]
            pi_hi = crv["pi_high"][i]
            self.assertLessEqual(ci_lo, fit_i)
            self.assertGreaterEqual(ci_hi, fit_i)
            self.assertLessEqual(pi_lo, ci_lo)
            self.assertGreaterEqual(pi_hi, ci_hi)

    def test_quadratic_and_cubic_fit(self):
        # Quadratic fit
        res_quad = fit_fitted_line_plot(self.x, self.y, model_type="quadratic", confidence=0.95)
        self.assertEqual(res_quad["degree"], 2)
        self.assertIn("X²", res_quad["equation"])
        self.assertEqual(len(res_quad["anova"]["sequential"]), 2)
        self.assertGreater(res_quad["r_squared"], 0.85)

        # Cubic fit
        res_cub = fit_fitted_line_plot(self.x, self.y, model_type="cubic", confidence=0.95)
        self.assertEqual(res_cub["degree"], 3)
        self.assertIn("X³", res_cub["equation"])
        self.assertEqual(len(res_cub["anova"]["sequential"]), 3)

    def test_report_formatting(self):
        res = fit_fitted_line_plot(self.x, self.y, model_type="quadratic", x_name="X_Val", y_name="Y_Val")
        rep = format_fitted_line_plot_report(res)
        self.assertIn("Fitted Line Plot: Y_Val versus X_Val", rep)
        self.assertIn("Regression Equation", rep)
        self.assertIn("Model Summary", rep)
        self.assertIn("Analysis of Variance", rep)
        self.assertIn("Linear", rep)
        self.assertIn("Quadratic", rep)

    def test_app_integration_and_recipe(self):
        entry = self.p.fitted_line_plot(1, 0, model_type="quadratic", confidence=0.95)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "fitted_line_plot")
        self.assertIn("connected_analysis", entry)

        conn = entry["connected_analysis"]
        self.assertEqual(conn["analysis_type"], "fitted_line_plot")
        self.assertIn("r_script", conn)
        self.assertIn("lm(", conn["r_script"])
        self.assertIn("predict(", conn["r_script"])

    def test_chart_widget_rendering(self):
        res = fit_fitted_line_plot(self.x, self.y, model_type="quadratic", x_name="X_Val", y_name="Y_Val")
        entry = {"title": "Test Plot", "result": res}
        widget = FittedLinePlotChartWidget(entry)
        widget.resize(840, 520)
        widget.show()
        self.app.processEvents()

        self.assertGreaterEqual(len(widget.hit_regions), len(self.x))
        widget.close()
        widget.deleteLater()
        self.app.processEvents()

    def test_dialogs_lifecycle(self):
        opts = default_fitted_line_plot_options()

        # Options dialog
        d_opt = FittedLinePlotOptionsDialog(None, opts)
        d_opt.chk_ci.setChecked(True)
        d_opt.chk_pi.setChecked(False)
        d_opt.spin_conf.setValue(90.0)
        d_opt.validate()
        self.assertTrue(d_opt.options["ci"])
        self.assertFalse(d_opt.options["pi"])
        self.assertAlmostEqual(d_opt.options["confidence"], 0.90)
        d_opt.close(); d_opt.deleteLater()

        # Graphs dialog
        d_grp = FittedLinePlotGraphsDialog(None, opts)
        d_grp.rdo_std.setChecked(True)
        d_grp.rdo_indiv.setChecked(True)
        d_grp.chk_norm.setChecked(True)
        d_grp.validate()
        self.assertEqual(d_grp.options["residuals_type"], "standardized")
        self.assertEqual(d_grp.options["graphs"], "normal")
        d_grp.close(); d_grp.deleteLater()

        # Storage dialog
        d_str = FittedLinePlotStorageDialog(None, opts)
        d_str.chk_fits.setChecked(True)
        d_str.chk_residuals.setChecked(True)
        d_str.validate()
        self.assertTrue(d_str.options["storage"]["fits"])
        self.assertTrue(d_str.options["storage"]["residuals"])
        d_str.close(); d_str.deleteLater()


if __name__ == "__main__":
    unittest.main()
