"""Unit tests for Analysis of Means (ANOM) matching Minitab 22 specifications."""
import os
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.anom import (
    calculate_anom_normal_1way,
    calculate_anom_normal_2way,
    calculate_anom_binomial,
    calculate_anom_poisson,
)
from statcraft.anom_report import format_anom_report
from statcraft.anom_chart import ANOMChartWidget, SingleANOMCanvas
from statcraft.anom_dialog import ANOMDialog


class TestANOM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Known synthetic benchmark dataset: 3 machines, 5 samples each
        # Machine 1: around 10, Machine 2: around 15, Machine 3: around 30 (outlier)
        self.y_normal = [
            10.1, 10.3, 9.8, 10.2, 9.9,
            14.8, 15.2, 15.0, 14.9, 15.1,
            29.5, 30.1, 30.4, 29.8, 30.2,
        ]
        self.factor_machine = [
            "M1", "M1", "M1", "M1", "M1",
            "M2", "M2", "M2", "M2", "M2",
            "M3", "M3", "M3", "M3", "M3",
        ]
        self.factor_operator = [
            "Op1", "Op2", "Op1", "Op2", "Op1",
            "Op1", "Op2", "Op1", "Op2", "Op1",
            "Op1", "Op2", "Op1", "Op2", "Op1",
        ]
        # Defectives data for Binomial ANOM
        self.defectives = [3, 4, 18, 5]
        self.batches = ["B1", "B2", "B3", "B4"]

        # Flaw counts for Poisson ANOM
        self.flaws = [2, 1, 15, 3]
        self.lots = ["L1", "L2", "L3", "L4"]

        self.ws = Worksheet("ANOM_Data", [
            Column("Measurement", "number", self.y_normal),
            Column("Machine", "text", self.factor_machine),
            Column("Operator", "text", self.factor_operator),
            Column("Defectives", "number", self.defectives + [None] * 11),
            Column("Batch", "text", self.batches + [None] * 11),
            Column("Flaws", "number", self.flaws + [None] * 11),
            Column("Lot", "text", self.lots + [None] * 11),
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def tearDown(self):
        self.app.processEvents()

    def test_normal_1way_calculations(self):
        res = calculate_anom_normal_1way(self.y_normal, self.factor_machine, alpha=0.05)
        self.assertEqual(res["analysis"], "anom")
        self.assertEqual(res["distribution"], "normal")
        self.assertEqual(res["type"], "one_way")
        self.assertEqual(res["k"], 3)
        self.assertEqual(res["total_n"], 15)

        # Check grand mean ~ 18.4
        self.assertAlmostEqual(res["grand_mean"], sum(self.y_normal) / 15, places=4)
        self.assertGreater(res["pooled_sd"], 0.0)
        self.assertGreater(res["critical_value"], 2.0)

        # Check levels
        levels = {l["level"]: l for l in res["levels"]}
        self.assertEqual(set(levels.keys()), {"M1", "M2", "M3"})
        self.assertAlmostEqual(levels["M1"]["mean"], 10.06, places=2)
        self.assertAlmostEqual(levels["M3"]["mean"], 30.0, places=1)

        # M1 (10.06) is far below grand mean (18.4), M3 (30.0) is far above -> significant
        self.assertTrue(levels["M1"]["significant"])
        self.assertTrue(levels["M3"]["significant"])
        self.assertTrue(res["outliers_detected"])

    def test_binomial_calculations(self):
        res = calculate_anom_binomial(self.defectives, self.batches, sample_size=100, alpha=0.05)
        self.assertEqual(res["distribution"], "binomial")
        self.assertEqual(res["k"], 4)
        self.assertEqual(res["total_events"], 30)
        self.assertEqual(res["total_n"], 400)
        self.assertAlmostEqual(res["grand_mean"], 30 / 400, places=4)

        levels = {l["level"]: l for l in res["levels"]}
        # Batch 3 has 18/100 = 0.18, grand mean is 0.075 -> should be out of bounds
        self.assertTrue(levels["B3"]["significant"])
        self.assertTrue(res["outliers_detected"])

    def test_poisson_calculations(self):
        res = calculate_anom_poisson(self.flaws, self.lots, sample_size=1.0, alpha=0.05)
        self.assertEqual(res["distribution"], "poisson")
        self.assertEqual(res["k"], 4)
        self.assertEqual(res["total_counts"], 21)
        self.assertEqual(res["total_units"], 4.0)

        levels = {l["level"]: l for l in res["levels"]}
        # Lot 3 has 15 flaws -> significant
        self.assertTrue(levels["L3"]["significant"])
        self.assertTrue(res["outliers_detected"])

    def test_normal_2way_calculations(self):
        res = calculate_anom_normal_2way(
            self.y_normal, self.factor_machine, self.factor_operator,
            alpha=0.05, factor1_name="Machine", factor2_name="Operator"
        )
        self.assertEqual(res["type"], "two_way")
        self.assertIn("factor1", res)
        self.assertIn("factor2", res)
        self.assertIn("interaction", res)

        f1 = res["factor1"]
        self.assertEqual(f1["k"], 3)
        self.assertTrue(f1["outliers_detected"])

        f2 = res["factor2"]
        self.assertEqual(f2["k"], 2)

        inter = res["interaction"]
        self.assertEqual(len(inter["levels"]), 6)

    def test_report_formatting(self):
        # 1-way report
        res1 = calculate_anom_normal_1way(self.y_normal, self.factor_machine, alpha=0.05)
        rep1 = format_anom_report(res1)
        self.assertIn("ANALYSIS OF MEANS", rep1)
        self.assertIn("Center Line:", rep1)
        self.assertIn("Critical Value:", rep1)
        self.assertIn("M1", rep1)
        self.assertIn("M3", rep1)

        # 2-way report
        res2 = calculate_anom_normal_2way(
            self.y_normal, self.factor_machine, self.factor_operator,
            alpha=0.05, factor1_name="Machine", factor2_name="Operator"
        )
        rep2 = format_anom_report(res2)
        self.assertIn("TWO-WAY ANALYSIS OF MEANS", rep2)
        self.assertIn("Main Effects: Machine", rep2)
        self.assertIn("Two-Way Interaction Effects", rep2)

    def test_app_integration_and_recipe(self):
        # Normal 1-way
        entry = self.p.anom(0, 1, distribution="normal", alpha=0.05)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "anom")
        self.assertIn("connected_analysis", entry)

        conn = entry["connected_analysis"]
        self.assertEqual(conn["analysis_type"], "anom")
        self.assertIn("r_script", conn)
        self.assertIn("tapply(", conn["r_script"])
        self.assertIn("qt(", conn["r_script"])

    def test_chart_widget_rendering(self):
        # 1-way
        res1 = calculate_anom_normal_1way(self.y_normal, self.factor_machine, alpha=0.05)
        entry1 = {"title": "ANOM Test", "result": res1}
        widget1 = ANOMChartWidget(entry1)
        widget1.resize(700, 450)
        widget1.show()
        self.app.processEvents()

        self.assertGreaterEqual(len(widget1.current_canvas.hit_regions), 3)
        widget1.close()
        widget1.deleteLater()
        self.app.processEvents()

        # 2-way
        res2 = calculate_anom_normal_2way(self.y_normal, self.factor_machine, self.factor_operator, alpha=0.05)
        entry2 = {"title": "ANOM 2-Way Test", "result": res2}
        widget2 = ANOMChartWidget(entry2)
        widget2.resize(700, 450)
        widget2.show()
        self.app.processEvents()
        widget2.close()
        widget2.deleteLater()
        self.app.processEvents()

    def test_dialog_lifecycle(self):
        dlg = ANOMDialog(self.ws)
        dlg.txt_response.setText("Measurement")
        dlg.txt_factor1.setText("Machine")
        dlg._on_ok()
        self.assertIsNotNone(dlg.selected_params)
        self.assertEqual(dlg.selected_params["response_index"], 0)
        self.assertEqual(dlg.selected_params["factor1_index"], 1)
        self.assertEqual(dlg.selected_params["distribution"], "normal")
        dlg.close()
        dlg.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
