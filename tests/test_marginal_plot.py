"""Unit tests for Marginal Plot engine, report, dialog, and chart widget.
"""
import unittest
import math
from statcraft.model import Worksheet, Column
from statcraft.marginal_plot import compute_marginal_plot
from statcraft.marginal_plot_report import format_marginal_plot_report
from statcraft.app import Presenter, format_entry
from statcraft.recipes import run, columns


def make_sheet():
    xs = [10.0, 12.0, 15.0, 14.0, 18.0, 20.0, 22.0, 25.0, 24.0, 28.0]
    ys = [25.0, 30.0, 34.0, 32.0, 42.0, 48.0, 50.0, 58.0, 56.0, 65.0]
    return Worksheet('Data', [Column('X', values=xs), Column('Y', values=ys)])


class TestMarginalPlot(unittest.TestCase):

    def test_histogram_marginal(self):
        ws = make_sheet()
        res = compute_marginal_plot(ws, y_index=1, x_index=0, marginal_type='histogram', show_normal_curve=True, bins=6)
        self.assertEqual(res['y_name'], 'Y')
        self.assertEqual(res['x_name'], 'X')
        self.assertEqual(res['n'], 10)
        self.assertEqual(res['marginal_type'], 'histogram')
        self.assertTrue(res['show_normal_curve'])

        # Correlation should be very high positive
        self.assertGreater(res['correlation'], 0.95)
        self.assertLess(res['p_value'], 0.001)

        # Normal curve points
        self.assertTrue(len(res['x_stats']['normal_curve']) > 10)
        self.assertTrue(len(res['y_stats']['normal_curve']) > 10)

    def test_boxplot_marginal(self):
        ws = make_sheet()
        res = compute_marginal_plot(ws, y_index=1, x_index=0, marginal_type='boxplot')
        self.assertEqual(res['marginal_type'], 'boxplot')
        x_box = res['x_stats']['box']
        y_box = res['y_stats']['box']
        self.assertLess(x_box['q1'], x_box['median'])
        self.assertLess(x_box['median'], x_box['q3'])
        self.assertLess(y_box['q1'], y_box['median'])
        self.assertLess(y_box['median'], y_box['q3'])

    def test_dotplot_marginal(self):
        ws = make_sheet()
        res = compute_marginal_plot(ws, y_index=1, x_index=0, marginal_type='dotplot')
        self.assertEqual(res['marginal_type'], 'dotplot')
        self.assertTrue(len(res['x_stats']['dots']) > 0)
        self.assertTrue(len(res['y_stats']['dots']) > 0)

    def test_report_formatting(self):
        ws = make_sheet()
        res = compute_marginal_plot(ws, y_index=1, x_index=0, marginal_type='histogram', show_normal_curve=True)
        report = format_marginal_plot_report(res)
        self.assertIn('Marginal Plot of Y vs X', report)
        self.assertIn('Pearson correlation', report)
        self.assertIn('Regression Equation', report)
        self.assertIn('Summary Statistics', report)

    def test_presenter_and_recipe(self):
        ws = make_sheet()
        p = Presenter()
        p.worksheet = ws
        entry = p.marginal_plot(y_index=1, x_index=0, marginal_type='histogram', show_normal_curve=True)
        self.assertEqual(entry['title'], 'Marginal Plot of Y vs X')
        self.assertIn('recipe', entry)

        recipe = entry['recipe']
        self.assertEqual(recipe['action'], 'marginal_plot')
        self.assertEqual(columns(recipe), [0, 1])

        # Recipe rerun
        rerun_entry = run(p, recipe)
        self.assertEqual(rerun_entry['result']['marginal_type'], 'histogram')
        self.assertEqual(rerun_entry['result']['n'], 10)

        # format_entry
        formatted = format_entry(entry)
        self.assertIn('Marginal Plot of Y vs X', formatted)

    def test_qt_chart_widget(self):
        from PySide6.QtWidgets import QApplication
        from statcraft.marginal_plot_chart import MarginalPlotChartWidget
        app = QApplication.instance() or QApplication([])

        ws = make_sheet()
        p = Presenter()
        p.worksheet = ws
        entry = p.marginal_plot(y_index=1, x_index=0, marginal_type='histogram', show_normal_curve=True)

        widget = MarginalPlotChartWidget(entry)
        self.assertIsNotNone(widget.canvas)
        pixmap = widget.canvas.grab()
        self.assertFalse(pixmap.isNull())


if __name__ == '__main__':
    unittest.main()
