"""Unit tests for Acceptance Sampling by Variables computational engine, report, chart, and dialog."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.acceptance_sampling_variables import solve_variables_sampling_plan
from statcraft.acceptance_sampling_variables_report import generate_acceptance_sampling_variables_report
from statcraft.acceptance_sampling_variables_dialogs import AcceptanceSamplingVariablesDialog
from statcraft.acceptance_sampling_variables_chart import AcceptanceSamplingVariablesChartWidget
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft import recipes


class TestAcceptanceSamplingVariables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_solve_plan_unknown_sigma_lower(self):
        # AQL 1.5%, RQL 5.0%, alpha 0.05, beta 0.10, LSL 10.0
        plan = solve_variables_sampling_plan(
            aql=0.015,
            rql=0.05,
            alpha=0.05,
            beta=0.10,
            lsl=10.0,
        )
        self.assertEqual(plan["analysis"], "acceptance_sampling_variables")
        self.assertEqual(plan["spec_type"], "lower")
        self.assertFalse(plan["sigma_known"])
        self.assertGreater(plan["n"], 20)
        self.assertGreater(plan["k"], 1.5)
        self.assertLess(plan["k"], 2.2)

        # Curves
        self.assertEqual(len(plan["oc_curve"]), 100)
        self.assertEqual(len(plan["aoq_curve"]), 100)
        self.assertEqual(len(plan["ati_curve"]), 100)

        # First point near zero defective should have Pa near 1.0
        self.assertAlmostEqual(plan["oc_curve"][0]["pa"], 1.0, places=2)

    def test_solve_plan_known_sigma_double(self):
        # Known sigma = 2.0, double limits: LSL 50, USL 70
        plan = solve_variables_sampling_plan(
            aql=0.01,
            rql=0.04,
            alpha=0.05,
            beta=0.10,
            lsl=50.0,
            usl=70.0,
            sigma=2.0,
            lot_size=5000,
        )
        self.assertTrue(plan["sigma_known"])
        self.assertEqual(plan["spec_type"], "double")
        self.assertEqual(plan["lot_size"], 5000)
        self.assertGreater(plan["aoql"], 0.0)

    def test_invalid_parameters(self):
        # AQL >= RQL
        with self.assertRaises(ValueError):
            solve_variables_sampling_plan(aql=0.05, rql=0.02, lsl=10)

        # No spec limits
        with self.assertRaises(ValueError):
            solve_variables_sampling_plan(aql=0.01, rql=0.05)

        # LSL >= USL
        with self.assertRaises(ValueError):
            solve_variables_sampling_plan(aql=0.01, rql=0.05, lsl=50, usl=40)

        # Negative sigma
        with self.assertRaises(ValueError):
            solve_variables_sampling_plan(aql=0.01, rql=0.05, lsl=10, sigma=-1)

    def test_report_generation(self):
        plan = solve_variables_sampling_plan(
            aql=0.015,
            rql=0.05,
            lsl=10.0,
            lot_size=2000,
        )
        report = generate_acceptance_sampling_variables_report(plan)
        self.assertIn("Acceptance Sampling by Variables", report)
        self.assertIn("Sample Size (n):", report)
        self.assertIn("Critical Distance (k):", report)
        self.assertIn("Accept lot if (Mean - LSL)", report)
        self.assertIn("Risk Analysis:", report)
        self.assertIn("AQL (Acceptable Quality)", report)
        self.assertIn("AOQL", report)

    def test_presenter_integration(self):
        pres = Presenter()
        st = {
            "aql": 0.015,
            "rql": 0.05,
            "lsl": 10.0,
            "usl": 20.0,
            "lot_size": 1000,
        }
        entry = pres.acceptance_sampling_variables(settings=st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "acceptance_sampling_variables")
        self.assertEqual(entry["result"]["analysis"], "acceptance_sampling_variables")

        text = format_entry(entry)
        self.assertIn("Acceptance Sampling by Variables", text)

        cols = recipes.columns(entry["recipe"])
        self.assertEqual(cols, [])

    def test_chart_widget_rendering(self):
        plan = solve_variables_sampling_plan(
            aql=0.015,
            rql=0.05,
            lsl=10.0,
            lot_size=1000,
        )
        entry = {"recipe": {"action": "acceptance_sampling_variables"}, "result": plan}
        widget = AcceptanceSamplingVariablesChartWidget(entry)
        self.assertIsNotNone(widget)

        # Test curve switching
        widget._set_curve("aoq")
        self.assertEqual(widget.active_curve, "aoq")
        widget._set_curve("ati")
        self.assertEqual(widget.active_curve, "ati")
        widget._set_curve("oc")
        self.assertEqual(widget.active_curve, "oc")

        from PySide6.QtGui import QPixmap
        pm = QPixmap(700, 480)
        widget.render(pm)
        self.assertFalse(pm.isNull())

    def test_dialog_validation(self):
        dlg = AcceptanceSamplingVariablesDialog()
        self.assertEqual(dlg.windowTitle(), "Acceptance Sampling by Variables")
        dlg.combo_spec_type.setCurrentIndex(0)
        dlg.edit_lsl.setText("15.0")
        dlg.spin_aql.setValue(1.5)
        dlg.spin_rql.setValue(5.0)
        dlg._on_accept()
        self.assertIsNotNone(dlg.settings)
        self.assertEqual(dlg.settings["lsl"], 15.0)
        self.assertAlmostEqual(dlg.settings["aql"], 0.015)
        self.assertAlmostEqual(dlg.settings["rql"], 0.05)


if __name__ == "__main__":
    unittest.main()
