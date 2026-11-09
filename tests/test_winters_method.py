"""Unit tests for Winters' Method Triple Exponential Smoothing computational engine, report, chart, and dialog."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.winters_method import winters_method
from statcraft.winters_method_report import generate_winters_method_report
from statcraft.winters_method_dialogs import WintersMethodDialog
from statcraft.time_series_chart import TimeSeriesChartWidget
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft import recipes


class TestWintersMethod(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Classic seasonal time series with upward trend and period 4 (quarterly)
        # 16 observations: 4 full cycles
        self.quarterly_data = [
            105, 135, 120, 100,  # Year 1
            110, 142, 125, 105,  # Year 2
            118, 150, 132, 112,  # Year 3
            125, 160, 140, 120,  # Year 4
        ]

    def test_multiplicative_custom_weights(self):
        res = winters_method(
            self.quarterly_data,
            season_length=4,
            model="multiplicative",
            alpha=0.2,
            gamma=0.2,
            delta=0.2,
            forecasts=4,
            conf_level=95.0,
            variable_name="Sales",
        )
        self.assertEqual(res["analysis"], "winters_method")
        self.assertEqual(res["model"], "multiplicative")
        self.assertEqual(res["season_length"], 4)
        self.assertEqual(res["n"], 16)
        self.assertAlmostEqual(res["alpha"], 0.2)
        self.assertAlmostEqual(res["gamma"], 0.2)
        self.assertAlmostEqual(res["delta"], 0.2)
        self.assertFalse(res["is_optimal"])

        self.assertEqual(len(res["fitted"]), 16)
        self.assertEqual(len(res["residuals"]), 16)
        self.assertEqual(len(res["levels"]), 16)
        self.assertEqual(len(res["trends"]), 16)
        self.assertEqual(len(res["seasonals"]), 4)

        # Accuracy
        acc = res["accuracy"]
        self.assertGreater(acc["mape"], 0)
        self.assertGreater(acc["mad"], 0)
        self.assertGreater(acc["msd"], 0)

        # Forecasts
        fcs = res["forecasts"]
        self.assertEqual(len(fcs), 4)
        for i, fc in enumerate(fcs):
            self.assertEqual(fc["period"], 17 + i)
            self.assertGreater(fc["forecast"], 100)
            self.assertLess(fc["lower"], fc["forecast"])
            self.assertGreater(fc["upper"], fc["forecast"])

    def test_additive_optimal_weights(self):
        res = winters_method(
            self.quarterly_data,
            season_length=4,
            model="additive",
            alpha=None,
            gamma=None,
            delta=None,
            forecasts=3,
            conf_level=90.0,
            variable_name="Demand",
        )
        self.assertEqual(res["analysis"], "winters_method")
        self.assertEqual(res["model"], "additive")
        self.assertTrue(res["is_optimal"])
        self.assertTrue(0.001 <= res["alpha"] <= 0.999)
        self.assertTrue(0.001 <= res["gamma"] <= 0.999)
        self.assertTrue(0.001 <= res["delta"] <= 0.999)

        self.assertEqual(len(res["forecasts"]), 3)
        self.assertAlmostEqual(res["conf_level"], 90.0)

    def test_invalid_parameters(self):
        # Fewer than 2 cycles
        with self.assertRaises(ValueError):
            winters_method([1, 2, 3, 4], season_length=4)

        # Season length < 2
        with self.assertRaises(ValueError):
            winters_method(self.quarterly_data, season_length=1)

        # Unknown model
        with self.assertRaises(ValueError):
            winters_method(self.quarterly_data, season_length=4, model="unknown")

        # Non-positive values for multiplicative
        with self.assertRaises(ValueError):
            bad_data = list(self.quarterly_data)
            bad_data[0] = -5.0
            winters_method(bad_data, season_length=4, model="multiplicative")

    def test_report_generation(self):
        res = winters_method(
            self.quarterly_data,
            season_length=4,
            model="multiplicative",
            alpha=0.3,
            gamma=0.1,
            delta=0.2,
            forecasts=2,
            variable_name="Revenue",
        )
        report = generate_winters_method_report(res)
        self.assertIn("Winters' Method Plot for Revenue", report)
        self.assertIn("Model: Multiplicative", report)
        self.assertIn("Seasonal Length: 4", report)
        self.assertIn("Accuracy Measures", report)
        self.assertIn("Forecasts (95% Confidence Level)", report)
        self.assertIn("Period", report)

    def test_presenter_integration(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Units", kind="number", values=self.quarterly_data))
        pres = Presenter()
        pres.worksheet = ws

        st = {
            "series_index": 0,
            "season_length": 4,
            "model": "multiplicative",
            "alpha": 0.2,
            "gamma": 0.2,
            "delta": 0.2,
            "forecasts": 2,
            "store_fits": True,
            "store_residuals": True,
            "store_forecasts": True,
        }
        entry = pres.winters_method(settings=st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "winters_method")
        self.assertEqual(entry["result"]["analysis"], "winters_method")

        # Verify storage columns
        col_names = [c.name for c in ws.columns]
        self.assertIn("SMOO_Units", col_names)
        self.assertIn("RESI_Units", col_names)
        self.assertIn("FORE_Units", col_names)

        # Verify formatting
        text = format_entry(entry)
        self.assertIn("Winters' Method Plot for Units", text)

        # Verify recipe columns
        cols = recipes.columns(entry["recipe"])
        self.assertEqual(cols, [0])

    def test_chart_widget_rendering(self):
        res = winters_method(
            self.quarterly_data,
            season_length=4,
            model="multiplicative",
            alpha=0.2,
            gamma=0.2,
            delta=0.2,
            forecasts=4,
            variable_name="QuarterlySales",
        )
        entry = {"recipe": {"action": "winters_method"}, "result": res}
        widget = TimeSeriesChartWidget(entry)
        self.assertIsNotNone(widget)
        widget.resize(780, 480)
        from PySide6.QtGui import QPixmap, QPainter
        pm = QPixmap(widget.size())
        widget.render(pm)
        self.assertFalse(pm.isNull())

    def test_dialog_initialization(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="QuarterlySales", kind="number", values=self.quarterly_data))
        dlg = WintersMethodDialog(ws)
        self.assertEqual(dlg.windowTitle(), "Winters' Method")
        dlg.edit_series.setText("QuarterlySales")
        dlg.spin_season.setValue(4)
        dlg.rb_multiplicative.setChecked(True)
        dlg.rb_optimal.setChecked(True)
        dlg.chk_fc.setChecked(True)
        dlg.spin_fc.setValue(4)
        dlg._on_accept()
        self.assertTrue(hasattr(dlg, "settings"))
        self.assertEqual(dlg.settings["series_index"], 0)
        self.assertEqual(dlg.settings["season_length"], 4)
        self.assertEqual(dlg.settings["model"], "multiplicative")
        self.assertEqual(dlg.settings["forecasts"], 4)


if __name__ == "__main__":
    unittest.main()
