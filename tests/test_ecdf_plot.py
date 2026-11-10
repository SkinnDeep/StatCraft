"""Unit tests for Empirical CDF (ECDF) engine, report, dialog, and chart widget.
"""
import unittest
import math
from statcraft.model import Worksheet, Column
from statcraft.ecdf_plot import compute_ecdf_plot
from statcraft.ecdf_report import format_ecdf_report
from statcraft.app import Presenter, format_entry
from statcraft.recipes import run, columns


def make_sheet():
    xs = [12.0, 14.0, 15.0, 18.0, 19.0, 22.0, 25.0, 28.0, 31.0, 35.0, 38.0, 42.0]
    grps = ['G1', 'G1', 'G1', 'G1', 'G1', 'G1', 'G2', 'G2', 'G2', 'G2', 'G2', 'G2']
    return Worksheet('Data', [Column('X', values=xs), Column('Group', kind='text', values=grps)])


class TestECDFPlot(unittest.TestCase):

    def test_single_variable_ecdf(self):
        ws = make_sheet()
        res = compute_ecdf_plot(ws, variable_index=0, distribution='Normal', confidence=0.95)
        self.assertEqual(res['variable_name'], 'X')
        self.assertEqual(res['n_total'], 12)
        self.assertEqual(len(res['series']), 1)

        s = res['series'][0]
        self.assertEqual(s['n'], 12)
        self.assertTrue(len(s['step_points']) > 12)
        # Check that empirical step points range from 0 to 1
        self.assertEqual(s['step_points'][0][1], 0.0)
        self.assertEqual(s['step_points'][-1][1], 1.0)

        # Check DKW epsilon
        # epsilon = sqrt(ln(2 / 0.05) / (2 * 12)) = sqrt(ln(40) / 24) = sqrt(3.688879 / 24) = sqrt(0.1537) ≈ 0.392
        self.assertAlmostEqual(s['epsilon'], math.sqrt(math.log(40.0) / 24.0), places=4)

        # Confidence bands lower and upper
        self.assertEqual(len(s['band_lower']), len(s['step_points']))
        self.assertEqual(len(s['band_upper']), len(s['step_points']))

        # Normal fit curve
        self.assertTrue(len(s['fit_curve']) > 50)
        self.assertIn('Mean', s['fit_params'])
        self.assertIn('StDev', s['fit_params'])

    def test_grouped_ecdf(self):
        ws = make_sheet()
        res = compute_ecdf_plot(ws, variable_index=0, group_index=1, distribution='None')
        self.assertEqual(res['group_name'], 'Group')
        self.assertEqual(len(res['series']), 2)
        groups = [s['group'] for s in res['series']]
        self.assertIn('G1', groups)
        self.assertIn('G2', groups)

    def test_percentiles_table(self):
        ws = make_sheet()
        res = compute_ecdf_plot(ws, variable_index=0, distribution='Normal')
        s = res['series'][0]
        pcts = [p['percent'] for p in s['percentiles']]
        self.assertEqual(pcts, [1, 5, 10, 25, 50, 75, 90, 95, 99])
        for p in s['percentiles']:
            self.assertIsNotNone(p['empirical'])
            self.assertIsNotNone(p['fitted'])

    def test_report_formatting(self):
        ws = make_sheet()
        res = compute_ecdf_plot(ws, variable_index=0, group_index=1, distribution='Normal')
        rep = format_ecdf_report(res)
        self.assertIn('Empirical Cumulative Distribution Function (ECDF) of X', rep)
        self.assertIn('Grouped by: Group', rep)
        self.assertIn('Group: G1', rep)
        self.assertIn('Group: G2', rep)
        self.assertIn('Percentiles', rep)

    def test_presenter_and_recipe(self):
        ws = make_sheet()
        p = Presenter()
        p.worksheet = ws
        entry = p.ecdf_plot(variable_index=0, group_index=1, distribution='Normal', confidence=0.95)
        self.assertEqual(entry['title'], 'Empirical CDF of X')
        self.assertIn('recipe', entry)

        recipe = entry['recipe']
        self.assertEqual(recipe['action'], 'ecdf_plot')
        self.assertEqual(columns(recipe), [0, 1])

        # Recipe rerun
        rerun_entry = run(p, recipe)
        self.assertEqual(rerun_entry['result']['variable_name'], 'X')
        self.assertEqual(len(rerun_entry['result']['series']), 2)

        # format_entry
        formatted = format_entry(entry)
        self.assertIn('Empirical Cumulative Distribution Function (ECDF) of X', formatted)

    def test_qt_chart_widget(self):
        from PySide6.QtWidgets import QApplication
        from statcraft.ecdf_chart import EmpiricalCDFChartWidget
        app = QApplication.instance() or QApplication([])

        ws = make_sheet()
        p = Presenter()
        p.worksheet = ws
        entry = p.ecdf_plot(variable_index=0, distribution='Normal')

        widget = EmpiricalCDFChartWidget(entry)
        self.assertIsNotNone(widget.canvas)
        pixmap = widget.canvas.grab()
        self.assertFalse(pixmap.isNull())


if __name__ == '__main__':
    unittest.main()
