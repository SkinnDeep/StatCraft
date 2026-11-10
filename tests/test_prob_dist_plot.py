"""Unit tests for Probability Distribution Plot engine, report, dialog, and chart widget.
"""
import unittest
import math
from statcraft.prob_dist_plot import compute_probability_distribution_plot, get_distribution_scipy
from statcraft.prob_dist_report import format_probability_distribution_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.recipes import run, columns


class TestProbabilityDistributionPlot(unittest.TestCase):

    def test_normal_single_curve(self):
        res = compute_probability_distribution_plot(
            distribution='Normal',
            parameters={'mean': 10.0, 'stdev': 2.0},
            mode='single',
        )
        self.assertEqual(res['distribution'], 'Normal')
        self.assertEqual(res['mode'], 'single')
        self.assertAlmostEqual(res['mean'], 10.0)
        self.assertAlmostEqual(res['stdev'], 2.0)
        self.assertFalse(res['is_discrete'])
        self.assertTrue(len(res['curve_points']) > 100)
        self.assertEqual(res['shaded_regions'], [])

    def test_normal_both_tails_probability(self):
        res = compute_probability_distribution_plot(
            distribution='Normal',
            parameters={'mean': 0.0, 'stdev': 1.0},
            mode='probability',
            shade_by='probability',
            tail='both',
            prob_value=0.05,
        )
        self.assertEqual(res['mode'], 'probability')
        self.assertEqual(res['tail'], 'both')
        self.assertAlmostEqual(res['total_shaded_prob'], 0.05, places=5)
        self.assertAlmostEqual(res['c1'], -1.95996, places=4)
        self.assertAlmostEqual(res['c2'], 1.95996, places=4)
        self.assertEqual(len(res['shaded_regions']), 2)
        self.assertEqual(len(res['cutoffs']), 2)

    def test_normal_right_tail_by_x(self):
        res = compute_probability_distribution_plot(
            distribution='Normal',
            parameters={'mean': 0.0, 'stdev': 1.0},
            mode='probability',
            shade_by='x_value',
            tail='right',
            x_value=1.64485,
        )
        self.assertAlmostEqual(res['total_shaded_prob'], 0.05, places=4)
        self.assertEqual(len(res['shaded_regions']), 1)
        self.assertEqual(len(res['cutoffs']), 1)

    def test_student_t_distribution(self):
        res = compute_probability_distribution_plot(
            distribution="Student's t",
            parameters={'df': 15.0},
            mode='probability',
            shade_by='probability',
            tail='both',
            prob_value=0.05,
        )
        self.assertAlmostEqual(res['c2'], 2.13145, places=4)
        self.assertAlmostEqual(res['total_shaded_prob'], 0.05, places=4)

    def test_discrete_binomial(self):
        res = compute_probability_distribution_plot(
            distribution='Binomial',
            parameters={'n': 10, 'p': 0.5},
            mode='probability',
            shade_by='x_value',
            tail='right',
            x_value=8,
        )
        self.assertTrue(res['is_discrete'])
        self.assertTrue(len(res['discrete_bars']) > 0)
        # P(X >= 8) for B(10, 0.5) is (45 + 10 + 1) / 1024 = 56 / 1024 = 0.0546875
        self.assertAlmostEqual(res['total_shaded_prob'], 56.0 / 1024.0, places=5)
        # Check shaded flag on bars
        for b in res['discrete_bars']:
            if b['x'] >= 8:
                self.assertTrue(b['shaded'])
            else:
                self.assertFalse(b['shaded'])

    def test_report_formatting(self):
        res = compute_probability_distribution_plot(
            distribution='Normal',
            parameters={'mean': 0.0, 'stdev': 1.0},
            mode='probability',
            shade_by='probability',
            tail='both',
            prob_value=0.05,
        )
        report = format_probability_distribution_report(res)
        self.assertIn('Probability Distribution Plot', report)
        self.assertIn('Distribution: Normal', report)
        self.assertIn('Both Tails', report)
        self.assertIn('Total Probability:     0.050000', report)
        self.assertIn('Mean:', report)

    def test_presenter_and_recipe(self):
        p = Presenter()
        p.worksheet = Worksheet('Test', [Column('X', values=[1, 2, 3])])
        entry = p.probability_distribution_plot(
            distribution='Normal',
            parameters={'mean': 0.0, 'stdev': 1.0},
            mode='probability',
            shade_by='probability',
            tail='both',
            prob_value=0.05,
        )
        self.assertEqual(entry['title'], 'Distribution Plot: Normal')
        self.assertIn('recipe', entry)
        recipe = entry['recipe']
        self.assertEqual(recipe['action'], 'probability_distribution_plot')
        self.assertEqual(columns(recipe), [])

        # Test recipe rerun
        rerun_entry = run(p, recipe)
        self.assertEqual(rerun_entry['result']['distribution'], 'Normal')
        self.assertAlmostEqual(rerun_entry['result']['total_shaded_prob'], 0.05, places=5)

    def test_format_entry_session_output(self):
        from statcraft.app import format_entry
        p = Presenter()
        entry = p.probability_distribution_plot(
            distribution='Student\'s t',
            parameters={'df': 10.0},
            mode='probability',
            shade_by='probability',
            tail='right',
            prob_value=0.025,
        )
        formatted = format_entry(entry)
        self.assertIn('Probability Distribution Plot', formatted)
        self.assertIn('Student\'s t', formatted)
        self.assertIn('Right Tail', formatted)

    def test_qt_chart_widget_instantiation(self):
        from PySide6.QtWidgets import QApplication
        from statcraft.prob_dist_chart import ProbabilityDistributionChartWidget
        app = QApplication.instance() or QApplication([])
        p = Presenter()
        entry = p.probability_distribution_plot(
            distribution='Normal',
            parameters={'mean': 0.0, 'stdev': 1.0},
            mode='probability',
            shade_by='probability',
            tail='both',
            prob_value=0.05,
        )
        widget = ProbabilityDistributionChartWidget(entry)
        self.assertIsNotNone(widget.canvas)
        pixmap = widget.canvas.grab()
        self.assertFalse(pixmap.isNull())


if __name__ == '__main__':
    unittest.main()
