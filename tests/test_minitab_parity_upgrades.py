import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from statcraft import io
from statcraft.app import Column, Presenter, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget, supported as chart_supported


class TestMinitabParityUpgrades(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = ModernWindow()
        p = self.win.presenter
        p.worksheet = Worksheet(
            "ParitySheet",
            [
                Column("Temp", "number", [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 32.0]),
                Column("Pressure", "number", [1.0, 1.2, 1.1, 1.5, 1.8, 2.0, 2.1, 2.5, 2.4, 2.8]),
                Column("Shift", "text", ["Day", "Day", "Day", "Day", "Day", "Night", "Night", "Night", "Night", "Night"]),
                Column("Yield", "number", [52.0, 58.0, 65.0, 74.0, 80.0, 71.0, 78.0, 82.0, 79.0, 75.0]),
            ],
        )
        p._results_dirty = False
        p.dirty = False
        self.win.refresh()

    def tearDown(self):
        self.win.presenter._results_dirty = False
        self.win.presenter.dirty = False
        self.win.close()

    def test_7a_legacy_mtw_mpj_raise_helpful_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ext in (".mtw", ".mpj"):
                fpath = Path(tmp) / f"legacy{ext}"
                fpath.write_bytes(b"binary-minitab")
                with self.assertRaises(io.UnsupportedFormatError) as ctx:
                    self.win.presenter.load(str(fpath))
                msg = str(ctx.exception)
                self.assertIn(".mwx", msg)
                self.assertIn(".xlsx", msg)

    def test_7b_normality_supports_ad_rj_and_ks_methods(self):
        p = self.win.presenter
        ad_entry = p.normality(0, method="Anderson-Darling")
        rj_entry = p.normality(0, method="Ryan-Joiner (similar to Shapiro-Wilk)")
        ks_entry = p.normality(0, method="Kolmogorov-Smirnov")

        self.assertEqual(ad_entry["result"]["statistic_name"], "AD")
        self.assertIn("anderson_darling", ad_entry["result"])
        self.assertEqual(rj_entry["result"]["statistic_name"], "RJ")
        self.assertGreater(rj_entry["result"]["ryan_joiner"], 0.8)
        self.assertEqual(ks_entry["result"]["statistic_name"], "KS")
        self.assertGreater(ks_entry["result"]["kolmogorov_smirnov"], 0.0)

        for entry in (ad_entry, rj_entry, ks_entry):
            self.assertTrue(0.0 <= entry["result"]["p_value"] <= 1.0)
            widget = ChartWidget(entry)
            self.assertIsNone(widget.error)
            self.assertEqual(len(widget.panels), 1)
            self.assertIn(entry["result"]["statistic_name"], widget.note)

    def test_7c_display_descriptive_by_groups_stats_graphs_and_dialog(self):
        p = self.win.presenter
        entry = p.describe_columns(
            [0],
            by_indices=[2],
            statistics=["count", "mean", "sample_stdev", "iqr", "skewness", "range"],
            graphs={"histogram_normal": True, "boxplot": True, "individual_value": False, "histogram": False},
        )
        res = entry["result"]
        self.assertEqual(len(res["columns"]), 2)
        levels = {row["by_level"]: row for row in res["columns"]}
        self.assertEqual(set(levels.keys()), {"Day", "Night"})
        self.assertIn("iqr", levels["Day"])
        self.assertIn("skewness", levels["Day"])
        self.assertTrue(chart_supported(res))
        widget = ChartWidget(entry)
        self.assertIsNone(widget.error)
        self.assertEqual(len(widget.panels), 4)  # 2 groups x (histogram + boxplot)

        from statcraft.descriptive_dialog import DisplayDescriptiveDialog
        dlg = DisplayDescriptiveDialog(p.worksheet, self.win)
        dlg.controls["indices"].setText("C1")
        dlg.controls["by_indices"].setText("C3")
        dlg._graph_opts["boxplot"] = True
        params = dlg.get_parameters()
        self.assertEqual(params["indices"], [0])
        self.assertEqual(params["by_indices"], [2])
        self.assertTrue(params["graphs"]["boxplot"])
        dlg.close()

    def test_7d_calculator_dialog_and_live_text_formula_recalculation(self):
        p = self.win.presenter
        from statcraft.calculator_dialog import CalculatorDialog

        dlg = CalculatorDialog(p.worksheet, self.win)
        dlg._insert_text("IF(C1 >= 22, 'Hot', 'Mild')")
        dlg.dest_combo.setCurrentText("Band")
        dlg.formula_chk.setChecked(True)
        params = dlg.get_parameters()
        dlg._on_accept()
        self.assertTrue(params["assign_formula"])

        p.calculate(**params)
        band_idx = next(i for i, c in enumerate(p.worksheet.columns) if c.name == "Band")
        band_col = p.worksheet.columns[band_idx]
        self.assertEqual(band_col.kind, "text")
        self.assertEqual(band_col.values[0], "Mild")
        self.assertEqual(band_col.values[-1], "Hot")

        # Mutating C1 should dynamically recalculate the text formula column
        p.set_cell(0, 0, "30")
        self.assertEqual(p.worksheet.columns[band_idx].values[0], "Hot")

    def test_7e_fit_regression_model_categorical_quadratic_and_interactions(self):
        p = self.win.presenter
        # Y = Yield (3), continuous = [Temp(0), Pressure(1)], categorical = [Shift(2)]
        # terms: Temp(0), Pressure(1), Shift(2), Temp^2([0,0]), Temp*Shift([0,2])
        entry = p.multiple_regression(
            3,
            [0, 1],
            confidence=0.95,
            categorical_indices=[2],
            model_terms=[[0], [1], [2], [0, 0], [0, 2]],
        )
        res = entry["result"]
        coef_names = [c["name"] for c in res["coefficients"]]
        self.assertIn("Temp*Temp", coef_names)
        self.assertTrue(any("Shift" in name for name in coef_names))
        self.assertTrue(any("Temp*Shift" in name for name in coef_names))
        self.assertIn("categorical_predictors", res)
        self.assertGreater(res["r_squared"], 0.8)

        from statcraft.regression_dialog import FitRegressionModelDialog
        dlg = FitRegressionModelDialog(self.win)
        dlg.controls["response_index"].setText("C4")
        dlg.controls["predictor_indices"].setText("C1 C2")
        dlg.controls["categorical_indices"].setText("C3")
        dlg.higher_terms = [(0, 0), (0, 2)]
        dlg.validate()
        self.assertIsNotNone(dlg.entry)
        self.assertIn("Temp*Temp", [c["name"] for c in dlg.entry["result"]["coefficients"]])


if __name__ == "__main__":
    unittest.main()
