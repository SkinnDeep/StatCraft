"""Unit tests for Preview 100 features:
1. Graphical Summary (Descriptive Stats, Anderson-Darling, CIs, Boxplot & Histogram)
2. Quality Run Chart (Runs about median & Runs up/down)
3. Patterned and Random Data Generation
4. Recipes and App integration
5. Chart widget rendering
"""
import unittest
import math
from statcraft.graphical_summary import graphical_summary
from statcraft.graphical_summary_report import generate_graphical_summary_report, format_graphical_summary_report
from statcraft.run_chart import run_chart
from statcraft.run_chart_report import generate_run_chart_report, format_run_chart_report
from statcraft.calc_data import make_patterned_numbers, generate_random_normal, generate_random_uniform
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft import recipes


class TestGraphicalSummary(unittest.TestCase):
    def setUp(self):
        self.data = [10.2, 11.5, 9.8, 12.1, 10.5, 11.0, 10.8, 12.4, 9.5, 11.2, 10.9, 11.7]

    def test_graphical_summary_calculations(self):
        res = graphical_summary(self.data, confidence=0.95)
        self.assertEqual(res['n'], 12)
        self.assertAlmostEqual(res['mean'], sum(self.data) / 12, places=4)
        self.assertTrue(res['stdev'] > 0)
        self.assertTrue(res['variance'] > 0)
        self.assertIn('skewness', res)
        self.assertIn('kurtosis', res)
        self.assertAlmostEqual(res['min'], 9.5)
        self.assertAlmostEqual(res['max'], 12.4)
        self.assertIn('ad_stat', res)
        self.assertIn('ad_p', res)
        
        # Check Confidence Intervals
        mean_low, mean_high = res['ci_mean']
        self.assertTrue(mean_low < res['mean'] < mean_high)
        med_low, med_high = res['ci_median']
        self.assertTrue(med_low <= res['median'] <= med_high)
        sd_low, sd_high = res['ci_stdev']
        self.assertTrue(sd_low < res['stdev'] < sd_high)

        # Check boxplot and histogram structures
        self.assertIn('boxplot', res)
        self.assertIn('histogram', res)
        self.assertEqual(sum(res['histogram']['counts']), 12)

    def test_graphical_summary_report(self):
        res = graphical_summary(self.data, confidence=0.95)
        report = generate_graphical_summary_report("Strength", res)
        self.assertIn("Summary Report for Strength", report)
        self.assertIn("Anderson-Darling Normality Test", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("95% Confidence Intervals", report)

        # format helper
        res['variable_name'] = 'Strength'
        formatted = format_graphical_summary_report(res)
        self.assertIn("Summary Report for Strength", formatted)


class TestRunChart(unittest.TestCase):
    def setUp(self):
        # 20 observations with some alternating and trending behavior
        self.data = [12, 14, 13, 15, 16, 18, 19, 21, 20, 22, 19, 17, 16, 14, 15, 13, 11, 10, 12, 14]

    def test_run_chart_subgroup1(self):
        res = run_chart(self.data, subgroup_size=1)
        self.assertEqual(res['n'], 20)
        self.assertEqual(res['subgroup_size'], 1)
        self.assertIn('median', res)

        rbm = res['runs_about_median']
        self.assertTrue(rbm['number_of_runs'] >= 1)
        self.assertTrue(rbm['expected_runs'] > 0)
        self.assertTrue(0.0 <= rbm['p_cluster'] <= 1.0)
        self.assertTrue(0.0 <= rbm['p_mixture'] <= 1.0)

        rud = res['runs_up_or_down']
        self.assertTrue(rud['number_of_runs'] >= 1)
        self.assertTrue(rud['expected_runs'] > 0)
        self.assertTrue(0.0 <= rud['p_trend'] <= 1.0)
        self.assertTrue(0.0 <= rud['p_oscillation'] <= 1.0)

    def test_run_chart_subgroups(self):
        res = run_chart(self.data, subgroup_size=2)
        self.assertEqual(res['n'], 10)
        self.assertEqual(res['subgroup_size'], 2)
        self.assertEqual(len(res['points']), 10)

    def test_run_chart_report(self):
        res = run_chart(self.data, subgroup_size=1)
        report = generate_run_chart_report("Viscosity", res)
        self.assertIn("Run Chart of Viscosity", report)
        self.assertIn("Runs About Median", report)
        self.assertIn("Runs Up or Down", report)
        self.assertIn("Approx P-Value for Clustering", report)
        self.assertIn("Approx P-Value for Trends", report)


class TestCalcData(unittest.TestCase):
    def test_make_patterned_numbers(self):
        res = make_patterned_numbers(1.0, 5.0, step=1.0, repeat_each=2, repeat_sequence=2)
        expected = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0, 5.0, 5.0,
                    1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0, 5.0, 5.0]
        self.assertEqual(res, expected)

    def test_generate_random_normal(self):
        res = generate_random_normal(100, mean=50.0, stdev=5.0, seed=42)
        self.assertEqual(len(res), 100)
        mean_calc = sum(res) / 100
        self.assertTrue(45.0 < mean_calc < 55.0)

    def test_generate_random_uniform(self):
        res = generate_random_uniform(100, low=10.0, high=20.0, seed=42)
        self.assertEqual(len(res), 100)
        self.assertTrue(all(10.0 <= x <= 20.0 for x in res))


