"""Unit and Integration Tests for JMP Fit Y by X platform."""
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.fit_y_by_x_engine import (
    detect_platform,
    compute_bivariate,
    compute_oneway,
    compute_contingency,
    compute_fit_y_by_x
)
from statcraft.fit_y_by_x_report import format_fit_y_by_x_report, get_fit_y_by_x_structured_tables
from statcraft.fit_y_by_x_chart import FitYByXChartWidget
from statcraft.modern_app import ModernWindow


class FitYByXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["STATCRAFT_TESTING"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Create test worksheet with continuous, discrete/categorical data
        self.ws = Worksheet("TestFitYByX", [
            Column("Continuous_Y", values=[12.5, 14.2, 15.8, 18.1, 19.5, 22.0, 24.3, 26.1, 28.5, 30.2]),
            Column("Continuous_X", values=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]),
            Column("Group_X", values=["A", "A", "A", "B", "B", "B", "C", "C", "C", "C"], kind="text"),
            Column("Category_Y", values=["Pass", "Pass", "Fail", "Pass", "Fail", "Fail", "Pass", "Pass", "Fail", "Pass"], kind="text"),
            Column("Category_X", values=["Shift1", "Shift1", "Shift2", "Shift2", "Shift1", "Shift2", "Shift1", "Shift2", "Shift1", "Shift2"], kind="text")
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_platform_detection(self):
        # Continuous by Continuous
        self.assertEqual(detect_platform(self.ws, 0, 1), "bivariate")
        # Continuous by Categorical
        self.assertEqual(detect_platform(self.ws, 0, 2), "oneway")
        # Categorical by Categorical
        self.assertEqual(detect_platform(self.ws, 3, 4), "contingency")

    def test_bivariate_computation(self):
        res = compute_bivariate(
            x_raw=self.ws.columns[1].values,
            y_raw=self.ws.columns[0].values,
            x_name="Continuous_X",
            y_name="Continuous_Y"
        )
        self.assertEqual(res["platform"], "bivariate")
        self.assertGreater(res["r_sq"], 0.95)  # Highly linear test data
        self.assertIn("ellipse_95", res["ellipses"])
        self.assertIn("ellipse_50", res["ellipses"])
        self.assertEqual(len(res["ellipses"]["ellipse_95"]["x"]), 120)
        self.assertGreater(len(res["parameter_estimates"]), 0)
        self.assertEqual(res["anova"]["df_model"], 1)
        self.assertEqual(res["anova"]["df_error"], 8)

        # Check report formatting
        rep = format_fit_y_by_x_report({"result": res})
        self.assertIn("Bivariate Fit of Continuous_Y By Continuous_X", rep)
        self.assertIn("RSquare", rep)

        # Check structured tables
        tables = get_fit_y_by_x_structured_tables(res)
        self.assertTrue(any(t["title"] == "Summary of Fit" for t in tables))
        self.assertTrue(any(t["title"] == "Analysis of Variance" for t in tables))

    def test_oneway_computation_and_means_diamonds(self):
        res = compute_oneway(
            x_raw=self.ws.columns[2].values,
            y_raw=self.ws.columns[0].values,
            x_name="Group_X",
            y_name="Continuous_Y"
        )
        self.assertEqual(res["platform"], "oneway")
        self.assertEqual(len(res["group_stats"]), 3)
        self.assertEqual(len(res["diamonds"]), 3)

        # Verify Means Diamonds geometry
        for d in res["diamonds"]:
            self.assertIn("ci_lower", d)
            self.assertIn("ci_upper", d)
            self.assertIn("polygon", d)
            self.assertEqual(len(d["polygon"]), 4)  # 4 vertices of diamond

        # Verify Tukey-Kramer HSD
        self.assertEqual(len(res["tukey_hsd"]), 3)  # 3 choose 2 pairs
        for pair in res["tukey_hsd"]:
            self.assertIn("difference", pair)
            self.assertIn("lower_cl", pair)
            self.assertIn("upper_cl", pair)

        # Check report formatting
        rep = format_fit_y_by_x_report({"result": res})
        self.assertIn("Oneway Analysis of Continuous_Y By Group_X", rep)
        self.assertIn("Tukey-Kramer HSD", rep)

        # Check structured tables
        tables = get_fit_y_by_x_structured_tables(res)
        self.assertTrue(any("Means and Standard Deviations" in t["title"] for t in tables))
        self.assertTrue(any("Tukey-Kramer HSD" in t["title"] for t in tables))

    def test_contingency_computation_and_mosaic_tiles(self):
        res = compute_contingency(
            x_raw=self.ws.columns[4].values,
            y_raw=self.ws.columns[3].values,
            x_name="Category_X",
            y_name="Category_Y"
        )
        self.assertEqual(res["platform"], "contingency")
        self.assertIn("chi2", res)
        self.assertIn("g2", res)
        self.assertEqual(res["df"], 1)
        self.assertGreater(len(res["mosaic_tiles"]), 0)

        # Verify mosaic geometry
        for tile in res["mosaic_tiles"]:
            self.assertGreater(tile["width"], 0)
            self.assertGreater(tile["height"], 0)
            self.assertIn("col_pct", tile)

        # Check report formatting
        rep = format_fit_y_by_x_report({"result": res})
        self.assertIn("Contingency Analysis of Category_Y By Category_X", rep)
        self.assertIn("Pearson", rep)

    def test_presenter_integration_and_ui_rendering(self):
        # 1. Bivariate through Presenter
        biv_entry = self.p.fit_y_by_x(y_index=0, x_index=1)
        self.assertEqual(biv_entry["recipe"]["action"], "fit_y_by_x")
        self.assertEqual(biv_entry["result"]["platform"], "bivariate")

        # 2. Oneway through Presenter
        oneway_entry = self.p.fit_y_by_x(y_index=0, x_index=2)
        self.assertEqual(oneway_entry["result"]["platform"], "oneway")

        # 3. Offscreen Qt Chart Rendering
        chart_biv = FitYByXChartWidget(biv_entry)
        chart_biv.resize(800, 600)
        chart_biv.show()
        self.app.processEvents()
        pix_biv = chart_biv.grab()
        self.assertFalse(pix_biv.isNull())
        chart_biv.close()

        chart_oneway = FitYByXChartWidget(oneway_entry)
        chart_oneway.resize(800, 600)
        chart_oneway.show()
        self.app.processEvents()
        pix_oneway = chart_oneway.grab()
        self.assertFalse(pix_oneway.isNull())
        chart_oneway.close()

        # 4. ModernWindow show_result integration
        w = ModernWindow(self.p)
        w.resize(1000, 700)
        w.show()
        self.app.processEvents()
        w.show_result(biv_entry)
        self.app.processEvents()

        tab_names = [w.result_tabs.tabText(i) for i in range(w.result_tabs.count())]
        self.assertIn("Report", tab_names)
        self.assertIn("Graph", tab_names)
        w.close()
        w.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
