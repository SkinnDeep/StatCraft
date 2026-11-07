"""Comprehensive Unit Tests for Individual Distribution Identification (Minitab 22 Parity)."""
import unittest
import numpy as np

from statcraft.dist_id import (
    DISTRIBUTION_NAMES,
    calculate_ad_exponential,
    calculate_ad_gamma,
    calculate_ad_logistic,
    calculate_ad_normal,
    calculate_ad_weibull,
    calculate_distribution_identification,
    fit_box_cox,
    fit_johnson,
)
from statcraft.dist_id_report import generate_dist_id_report
from statcraft.model import Column, Worksheet


class TestDistIdEngine(unittest.TestCase):
    """Test statistical algorithms, distribution fitting, and AD goodness-of-fit."""

    def setUp(self):
        np.random.seed(42)
        self.normal_data = np.random.normal(50.0, 5.0, size=60)
        self.weibull_data = np.random.weibull(2.0, size=60) * 15.0 + 10.0
        self.exp_data = np.random.exponential(12.0, size=60) + 2.0

    def test_ad_normal_calculation(self):
        ad, p = calculate_ad_normal(self.normal_data)
        self.assertGreater(ad, 0.0)
        self.assertGreater(p, 0.05)
        self.assertLessEqual(p, 1.0)

    def test_ad_weibull_calculation(self):
        ad, p = calculate_ad_weibull(self.weibull_data, shape=2.0, scale=15.0)
        self.assertGreater(ad, 0.0)
        self.assertGreaterEqual(p, 0.0001)
        self.assertLessEqual(p, 1.0)

    def test_ad_exponential_calculation(self):
        ad, p = calculate_ad_exponential(self.exp_data, scale=14.0)
        self.assertGreater(ad, 0.0)
        self.assertGreaterEqual(p, 0.0001)

    def test_ad_logistic_calculation(self):
        ad, p = calculate_ad_logistic(self.normal_data, loc=50.0, scale=3.0)
        self.assertGreater(ad, 0.0)
        self.assertGreaterEqual(p, 0.0001)

    def test_ad_gamma_calculation(self):
        ad, p = calculate_ad_gamma(self.weibull_data, shape=4.0, scale=3.0)
        self.assertGreater(ad, 0.0)
        self.assertGreaterEqual(p, 0.0001)

    def test_box_cox_optimization(self):
        bc = fit_box_cox(self.weibull_data)
        self.assertIn("lambda", bc)
        self.assertIn("rounded_lambda", bc)
        self.assertIn("ad", bc)
        self.assertIn("p_value", bc)
        self.assertIsInstance(bc["rounded_lambda"], float)
        self.assertEqual(len(bc["transformed"]), len(self.weibull_data))

    def test_johnson_transformation(self):
        j = fit_johnson(self.weibull_data)
        self.assertIn(j["family"], ("SB", "SL", "SU", "SN"))
        self.assertIn("function", j)
        self.assertGreaterEqual(j["p_value"], 0.0001)
        self.assertIsInstance(j["passed"], bool)

    def test_all_16_distributions_fit(self):
        res = calculate_distribution_identification(self.weibull_data, variable_name="Strength")
        self.assertEqual(res["analysis"], "dist_id")
        self.assertEqual(res["variable_name"], "Strength")
        self.assertEqual(res["n_samples"], 60)
        self.assertGreaterEqual(len(res["fits"]), 14)

        # Verify Goodness of Fit table
        gof = res["gof_table"]
        self.assertGreaterEqual(len(gof), 14)
        dist_titles = [row["distribution"] for row in gof]
        self.assertIn("Normal", dist_titles)
        self.assertIn("Box-Cox Transformation", dist_titles)
        self.assertIn("Weibull", dist_titles)
        self.assertIn("3-Parameter Weibull", dist_titles)
        self.assertIn("Johnson Transformation", dist_titles)

        # Check that 3-parameter Weibull has LRT P
        w3_row = next((r for r in gof if r["key"] == "weibull_3p"), None)
        self.assertIsNotNone(w3_row)
        self.assertIsNotNone(w3_row.get("lrt_p"))

        # Verify Parameters table
        params = res["param_table"]
        self.assertGreaterEqual(len(params), 14)
        w3_param = next((r for r in params if r["key"] == "weibull_3p"), None)
        self.assertIsNotNone(w3_param)
        self.assertIsNotNone(w3_param.get("shape"))
        self.assertIsNotNone(w3_param.get("scale"))
        self.assertIsNotNone(w3_param.get("threshold"))

        # Best fit should be selected
        self.assertIsNotNone(res["best_fit"])

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            calculate_distribution_identification([1.0, 2.0])  # fewer than 3

        with self.assertRaises(ValueError):
            calculate_distribution_identification([5.0, 5.0, 5.0, 5.0])  # zero variance


