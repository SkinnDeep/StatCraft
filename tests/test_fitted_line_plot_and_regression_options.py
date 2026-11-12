import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit

_app = QApplication.instance() or QApplication(sys.argv)


def _tab_titles(tab_widget):
    return [tab_widget.tabText(i) for i in range(tab_widget.count())]


class TestFittedLinePlotAndRegressionOptions(unittest.TestCase):
    def setUp(self):
        from statcraft.modern_app import ModernWindow

        self.win = ModernWindow()
        ws = self.win.presenter.worksheet
        ws.columns[0].name = "X"
        ws.columns[0].kind = "number"
        ws.columns[0].values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        ws.columns[1].name = "Y"
        ws.columns[1].kind = "number"
        ws.columns[1].values = [2.1, 4.3, 5.8, 8.2, 10.1, 11.7, 14.2, 19.5]
        self.win.refresh()

    def tearDown(self):
        self.win.close()

    def test_fitted_line_plot_residual_graphs_and_coefficients_storage(self):
        from statcraft.fitted_line_plot_dialog import FittedLinePlotDialog

        dlg = FittedLinePlotDialog(self.win)
        dlg.controls["response_index"].setText("Y")
        dlg.controls["predictor_index"].setText("X")
        dlg.options["graphs"] = "four"
        dlg.options["residuals_type"] = "standardized"
        dlg.options["storage"]["coefficients"] = True
        dlg.validate()
        self.assertIsNotNone(dlg.entry)
        self.win.show_result(dlg.entry)

        titles = _tab_titles(self.win.result_tabs)
        self.assertIn("Graph", titles)
        self.assertIn("Residual Plots", titles)

        # Coefficients (intercept + slope) stored in COEF1
        col_names = [c.name for c in self.win.presenter.worksheet.columns]
        self.assertIn("COEF1", col_names)
        coef_col = next(c for c in self.win.presenter.worksheet.columns if c.name == "COEF1")
        self.assertEqual(len(coef_col.values), 2)

        # None graph option must omit Residual Plots tab
        dlg_none = FittedLinePlotDialog(self.win)
        dlg_none.controls["response_index"].setText("Y")
        dlg_none.controls["predictor_index"].setText("X")
        dlg_none.options["graphs"] = "none"
        dlg_none.validate()
        self.win.show_result(dlg_none.entry)
        titles_none = _tab_titles(self.win.result_tabs)
        self.assertIn("Graph", titles_none)
        self.assertNotIn("Residual Plots", titles_none)

    def test_regression_residual_chart_supports_fits_and_residuals_type(self):
        from statcraft.regression_residual_chart import RegressionResidualChartWidget

        entry = self.win.presenter.fitted_line_plot(
            response_index=1,
            predictor_index=0,
            model_type="linear",
            options={"graphs": "fits", "residuals_type": "deleted"},
        )
        chart = RegressionResidualChartWidget(entry)
        self.assertEqual(len(chart.fitted), 8)
        self.assertEqual(len(chart.std_resids), 8)
        self.assertEqual(chart.std_resids, entry["result"]["del_residuals"])

    def test_fit_regression_model_results_options_filter_output(self):
        from statcraft.regression_dialog import FitRegressionModelDialog
        from statcraft.app import format_entry

        dlg = FitRegressionModelDialog(self.win)
        dlg.controls["response_index"].setText("Y")
        dlg.controls["predictor_indices"].setText("X")
        dlg.options["results"] = {
            "equation": False,
            "summary": False,
            "anova": True,
            "unusual": False,
        }
        dlg.validate()
        self.assertIsNotNone(dlg.entry)

        text = format_entry(dlg.entry)
        self.assertNotIn("Regression Equation", text)
        self.assertNotIn("Model Summary", text)
        self.assertIn("Analysis of Variance", text)
        self.assertNotIn("Fits and Diagnostics for Unusual Observations", text)

        # Also check report card content respects the options
        self.win.show_result(dlg.entry)
        report_widget = self.win.result_tabs.widget(0)
        texts = [w.text() for w in report_widget.findChildren(QLabel)] + [
            w.toPlainText() for w in report_widget.findChildren(QPlainTextEdit)
        ]
        joined = "\n".join(texts)
        self.assertNotIn("Regression Equation", joined)
        self.assertNotIn("Summary", joined)


if __name__ == "__main__":
    unittest.main()
