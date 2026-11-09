"""Unit tests for Attribute Gage Study (Analytic Method)."""
import math
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.model import Worksheet, Column
from statcraft.attribute_gage import compute_attribute_gage_study
from statcraft.attribute_gage_report import generate_attribute_gage_report
from statcraft.attribute_gage_chart import AttributeGageChartWidget
from statcraft.attribute_gage_dialogs import (
    AttributeGageDialog,
    AttributeGageOptionsDialog,
    AttributeGageInfoDialog,
)
from statcraft.app import Presenter, format_entry
import statcraft.recipes as recipes


class TestAttributeGageComputation(unittest.TestCase):
    def setUp(self):
        # AIAG MSA 4th ed style reference data
        self.ref_values = [0.015, 0.025, 0.035, 0.045, 0.055, 0.065, 0.075, 0.085]
        self.acceptances = [0, 1, 3, 10, 15, 18, 20, 20]
        self.trials = 20
        self.target = 0.050
        self.tolerance = 0.080

    def test_basic_attribute_gage_computation(self):
        settings = {
            'target': self.target,
            'tolerance': self.tolerance,
            'alpha': 0.05,
            'study_multiplier': 5.15,
            'gage_info': {'gage_name': 'Test Caliper'},
        }
        res = compute_attribute_gage_study(
            reference_values=self.ref_values,
            acceptances=self.acceptances,
            trials=self.trials,
            settings=settings,
        )

        reg = res['regression']
        bias_info = res['bias_metrics']
        rep_info = res['repeatability']
        plot_info = res['plot_data']

        self.assertEqual(reg['n'], 8)
        self.assertEqual(bias_info['target'], 0.050)
        self.assertEqual(rep_info['tolerance'], 0.080)

        # Probit slope should be positive (acceptance rate increases with ref)
        self.assertGreater(reg['slope'], 0.0)
        # x_half should be close to 0.045-0.055 range
        self.assertGreater(bias_info['x_half'], 0.03)
        self.assertLess(bias_info['x_half'], 0.07)

        # Bias = x_half - target
        self.assertAlmostEqual(bias_info['bias'], bias_info['x_half'] - self.target, places=6)
        self.assertGreater(bias_info['se_bias'], 0.0)

        # Repeatability
        # pre-adjusted = 5.15 / slope
        # adjusted = pre-adjusted / 1.08
        expected_pre = 5.15 / reg['slope']
        expected_adj = expected_pre / 1.08
        self.assertAlmostEqual(rep_info['pre_adjusted'], expected_pre, places=6)
        self.assertAlmostEqual(rep_info['adjusted'], expected_adj, places=6)

        # %Repeatability = 100 * adjusted / tolerance
        expected_pct_rep = (expected_adj / self.tolerance) * 100.0
        self.assertAlmostEqual(rep_info['pct_repeatability'], expected_pct_rep, places=5)

        # Curve data
        self.assertIn('curve_x', plot_info)
        self.assertIn('curve_p', plot_info)
        self.assertGreater(len(plot_info['curve_x']), 50)

    def test_report_generation(self):
        res = compute_attribute_gage_study(
            reference_values=self.ref_values,
            acceptances=self.acceptances,
            trials=self.trials,
            settings={'target': self.target, 'tolerance': self.tolerance, 'gage_info': {'gage_name': 'Micrometer A'}},
        )
        rpt = generate_attribute_gage_report(res, reference_col="Reference", accept_col="Acceptances")
        self.assertIn("Attribute Gage Study (Analytic Method)", rpt)
        self.assertIn("Micrometer A", rpt)
        self.assertIn("Regression Equation", rpt)
        self.assertIn("Z =", rpt)
        self.assertIn("Repeatability", rpt)
        self.assertIn("Bias", rpt)
        self.assertIn("T-Statistic", rpt)

    def test_validation_errors(self):
        # Empty inputs
        with self.assertRaises(ValueError):
            compute_attribute_gage_study([], [], 20)

        # Length mismatch
        with self.assertRaises(ValueError):
            compute_attribute_gage_study([1.0, 2.0], [5], 20)

        # Invalid trials
        with self.assertRaises(ValueError):
            compute_attribute_gage_study([1.0, 2.0, 3.0], [1, 2, 3], 0)

        # Acceptances exceed trials
        with self.assertRaises(ValueError):
            compute_attribute_gage_study([1.0, 2.0, 3.0], [1, 25, 2], 20)

        # Fewer than 2 distinct ref values
        with self.assertRaises(ValueError):
            compute_attribute_gage_study([1.0, 1.0, 1.0], [1, 2, 3], 20)


