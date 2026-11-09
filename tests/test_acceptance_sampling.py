"""Unit tests for Acceptance Sampling by Attributes computational engine, report, chart, and dialogs."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.acceptance_sampling import (
    solve_attribute_sampling_plan,
    compute_acceptance_sampling_attributes,
)
from statcraft.acceptance_sampling_report import generate_acceptance_sampling_report
from statcraft.acceptance_sampling_chart import AcceptanceSamplingChartWidget
from statcraft.acceptance_sampling_dialogs import AcceptanceSamplingDialog
from statcraft.app import Presenter, format_entry
import statcraft.recipes as recipes


class TestAcceptanceSamplingComputation(unittest.TestCase):
    def test_standard_binomial_sampling_plan(self):
        # Benchmark: AQL = 1% (0.01), RQL = 5% (0.05), Alpha = 0.05, Beta = 0.10
        res = compute_acceptance_sampling_attributes({
            "aql": 0.01,
            "rql": 0.05,
            "alpha": 0.05,
            "beta": 0.10,
        })

        n = res["sample_size"]
        c = res["acceptance_number"]

        self.assertGreater(n, 50)
        self.assertGreaterEqual(c, 1)

        # Realized producer risk and consumer risk conditions
        self.assertGreaterEqual(res["actual_p_accept_aql"], 1.0 - res["target_alpha"] - 0.01)
        self.assertLessEqual(res["actual_p_accept_rql"], res["target_beta"] + 0.01)

        # Curves
        curves = res["curves"]
        self.assertIn("p_values", curves)
        self.assertIn("oc_values", curves)
        self.assertIn("aoq_values", curves)
        self.assertGreater(len(curves["p_values"]), 50)

        # AOQL exists and is non-zero
        self.assertGreater(res["aoql"], 0.0)
        self.assertGreater(res["p_at_aoql"], 0.0)

    def test_finite_lot_size_hypergeometric(self):
        res = compute_acceptance_sampling_attributes({
            "aql": 0.015,
            "rql": 0.08,
            "alpha": 0.05,
            "beta": 0.10,
            "lot_size": 2000,
        })
        self.assertEqual(res["lot_size"], 2000)
        self.assertIsNotNone(res["curves"]["ati_values"])
        self.assertEqual(len(res["curves"]["ati_values"]), len(res["curves"]["p_values"]))

        # ATI starts at n and approaches N as defect rate rises
        n = res["sample_size"]
        self.assertAlmostEqual(res["curves"]["ati_values"][0], n, delta=5.0)
        self.assertGreater(res["curves"]["ati_values"][-1], 1500)

    def test_user_specified_plan_comparison(self):
        res = compute_acceptance_sampling_attributes({
            "aql": 0.01,
            "rql": 0.05,
            "user_n": 80,
            "user_c": 2,
        })
        self.assertEqual(res["sample_size"], 80)
        self.assertEqual(res["acceptance_number"], 2)
        self.assertTrue(res["is_user_plan"])
        self.assertAlmostEqual(res["actual_alpha"], 1.0 - res["actual_p_accept_aql"], places=6)

    def test_validation_errors(self):
        # AQL <= 0
        with self.assertRaises(ValueError):
            solve_attribute_sampling_plan(aql=0.0, rql=0.05)
        # RQL <= AQL
        with self.assertRaises(ValueError):
            solve_attribute_sampling_plan(aql=0.05, rql=0.04)
        # Alpha >= 1
        with self.assertRaises(ValueError):
            solve_attribute_sampling_plan(aql=0.01, rql=0.05, alpha=1.2)

    def test_report_generation(self):
        res = compute_acceptance_sampling_attributes({
            "aql": 0.01,
            "rql": 0.05,
            "alpha": 0.05,
            "beta": 0.10,
            "lot_size": 5000,
            "title": "Vendor Incoming Inspection Plan",
        })
        rpt = generate_acceptance_sampling_report(res)
        self.assertIn("Vendor Incoming Inspection Plan", rpt)
        self.assertIn("Sampling Plan", rpt)
        self.assertIn("Sample Size (n)", rpt)
        self.assertIn("Acceptance Number (c)", rpt)
        self.assertIn("Quality Levels and Risks", rpt)
        self.assertIn("AQL (Acceptable)", rpt)
        self.assertIn("RQL / LTPD (Reject)", rpt)
        self.assertIn("Average Outgoing Quality (AOQ)", rpt)
        self.assertIn("AOQL (Quality Limit)", rpt)


class TestAcceptanceSamplingUIAndPresenter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def setUp(self):
        self.presenter = Presenter()

    def test_presenter_acceptance_sampling_and_recipe(self):
        entry = self.presenter.acceptance_sampling_attributes({
            "aql": 0.01,
            "rql": 0.05,
            "alpha": 0.05,
            "beta": 0.10,
        })
        self.assertIsNotNone(entry)
        res = entry["result"]
        self.assertEqual(res["analysis"], "acceptance_sampling_attributes")
        self.assertEqual(res["graph"], "acceptance_sampling_attributes")
        self.assertIn("Acceptance Sampling by Attributes", entry["title"])

        # Formatted session report
        rpt = format_entry(entry)
        self.assertIn("Acceptance Sampling by Attributes", rpt)
        self.assertIn("Quality Levels and Risks", rpt)

        # Recipe verification
        recipe = entry["recipe"]
        self.assertEqual(recipe["action"], "acceptance_sampling_attributes")
        self.assertIn("acceptance_sampling_attributes", recipes.FIELDS)
        self.assertEqual(recipes.columns(recipe), [])

        # Rerun result
        rerun_entry = self.presenter.rerun_result(entry)
        self.assertIsNotNone(rerun_entry)
        self.assertEqual(rerun_entry["result"]["analysis"], "acceptance_sampling_attributes")

    def test_chart_widget_rendering_and_mode_switching(self):
        res = compute_acceptance_sampling_attributes({
            "aql": 0.01,
            "rql": 0.05,
            "lot_size": 3000,
        })
        chart = AcceptanceSamplingChartWidget(res)
        chart.resize(800, 600)
        chart.show()
        QCoreApplication.processEvents()

        # Render OC curve
        pm_oc = chart.render_chart_pixmap(800, 600)
        self.assertFalse(pm_oc.isNull())

        # Switch to AOQ curve
        chart._select_mode("aoq")
        self.assertEqual(chart.canvas.mode, "aoq")
        pm_aoq = chart.render_chart_pixmap(800, 600)
        self.assertFalse(pm_aoq.isNull())

        # Switch to ATI curve
        chart._select_mode("ati")
        self.assertEqual(chart.canvas.mode, "ati")
        pm_ati = chart.render_chart_pixmap(800, 600)
        self.assertFalse(pm_ati.isNull())

        chart.close()

    def test_dialogs(self):
        dlg = AcceptanceSamplingDialog()
        dlg.edit_aql.setText("1.5")
        dlg.edit_rql.setText("6.0")
        dlg.edit_alpha.setText("0.05")
        dlg.edit_beta.setText("0.10")
        dlg.edit_lot.setText("10000")

        dlg._on_ok()
        p = dlg.result_params
        self.assertIsNotNone(p)
        st = p["settings"]
        self.assertAlmostEqual(st["aql"], 0.015, places=5)
        self.assertAlmostEqual(st["rql"], 0.060, places=5)
        self.assertEqual(st["lot_size"], 10000)


if __name__ == '__main__':
    unittest.main()
