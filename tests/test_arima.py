"""Unit tests for Box-Jenkins ARIMA computational engine, report, dialog, and presenter."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.arima import fit_arima, difference_series, undifference_forecasts
from statcraft.arima_report import generate_arima_report
from statcraft.arima_dialogs import ARIMADialog
from statcraft.time_series_chart import TimeSeriesChartWidget
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft import recipes


class TestARIMA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Simulated stationary AR(1) process with phi = 0.6, mean = 20
        # 30 observations
        np_rng = [
            20.5, 21.2, 19.8, 20.1, 21.5, 22.0, 21.1, 20.3, 19.5, 19.2,
            20.4, 21.0, 20.8, 19.9, 19.4, 20.1, 20.7, 21.3, 20.9, 20.2,
            19.7, 20.0, 20.6, 21.1, 20.5, 19.8, 19.3, 20.2, 20.9, 21.4
        ]
        self.series = np_rng

    def test_difference_and_undifference(self):
        y = [10.0, 12.0, 15.0, 19.0, 24.0]
        w = difference_series(y, d=1)
        self.assertEqual(list(w), [2.0, 3.0, 4.0, 5.0])

        fc_diff = [6.0, 7.0]
        y_fc = undifference_forecasts(y, fc_diff, d=1)
        self.assertEqual(y_fc, [30.0, 37.0])

    def test_fit_ar1_model(self):
        res = fit_arima(
            self.series,
            p=1,
            d=0,
            q=0,
            include_constant=True,
            forecasts=3,
            conf_level=95.0,
            variable_name="Temp",
        )
        self.assertEqual(res["analysis"], "arima")
        self.assertEqual(res["p"], 1)
        self.assertEqual(res["d"], 0)
        self.assertEqual(res["q"], 0)
        self.assertEqual(res["n_orig"], 30)
        self.assertGreater(res["ss"], 0.0)
        self.assertGreater(res["ms"], 0.0)

        # Estimates
        estimates = res["estimates"]
        self.assertEqual(len(estimates), 2)  # AR 1 and Constant
        types = [e["type"] for e in estimates]
        self.assertIn("AR  1", types)
        self.assertIn("Constant", types)

        ar1_est = next(e for e in estimates if e["type"] == "AR  1")
        self.assertGreater(ar1_est["se"], 0.0)

        # Forecasts
        fcs = res["forecasts"]
        self.assertEqual(len(fcs), 3)
        for fc in fcs:
            self.assertGreater(fc["forecast"], 15.0)
            self.assertLess(fc["forecast"], 25.0)
            self.assertLess(fc["lower"], fc["forecast"])
            self.assertGreater(fc["upper"], fc["forecast"])

    def test_fit_ima_model(self):
        res = fit_arima(
            self.series,
            p=0,
            d=1,
            q=1,
            include_constant=False,
            forecasts=2,
            variable_name="Units",
        )
        self.assertEqual(res["d"], 1)
        self.assertEqual(res["q"], 1)
        self.assertEqual(len(res["estimates"]), 1)
        self.assertEqual(res["estimates"][0]["type"], "MA  1")

    def test_invalid_parameters(self):
        # Too short series
        with self.assertRaises(ValueError):
            fit_arima([1.0, 2.0, 3.0], p=2, q=2)

    def test_report_generation(self):
        res = fit_arima(
            self.series,
            p=1,
            d=0,
            q=0,
            include_constant=True,
            forecasts=2,
            variable_name="Temp",
        )
        report = generate_arima_report(res)
        self.assertIn("ARIMA(1,0,0): Temp", report)
        self.assertIn("Final Estimates of Parameters", report)
        self.assertIn("AR  1", report)
        self.assertIn("Constant", report)
        self.assertIn("Number of observations: 30", report)
        self.assertIn("Forecasts (95% Confidence Level)", report)

    def test_presenter_integration(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Temp", kind="number", values=self.series))
        pres = Presenter()
        pres.worksheet = ws

        st = {
            "series_index": 0,
            "p": 1,
            "d": 0,
            "q": 0,
            "include_constant": True,
            "forecasts": 3,
            "store_fits": True,
            "store_residuals": True,
            "store_forecasts": True,
        }
        entry = pres.arima(settings=st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "arima")
        self.assertEqual(entry["result"]["analysis"], "arima")

        # Storage columns
        col_names = [c.name for c in ws.columns]
        self.assertIn("FITT_Temp", col_names)
        self.assertIn("RESI_Temp", col_names)
        self.assertIn("FORE_Temp", col_names)

        # Formatting
        text = format_entry(entry)
        self.assertIn("ARIMA(1,0,0): Temp", text)

        # Recipe columns
        cols = recipes.columns(entry["recipe"])
        self.assertEqual(cols, [0])

    def test_chart_widget_rendering(self):
        res = fit_arima(
            self.series,
            p=1,
            d=0,
            q=0,
            include_constant=True,
            forecasts=3,
            variable_name="Temp",
        )
        entry = {"recipe": {"action": "arima"}, "result": res}
        widget = TimeSeriesChartWidget(entry)
        self.assertIsNotNone(widget)

        from PySide6.QtGui import QPixmap
        pm = QPixmap(780, 480)
        widget.render(pm)
        self.assertFalse(pm.isNull())

    def test_dialog_validation(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Temp", kind="number", values=self.series))
        dlg = ARIMADialog(ws)
        self.assertEqual(dlg.windowTitle(), "ARIMA")
        dlg.edit_series.setText("Temp")
        dlg.spin_p.setValue(1)
        dlg.spin_d.setValue(0)
        dlg.spin_q.setValue(0)
        dlg.chk_constant.setChecked(True)
        dlg._on_accept()
        self.assertIsNotNone(dlg.settings)
        self.assertEqual(dlg.settings["series_index"], 0)
        self.assertEqual(dlg.settings["p"], 1)


if __name__ == "__main__":
    unittest.main()
