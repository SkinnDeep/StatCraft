"""Unit tests for Symmetry Plot computational engine, report, chart, and dialogs."""
import math
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.model import Worksheet, Column
from statcraft.symmetry_plot import compute_symmetry_plot
from statcraft.symmetry_plot_report import generate_symmetry_plot_report
from statcraft.symmetry_plot_chart import SymmetryPlotChartWidget
from statcraft.symmetry_plot_dialogs import SymmetryPlotDialog, SymmetryPlotOptionsDialog
from statcraft.app import Presenter, format_entry
import statcraft.recipes as recipes


class TestSymmetryPlotComputation(unittest.TestCase):
    def test_symmetric_distribution(self):
        # Perfectly symmetric data around 50
        vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
        res = compute_symmetry_plot(vals)

        self.assertEqual(res["n"], 9)
        self.assertEqual(res["n_missing"], 0)
        self.assertEqual(res["k_pairs"], 4)
        self.assertAlmostEqual(res["median"], 50.0, places=6)
        self.assertAlmostEqual(res["mean"], 50.0, places=6)
        self.assertAlmostEqual(res["skewness"], 0.0, places=6)
        self.assertEqual(res["skew_label"], "Symmetric")

        # In perfectly symmetric data, lower_dist == upper_dist for all pairs
        for pt in res["points_table"]:
            self.assertAlmostEqual(pt["lower_dist"], pt["upper_dist"], places=6)
            self.assertAlmostEqual(pt["discrepancy"], 0.0, places=6)

    def test_right_skewed_distribution(self):
        # Right-skewed data: most values clustered low, long right tail
        vals = [1.0, 1.2, 1.5, 1.8, 2.0, 2.3, 2.8, 4.5, 9.0, 22.0]
        res = compute_symmetry_plot(vals)

        self.assertEqual(res["n"], 10)
        self.assertGreater(res["skewness"], 0.5)
        self.assertEqual(res["skew_label"], "Skewed Right")
        self.assertIn("skewed right", res["assessment"])

        # Check that upper distances exceed lower distances
        p_data = res["plot_data"]
        mean_u = sum(p_data["lower_distances"]) / len(p_data["lower_distances"])
        mean_v = sum(p_data["upper_distances"]) / len(p_data["upper_distances"])
        self.assertGreater(mean_v, mean_u)

    def test_missing_and_invalid_values(self):
        vals = [None, 10.0, float('nan'), 20.0, 30.0, "invalid", 40.0, 50.0]
        res = compute_symmetry_plot(vals)
        self.assertEqual(res["n"], 5)
        self.assertEqual(res["n_missing"], 3)
        self.assertAlmostEqual(res["median"], 30.0, places=6)

    def test_insufficient_data_error(self):
        with self.assertRaises(ValueError):
            compute_symmetry_plot([1.0, 2.0, 3.0])

    def test_report_generation(self):
        vals = [12.0, 15.0, 18.0, 22.0, 25.0, 30.0, 35.0, 50.0]
        res = compute_symmetry_plot(vals, settings={"title": "Custom Symmetry Assessment"})
        rpt = generate_symmetry_plot_report(res, variable_name="Thickness")
        self.assertIn("Custom Symmetry Assessment", rpt)
        self.assertIn("Summary Statistics", rpt)
        self.assertIn("Sample Size (N)", rpt)
        self.assertIn("Skewness", rpt)
        self.assertIn("Distance from Median Table", rpt)
        self.assertIn("Lower Dist", rpt)


class TestSymmetryPlotUIAndPresenter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def setUp(self):
        self.ws = Worksheet("Quality Testing", [
            Column("ID", "text", ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]),
            Column("Measurement", "number", [10.2, 12.5, 14.8, 15.1, 16.0, 16.4, 17.2, 18.9, 21.3, 26.5]),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_presenter_symmetry_plot_and_recipe(self):
        entry = self.presenter.symmetry_plot(
            column_index=1,
            settings={"show_line": True},
        )
        self.assertIsNotNone(entry)
        res = entry["result"]
        self.assertEqual(res["analysis"], "symmetry_plot")
        self.assertEqual(res["graph"], "symmetry_plot")
        self.assertIn("Symmetry Plot", entry["title"])

        # Formatted session report
        rpt = format_entry(entry)
        self.assertIn("Symmetry Plot", rpt)
        self.assertIn("Summary Statistics", rpt)

        # Recipe verification
        recipe = entry["recipe"]
        self.assertEqual(recipe["action"], "symmetry_plot")
        self.assertEqual(recipe["parameters"]["column_index"], 1)
        self.assertIn("symmetry_plot", recipes.FIELDS)

        # Recipe columns dependency
        cols = recipes.columns(recipe)
        self.assertEqual(cols, [1])

        # Rerun result
        rerun_entry = self.presenter.rerun_result(entry)
        self.assertIsNotNone(rerun_entry)
        self.assertEqual(rerun_entry["result"]["analysis"], "symmetry_plot")

    def test_chart_widget_rendering(self):
        vals = [10.2, 12.5, 14.8, 15.1, 16.0, 16.4, 17.2, 18.9, 21.3, 26.5]
        res = compute_symmetry_plot(vals)
        chart = SymmetryPlotChartWidget(res)
        chart.resize(750, 550)
        chart.show()
        QCoreApplication.processEvents()

        pm = chart.render_chart_pixmap(width=750, height=550)
        self.assertFalse(pm.isNull())
        self.assertEqual(pm.width(), 750)
        self.assertEqual(pm.height(), 550)
        chart.close()

    def test_dialogs(self):
        dlg = SymmetryPlotDialog(self.ws)
        dlg.edit_vars.setText("C2")

        # Test options sub-dialog
        opt_dlg = SymmetryPlotOptionsDialog(dlg.options, parent=dlg)
        opt_dlg.chk_line.setChecked(True)
        opt_dlg.edit_title.setText("Thickness Symmetry Evaluation")
        opt_dlg.accept()
        dlg.options.update(opt_dlg.get_options())
        self.assertEqual(dlg.options["title"], "Thickness Symmetry Evaluation")

        dlg._on_ok()
        p = dlg.result_params
        self.assertIsNotNone(p)
        self.assertEqual(p["columns"], [1])
        self.assertTrue(p["settings"]["show_line"])
        self.assertEqual(p["settings"]["title"], "Thickness Symmetry Evaluation")


if __name__ == '__main__':
    unittest.main()