class TestDistIdReport(unittest.TestCase):
    """Test report generation output."""

    def test_report_formatting(self):
        np.random.seed(42)
        data = np.random.weibull(2.0, size=50) * 10.0 + 5.0
        res = calculate_distribution_identification(data, variable_name="Torque")
        report = generate_dist_id_report(res)

        self.assertIn("Individual Distribution Identification for Torque", report)
        self.assertIn("Goodness of Fit Test", report)
        self.assertIn("ML Estimates of Distribution Parameters", report)
        self.assertIn("Box-Cox Transformation:", report)
        self.assertIn("Johnson Transformation", report)
        self.assertIn("Selected Best-Fitting Distribution", report)


class TestDistIdAppIntegration(unittest.TestCase):
    """Test full integration with worksheet, App, connected analysis, and recipes."""

    def setUp(self):
        self.ws = Worksheet()
        np.random.seed(42)
        vals = (np.random.weibull(2.0, size=40) * 10.0 + 5.0).tolist()
        self.ws.columns.append(Column(name="Torque", kind="number", values=vals))

    def test_app_dist_id_call(self):
        from statcraft.app import Presenter
        app = Presenter()
        app.worksheet = self.ws
        entry = app.dist_id(column_index=0)

        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "Individual Distribution Identification for Torque")
        self.assertIn("connected_analysis", entry)
        conn = entry["connected_analysis"]
        self.assertEqual(conn["analysis_type"], "dist_id")
        self.assertEqual(conn["response_name"], "Torque")
        self.assertIn("r_script", conn)
        self.assertIn("fitdistrplus", conn["r_script"])

    def test_recipe_replay(self):
        from statcraft.app import Presenter
        from statcraft.recipes import run
        app = Presenter()
        app.worksheet = self.ws
        recipe = {
            "action": "dist_id",
            "parameters": {
                "column_index": 0,
                "distributions": ["normal", "weibull"],
                "subgroup_size": 1,
                "alpha": 0.05,
            }
        }
        entry = run(app, recipe)
        self.assertIsNotNone(entry)
        self.assertIn("fits", entry["result"])
        self.assertIn("normal", entry["result"]["fits"])
        self.assertIn("weibull", entry["result"]["fits"])


class TestDistIdUI(unittest.TestCase):
    """Test Qt UI components (Dialog & Chart)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.ws = Worksheet()
        np.random.seed(42)
        vals = (np.random.weibull(2.0, size=30) * 10.0 + 5.0).tolist()
        self.ws.columns.append(Column(name="Torque", kind="number", values=vals))

    def test_chart_widget_groups(self):
        from statcraft.app import Presenter
        from statcraft.dist_id_chart import DistIdChartWidget
        app = Presenter()
        app.worksheet = self.ws
        entry = app.dist_id(column_index=0)

        widget = DistIdChartWidget(entry)
        self.assertIsNotNone(widget)

        # Switch groups
        widget._switch_group("g1")
        self.assertIsNotNone(widget.current_group_widget)
        widget._switch_group("g2")
        self.assertIsNotNone(widget.current_group_widget)
        widget._switch_group("g3")
        self.assertIsNotNone(widget.current_group_widget)
        widget._switch_group("g4")
        self.assertIsNotNone(widget.current_group_widget)
        widget._switch_group("best")
        self.assertIsNotNone(widget.current_group_widget)

    def test_dialog_creation(self):
        from statcraft.dist_id_dialog import DistIdDialog
        dlg = DistIdDialog(self.ws)
        self.assertEqual(dlg.windowTitle(), "Individual Distribution Identification")
        self.assertEqual(dlg.col_list.count(), 1)
        self.assertTrue(dlg.rb_all.isChecked())


if __name__ == "__main__":
    unittest.main()
