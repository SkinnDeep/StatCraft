"""Comprehensive Unit Tests for Johnson Transformation (Minitab 22 Parity)."""
import unittest
import numpy as np

from statcraft.johnson import calculate_johnson_transformation
from statcraft.johnson_report import generate_johnson_report
from statcraft.model import Column, Worksheet


class TestJohnsonEngine(unittest.TestCase):
    """Test Slifker-Shapiro Johnson transformation algorithm and AD normality tests."""

    def setUp(self):
        np.random.seed(42)
        # Bounded / Weibull nonnormal dataset
        self.weibull_data = np.random.weibull(2.0, size=60) * 15.0 + 10.0
        # Right skewed lognormal dataset
        self.lognorm_data = np.random.lognormal(2.5, 0.6, size=60)

    def test_johnson_fit_weibull(self):
        res = calculate_johnson_transformation(self.weibull_data, variable_name="Thickness")
        self.assertEqual(res["analysis"], "johnson_transformation")
        self.assertEqual(res["variable_name"], "Thickness")
        self.assertIn(res["family"], ("SB", "SL", "SU"))
        self.assertIn("function", res)
        self.assertGreaterEqual(res["transformed"]["p_value"], 0.0001)

        # Transformed values should have same length as input
        full_vals = res["transformed"]["full_values"]
        self.assertEqual(len(full_vals), len(self.weibull_data))

    def test_johnson_fit_lognormal(self):
        res = calculate_johnson_transformation(self.lognorm_data, variable_name="Diameter")
        self.assertIn(res["family"], ("SB", "SL", "SU"))
        self.assertGreater(res["original"]["ad"], 0.0)
        self.assertGreater(res["transformed"]["ad"], 0.0)

    def test_missing_values_preserved(self):
        raw = [10.0, None, 15.0, 20.0, None, 25.0]
        res = calculate_johnson_transformation(raw, variable_name="TestMiss")
        full_vals = res["transformed"]["full_values"]
        self.assertEqual(len(full_vals), 6)
        self.assertIsNone(full_vals[1])
        self.assertIsNone(full_vals[4])
        self.assertIsNotNone(full_vals[0])


class TestJohnsonReport(unittest.TestCase):
    """Test report formatting."""

    def test_report_content(self):
        np.random.seed(42)
        data = np.random.weibull(2.0, size=40) * 12.0 + 8.0
        res = calculate_johnson_transformation(data, variable_name="Yield")
        rep = generate_johnson_report(res)

        self.assertIn("Johnson Transformation for Yield", rep)
        self.assertIn("Transformation Function", rep)
        self.assertIn("Goodness of Fit Test (Normality)", rep)
        self.assertIn("Original Data", rep)
        self.assertIn("Transformed Data", rep)
        self.assertIn("Transformed data stored in column:", rep)


class TestJohnsonAppIntegration(unittest.TestCase):
    """Test integration with Worksheet, Presenter, Connected Analysis, and Recipes."""

    def setUp(self):
        self.ws = Worksheet()
        np.random.seed(42)
        vals = (np.random.weibull(2.0, size=40) * 10.0 + 5.0).tolist()
        self.ws.columns.append(Column(name="Torque", kind="number", values=vals))

    def test_app_johnson_call_and_store(self):
        from statcraft.app import Presenter
        app = Presenter()
        app.worksheet = self.ws

        col_count_before = len(self.ws.columns)
        entry = app.johnson_transformation(column_index=0, store_column_name="Johnson_Torque")

        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "Johnson Transformation for Torque")
        self.assertEqual(len(self.ws.columns), col_count_before + 1)
        self.assertEqual(self.ws.columns[-1].name, "Johnson_Torque")
        self.assertEqual(len(self.ws.columns[-1].values), 40)

        conn = entry.get("connected_analysis")
        self.assertIsNotNone(conn)
        self.assertEqual(conn["analysis_type"], "johnson_transformation")
        self.assertIn("r_script", conn)
        self.assertIn("JohnsonFit", conn["r_script"])

    def test_recipe_replay(self):
        from statcraft.app import Presenter
        from statcraft.recipes import run
        app = Presenter()
        app.worksheet = self.ws
        recipe = {
            "action": "johnson_transformation",
            "parameters": {
                "column_index": 0,
                "store_column_name": "Replay_Johnson",
                "p_threshold": 0.10,
            }
        }
        entry = run(app, recipe)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["store_column_name"], "Replay_Johnson")


class TestJohnsonUI(unittest.TestCase):
    """Test Qt UI elements."""

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

    def test_chart_widget(self):
        from statcraft.app import Presenter
        from statcraft.johnson_chart import JohnsonChartWidget
        app = Presenter()
        app.worksheet = self.ws
        entry = app.johnson_transformation(column_index=0)

        widget = JohnsonChartWidget(entry)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.var_name, "Torque")

    def test_dialog_creation(self):
        from statcraft.johnson_dialog import JohnsonDialog
        dlg = JohnsonDialog(self.ws)
        self.assertEqual(dlg.windowTitle(), "Johnson Transformation")
        self.assertEqual(dlg.col_list.count(), 1)


if __name__ == "__main__":
    unittest.main()