class TestAppIntegration(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(name="TestWS")
        col = Column("Diameter", "number", [10.1, 10.2, 10.0, 10.4, 10.3, 10.5, 10.2, 10.1, 10.6, 10.3])
        self.ws.columns.append(col)
        self.app = Presenter()
        self.app.worksheet = self.ws

    def test_graphical_summary_app(self):
        entry = self.app.graphical_summary(0, confidence=0.95)
        self.assertIsNotNone(entry)
        self.assertEqual(entry['result']['analysis'], 'graphical_summary')
        self.assertIn('ad_stat', entry['result'])
        self.assertEqual(entry['recipe']['action'], 'graphical_summary')

        # Test recalculation via recipes.run
        entry_rerun = recipes.run(self.app, entry['recipe'])
        self.assertEqual(entry_rerun['result']['n'], 10)

    def test_run_chart_app(self):
        entry = self.app.run_chart(0, subgroup_size=1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry['result']['analysis'], 'run_chart')
        self.assertIn('runs_about_median', entry['result'])
        self.assertEqual(entry['recipe']['action'], 'run_chart')

        # Test recalculation via recipes.run
        entry_rerun = recipes.run(self.app, entry['recipe'])
        self.assertEqual(entry_rerun['result']['n'], 10)

    def test_calc_data_app(self):
        # Patterned data
        self.app.make_patterned_data(0, 1.0, 3.0, 1.0, 1, 2)
        self.assertEqual(self.app.worksheet.columns[0].values, [1.0, 2.0, 3.0, 1.0, 2.0, 3.0])
        self.assertTrue(self.app.dirty)

        # Random normal data
        self.app.generate_random_data(0, 'normal', 25, 100.0, 10.0, seed=99)
        self.assertEqual(len(self.app.worksheet.columns[0].values), 25)

        # Random uniform data
        self.app.generate_random_data(0, 'uniform', 15, 0.0, 1.0, seed=99)
        self.assertEqual(len(self.app.worksheet.columns[0].values), 15)


class TestChartWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls._qapp = QApplication([])
        else:
            cls._qapp = QApplication.instance()

    def test_graphical_summary_widget_paint(self):
        from statcraft.graphical_summary_chart import GraphicalSummaryChartWidget
        from PySide6.QtGui import QPixmap, QPainter
        data = [10.2, 11.5, 9.8, 12.1, 10.5, 11.0, 10.8, 12.4, 9.5, 11.2, 10.9, 11.7]
        res = graphical_summary(data, confidence=0.95)
        res['variable_name'] = 'Measurements'
        res['analysis'] = 'graphical_summary'
        entry = {'title': 'Summary Report for Measurements', 'result': res}

        widget = GraphicalSummaryChartWidget(entry)
        widget.resize(800, 600)
        pix = QPixmap(800, 600)
        widget.render(pix)
        self.assertFalse(pix.isNull())

    def test_run_chart_widget_paint(self):
        from statcraft.run_chart_plot import RunChartWidget
        from PySide6.QtGui import QPixmap
        data = [12, 14, 13, 15, 16, 18, 19, 21, 20, 22, 19, 17, 16, 14, 15, 13, 11, 10, 12, 14]
        res = run_chart(data, subgroup_size=1)
        res['variable_name'] = 'Parts'
        res['analysis'] = 'run_chart'
        entry = {'title': 'Run Chart of Parts', 'result': res}

        widget = RunChartWidget(entry)
        widget.resize(800, 600)
        pix = QPixmap(800, 600)
        widget.render(pix)
        self.assertFalse(pix.isNull())


class TestDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls._qapp = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet(name="DialogWS")
        self.ws.columns.append(Column("Strength", "number", [10, 11, 12, 13, 14, 15]))
        self.ws.columns.append(Column("Speed", "number", [100, 105, 110, 115, 120, 125]))

    def test_graphical_summary_dialog(self):
        from statcraft.graphical_summary_dialogs import GraphicalSummaryDialog
        dlg = GraphicalSummaryDialog(self.ws)
        dlg.var_edit.setText("Strength")
        dlg.conf_edit.setText("99.0")
        settings = dlg.get_settings()
        self.assertEqual(settings['variables'], [0])
        self.assertAlmostEqual(settings['confidence'], 0.99)
        dlg.close()

    def test_run_chart_dialog(self):
        from statcraft.run_chart_dialogs import RunChartDialog
        dlg = RunChartDialog(self.ws)
        dlg.var_edit.setText("Speed")
        dlg.subgroup_edit.setText("2")
        settings = dlg.get_settings()
        self.assertEqual(settings['variable'], 1)
        self.assertEqual(settings['subgroup_size'], 2)
        dlg.close()

    def test_patterned_numbers_dialog(self):
        from statcraft.calc_data_dialogs import PatternedNumbersDialog
        dlg = PatternedNumbersDialog(self.ws)
        dlg.from_edit.setText("5")
        dlg.to_edit.setText("15")
        dlg.step_edit.setText("2.5")
        dlg.rep_each_edit.setText("1")
        dlg.rep_seq_edit.setText("3")
        settings = dlg.get_settings()
        self.assertEqual(settings['from_val'], 5.0)
        self.assertEqual(settings['to_val'], 15.0)
        self.assertEqual(settings['step'], 2.5)
        self.assertEqual(settings['repeat_sequence'], 3)
        dlg.close()

    def test_random_data_dialogs(self):
        from statcraft.calc_data_dialogs import RandomNormalDialog, RandomUniformDialog
        dlg_norm = RandomNormalDialog(self.ws)
        dlg_norm.num_edit.setText("80")
        dlg_norm.mean_edit.setText("25.0")
        dlg_norm.sd_edit.setText("3.0")
        norm_s = dlg_norm.get_settings()
        self.assertEqual(norm_s['n'], 80)
        self.assertEqual(norm_s['mean'], 25.0)
        self.assertEqual(norm_s['stdev'], 3.0)
        dlg_norm.close()

        dlg_unif = RandomUniformDialog(self.ws)
        dlg_unif.num_edit.setText("45")
        dlg_unif.low_edit.setText("1.0")
        dlg_unif.high_edit.setText("10.0")
        unif_s = dlg_unif.get_settings()
        self.assertEqual(unif_s['n'], 45)
        self.assertEqual(unif_s['low'], 1.0)
        self.assertEqual(unif_s['high'], 10.0)
        dlg_unif.close()


if __name__ == '__main__':
    unittest.main()
