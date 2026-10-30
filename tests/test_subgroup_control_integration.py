import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication, QDialog

from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget, supported
from statcraft.subgroup_control import control_chart_settings
from statcraft.subgroup_control_dialogs import (
    XbarRChartDialog,
    XbarSChartDialog,
    ControlChartOptionsDialog,
)
from statcraft.subgroup_control_report import text_report
from statcraft.office_export import OfficeSnapshot, export_docx, export_pptx


class TestSubgroupControlIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _populate_window(self):
        win = ModernWindow()
        # 20 observations in 4 subgroups of size 5:
        # S1: 10, 11, 12, 11, 10
        # S2: 12, 13, 14, 13, 12
        # S3: 15, 16, 17, 16, 15
        # S4: 20, 21, 22, 21, 20
        meas = [10.0, 11.0, 12.0, 11.0, 10.0,
                12.0, 13.0, 14.0, 13.0, 12.0,
                15.0, 16.0, 17.0, 16.0, 15.0,
                20.0, 21.0, 22.0, 21.0, 20.0]
        sub_id = ['Batch1']*5 + ['Batch2']*5 + ['Batch3']*5 + ['Batch4']*5
        win.presenter.worksheet = Worksheet(
            'ProcessLog',
            [
                Column('Diameter', 'number', meas),
                Column('BatchID', 'text', sub_id),
                Column('Sample1', 'number', [10.0, 12.0, 15.0, 20.0]),
                Column('Sample2', 'number', [11.0, 13.0, 16.0, 21.0]),
                Column('Sample3', 'number', [12.0, 14.0, 17.0, 22.0]),
                Column('Sample4', 'number', [11.0, 13.0, 16.0, 21.0]),
                Column('Sample5', 'number', [10.0, 12.0, 15.0, 20.0]),
            ],
        )
        return win

    def test_xbar_r_dialog_and_child_options(self):
        win = self._populate_window()
        try:
            dlg = XbarRChartDialog(win)
            self.assertEqual(dlg.combo_arrangement.currentIndex(), 0)  # Stacked
            dlg.resp_edit.setText('C1')
            dlg.sub_size_edit.setText('C2')

            # Child Options Dialog
            opt_dlg = ControlChartOptionsDialog(dlg, dlg.options, chart_type='xbar_r')
            opt_dlg.mean_edit.setText('14.5')
            opt_dlg.sigma_edit.setText('3.2')
            opt_dlg.ksigma_edit.setText('3.0')
            opt_dlg.chk_perform_all.setChecked(True)
            opt_dlg.chk_s_points.setChecked(True)
            opt_dlg.chk_s_center.setChecked(True)
            opt_dlg.chk_s_limits.setChecked(True)
            opt_dlg.validate()

            dlg.options = opt_dlg.options
            self.assertEqual(dlg.options['historical_mean'], 14.5)
            self.assertEqual(dlg.options['historical_sigma'], 3.2)
            self.assertTrue(dlg.options['tests']['test2']['enabled'])
            self.assertTrue(dlg.options['storage']['points'])

            dlg.run_analysis()
            self.assertEqual(len(win.presenter.history), 1)
            entry = win.presenter.history[0]
            self.assertIn("Xbar-R Chart", entry['title'])
            self.assertEqual(entry['result']['analysis'], 'subgroup_control')
            self.assertEqual(entry['result']['chart_type'], 'xbar_r')

            # Chart widget supported and prepare
            self.assertTrue(supported(entry['result']))
            chart = ChartWidget(entry['result'])
            self.assertEqual(len(chart.panels), 2)
            self.assertEqual(chart.panels[0]['subpanel'], 'xbar')
            self.assertEqual(chart.panels[1]['subpanel'], 'disp')

            # Office export
            with tempfile.TemporaryDirectory() as td:
                docx_path = Path(td) / 'XbarR.docx'
                pptx_path = Path(td) / 'XbarR.pptx'
                rep = text_report(entry['result'])
                snap = OfficeSnapshot('Xbar-R Chart', rep)
                export_docx(str(docx_path), snap)
                export_pptx(str(pptx_path), snap)
                self.assertTrue(docx_path.exists())
                self.assertTrue(pptx_path.exists())
                self.assertGreater(docx_path.stat().st_size, 1000)
                self.assertGreater(pptx_path.stat().st_size, 1000)
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()

    def test_xbar_s_dialog_unstacked_mode(self):
        win = self._populate_window()
        try:
            dlg = XbarSChartDialog(win)
            dlg.combo_arrangement.setCurrentIndex(1)  # Unstacked row columns
            self.assertFalse(dlg.unstacked_widget.isHidden())
            self.assertTrue(dlg.stacked_widget.isHidden())
            dlg.rows_edit.setText('C3 C4 C5 C6 C7')

            dlg.run_analysis()
            self.assertEqual(len(win.presenter.history), 1)
            entry = win.presenter.history[0]
            self.assertIn("Xbar-S Chart", entry['title'])
            self.assertEqual(entry['result']['analysis'], 'subgroup_control')
            self.assertEqual(entry['result']['chart_type'], 'xbar_s')

            # Verify unstacked recipe
            recipe = entry['recipe']
            self.assertEqual(recipe['action'], 'subgroup_control_chart')
            self.assertFalse(recipe['parameters']['stacked'])
            self.assertEqual(recipe['parameters']['indices'], [2, 3, 4, 5, 6])
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()

    def test_column_movement_and_recipe_remapping(self):
        win = self._populate_window()
        try:
            # Run stacked Xbar-R with response C1 and factor C2
            res = win.presenter.subgroup_control_chart(
                chart_type='xbar_r',
                stacked=True,
                response_index=0,
                factor_index=1,
            )
            entry = win.presenter.history[0]
            orig_res = entry['result']

            # Insert 2 columns before C1
            win.presenter.insert_columns(0, 2)
            # Response should now be at index 2, factor at index 3
            self.assertEqual(entry['recipe']['parameters']['response_index'], 2)
            self.assertEqual(entry['recipe']['parameters']['factor_index'], 3)

            # Rerun result
            rerun_entry = win.presenter.rerun_result(entry)
            self.assertEqual(rerun_entry['result']['means'], orig_res['means'])
            self.assertAlmostEqual(rerun_entry['result']['within_stdev'], orig_res['within_stdev'], places=7)
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()


if __name__ == '__main__':
    unittest.main()
