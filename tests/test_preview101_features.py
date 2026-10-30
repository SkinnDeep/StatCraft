"""Unit tests for Preview 101 features:
1. Multi-Vari Chart (Stat > Quality Tools > Multi-Vari Chart...)
2. Grubbs' Outlier Test (Stat > Basic Statistics > Outlier Test...)
3. Column Standardization (Calc > Standardize...)
4. Presenter, Recipes, and Dialog Integration
"""
import unittest
from statcraft.multivari import compute_multivari
from statcraft.multivari_report import format_multivari_report
from statcraft.outlier_test import grubbs_test
from statcraft.outlier_test_report import format_outlier_report
from statcraft.standardize import standardize_column
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft import recipes


class TestMultiVari(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(name="MultiVariWS")
        # Factors: Part (1, 2), Operator (A, B)
        # Response: Length
        self.ws.columns.append(Column("Length", "number", [10.2, 10.4, 10.1, 10.5, 12.1, 12.3, 11.9, 12.4]))
        self.ws.columns.append(Column("Part", "text", ["P1", "P1", "P1", "P1", "P2", "P2", "P2", "P2"]))
        self.ws.columns.append(Column("Operator", "text", ["Op1", "Op1", "Op2", "Op2", "Op1", "Op1", "Op2", "Op2"]))

    def test_multivari_calculation(self):
        res = compute_multivari(self.ws, 0, [1, 2])
        self.assertEqual(res['n_total'], 8)
        self.assertEqual(res['response_name'], "Length")
        self.assertEqual(res['factor_names'], ["Part", "Operator"])
        self.assertTrue(res['grand_mean'] > 10.0)
        self.assertEqual(len(res['cells']), 4)
        self.assertIn("Part", res['factor_level_means'])
        self.assertIn("Operator", res['factor_level_means'])

    def test_multivari_report(self):
        res = compute_multivari(self.ws, 0, [1, 2])
        rep = format_multivari_report(res)
        self.assertIn("Multi-Vari Chart for Length", rep)
        self.assertIn("Factor: Part", rep)
        self.assertIn("Factor: Operator", rep)
        self.assertIn("Cell Combinations:", rep)


class TestOutlierTest(unittest.TestCase):
    def test_grubbs_with_outlier(self):
        # Sample with an obvious high outlier (55.0)
        data = [10.1, 10.2, 9.9, 10.4, 10.0, 10.3, 10.1, 9.8, 10.5, 55.0]
        res = grubbs_test(data, alpha=0.05, alternative='two-sided')
        self.assertEqual(res['n'], 10)
        self.assertTrue(res['is_outlier'])
        self.assertEqual(res['outlier_value'], 55.0)
        self.assertEqual(res['outlier_row'], 10)
        self.assertEqual(res['outlier_type'], "High")
        self.assertTrue(res['p_value'] < 0.01)

    def test_grubbs_no_outlier(self):
        data = [10.1, 10.2, 9.9, 10.4, 10.0, 10.3, 10.1, 9.8, 10.5, 10.3]
        res = grubbs_test(data, alpha=0.05, alternative='two-sided')
        self.assertFalse(res['is_outlier'])
        self.assertTrue(res['p_value'] > 0.05)

    def test_outlier_report(self):
        data = [10.1, 10.2, 9.9, 10.4, 10.0, 10.3, 10.1, 9.8, 10.5, 55.0]
        res = grubbs_test(data, alpha=0.05, alternative='two-sided')
        res['variable_name'] = "Voltage"
        rep = format_outlier_report(res)
        self.assertIn("Outlier Test: Voltage", rep)
        self.assertIn("Grubbs' Test", rep)
        self.assertIn("An outlier is detected at row 10", rep)


class TestStandardize(unittest.TestCase):
    def test_standardize_methods(self):
        data = [10.0, 20.0, 30.0, None, 40.0]

        # 1. Z-score
        z = standardize_column(data, method='zscore')
        self.assertIsNone(z[3])
        valid_z = [x for x in z if x is not None]
        mean_z = sum(valid_z) / len(valid_z)
        self.assertAlmostEqual(mean_z, 0.0, places=4)

        # 2. Subtract mean
        sm = standardize_column(data, method='subtract_mean')
        self.assertAlmostEqual(sm[0], 10.0 - 25.0, places=4)

        # 3. Range 0 to 1
        r01 = standardize_column(data, method='range_0_1')
        self.assertAlmostEqual(r01[0], 0.0, places=4)
        self.assertAlmostEqual(r01[4], 1.0, places=4)


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(name="IntegrationWS")
        self.ws.columns.append(Column("Measurements", "number", [10, 12, 11, 13, 12, 14, 11, 15]))
        self.ws.columns.append(Column("Machine", "text", ["M1", "M1", "M1", "M1", "M2", "M2", "M2", "M2"]))
        self.app = Presenter()
        self.app.worksheet = self.ws

    def test_multivari_presenter_and_recipe(self):
        entry = self.app.multivari(0, [1])
        self.assertEqual(entry['result']['analysis'], 'multivari')
        self.assertEqual(entry['recipe']['action'], 'multivari')

        replayed = recipes.run(self.app, entry['recipe'])
        self.assertEqual(replayed['result']['n_total'], 8)

    def test_outlier_test_presenter_and_recipe(self):
        entry = self.app.outlier_test(0, alpha=0.05, alternative='two-sided')
        self.assertEqual(entry['result']['analysis'], 'outlier_test')
        self.assertEqual(entry['recipe']['action'], 'outlier_test')

        replayed = recipes.run(self.app, entry['recipe'])
        self.assertEqual(replayed['result']['n'], 8)

    def test_standardize_presenter(self):
        entry = self.app.standardize([0], method='zscore')
        self.assertEqual(len(self.ws.columns), 3)
        self.assertEqual(self.ws.columns[2].name, "Z_Measurements")
        self.assertTrue(self.app.dirty)


class TestChartWidgetsAndDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls._qapp = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet(name="TestWidgetsWS")
        self.ws.columns.append(Column("Score", "number", [50, 52, 48, 55, 53, 51, 95, 52]))
        self.ws.columns.append(Column("Batch", "text", ["B1", "B1", "B1", "B1", "B2", "B2", "B2", "B2"]))

    def test_multivari_widget_and_dialog(self):
        from statcraft.multivari_chart import MultiVariChartWidget
        from statcraft.multivari_dialogs import MultiVariDialog
        from PySide6.QtGui import QPixmap

        res = compute_multivari(self.ws, 0, [1])
        entry = {'title': 'Multi-Vari Chart for Score', 'result': res}
        widget = MultiVariChartWidget(entry)
        widget.resize(800, 500)
        pix = QPixmap(800, 500)
        widget.render(pix)
        self.assertFalse(pix.isNull())

        dlg = MultiVariDialog(self.ws)
        dlg.resp_edit.setText("Score")
        dlg.f1_edit.setText("Batch")
        settings = dlg.get_settings()
        self.assertEqual(settings['response_index'], 0)
        self.assertEqual(settings['factor_indices'], [1])
        dlg.close()

    def test_outlier_widget_and_dialog(self):
        from statcraft.outlier_test_chart import OutlierTestChartWidget
        from statcraft.outlier_test_dialogs import OutlierTestDialog
        from PySide6.QtGui import QPixmap

        res = grubbs_test([50, 52, 48, 55, 53, 51, 95, 52], alpha=0.05)
        res['variable_name'] = 'Score'
        entry = {'title': 'Outlier Plot for Score', 'result': res}
        widget = OutlierTestChartWidget(entry)
        widget.resize(800, 500)
        pix = QPixmap(800, 500)
        widget.render(pix)
        self.assertFalse(pix.isNull())

        dlg = OutlierTestDialog(self.ws)
        dlg.var_edit.setText("Score")
        dlg.alpha_edit.setText("0.05")
        settings = dlg.get_settings()
        self.assertEqual(settings['variable_index'], 0)
        self.assertEqual(settings['alpha'], 0.05)
        dlg.close()

    def test_standardize_dialog(self):
        from statcraft.standardize_dialogs import StandardizeDialog

        dlg = StandardizeDialog(self.ws)
        dlg.cols_edit.setText("Score")
        settings = dlg.get_settings()
        self.assertEqual(settings['source_indices'], [0])
        self.assertEqual(settings['method'], "zscore")
        dlg.close()


if __name__ == '__main__':
    unittest.main()