class TestAttributeGageUIAndPresenter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def setUp(self):
        self.ws = Worksheet('Attribute Study Data', [
            Column('Part', 'text', ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']),
            Column('Reference', 'number', [0.015, 0.025, 0.035, 0.045, 0.055, 0.065, 0.075, 0.085]),
            Column('Accepts', 'number', [0, 1, 3, 10, 15, 18, 20, 20]),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_presenter_attribute_gage_and_recipe(self):
        entry = self.presenter.attribute_gage(
            ref_index=1,
            acc_index=2,
            trials=20,
            part_index=0,
            settings={'target': 0.050, 'tolerance': 0.080},
        )
        self.assertIsNotNone(entry)
        res = entry['result']
        self.assertEqual(res['analysis'], 'attribute_gage')
        self.assertEqual(res['graph'], 'attribute_gage')
        self.assertIn("Attribute Gage Study", entry['title'])

        formatted = format_entry(entry)
        self.assertIn("Attribute Gage Study", formatted)
        self.assertIn("Repeatability", formatted)

        # Verify recipe was recorded
        recipe = entry['recipe']
        self.assertEqual(recipe['action'], 'attribute_gage')
        self.assertEqual(recipe['parameters']['trials'], 20)
        self.assertIn('attribute_gage', recipes.FIELDS)

        # Verify rerun_result
        rerun_entry = self.presenter.rerun_result(entry)
        self.assertIsNotNone(rerun_entry)
        self.assertEqual(rerun_entry['result']['analysis'], 'attribute_gage')

    def test_chart_widget_rendering(self):
        res = compute_attribute_gage_study(
            reference_values=[0.015, 0.025, 0.035, 0.045, 0.055, 0.065, 0.075, 0.085],
            acceptances=[0, 1, 3, 10, 15, 18, 20, 20],
            trials=20,
            settings={'target': 0.050, 'tolerance': 0.080, 'gage_info': {'gage_name': 'OptiGage'}},
        )
        chart = AttributeGageChartWidget(res)
        chart.resize(800, 600)
        chart.show()
        QCoreApplication.processEvents()

        # Render to pixmap
        pm = chart.render_chart_pixmap(width=800, height=600)
        self.assertFalse(pm.isNull())
        self.assertEqual(pm.width(), 800)
        self.assertEqual(pm.height(), 600)
        chart.close()

    def test_dialogs(self):
        # AttributeGageDialog
        dlg = AttributeGageDialog(self.ws)
        dlg.edit_ref.setText("C2")
        dlg.edit_acc.setText("C3")
        dlg.edit_trials.setText("20")

        # Test options dialog
        opt_dlg = AttributeGageOptionsDialog(dlg.options, parent=dlg)
        opt_dlg.edit_target.setText("0.050")
        opt_dlg.edit_tolerance.setText("0.080")
        opt_dlg._validate_and_accept()
        dlg.options.update(opt_dlg.get_options())
        self.assertEqual(dlg.options['target'], 0.050)
        self.assertEqual(dlg.options['tolerance'], 0.080)

        # Test info dialog
        info_dlg = AttributeGageInfoDialog(dlg.gage_info, parent=dlg)
        info_dlg.edit_name.setText("LaserMic 2000")
        dlg.gage_info.update(info_dlg.get_info())
        self.assertEqual(dlg.gage_info['gage_name'], "LaserMic 2000")

        dlg._on_ok()
        p = dlg.result_params
        self.assertIsNotNone(p)
        self.assertEqual(p['ref_column'], 1)
        self.assertEqual(p['acc_column'], 2)
        self.assertEqual(p['trials'], 20)
        self.assertEqual(p['settings']['target'], 0.050)
        self.assertEqual(p['settings']['gage_info']['gage_name'], "LaserMic 2000")


if __name__ == '__main__':
    unittest.main()
