import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication, QDialog

from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget, supported
from statcraft.oneway import oneway_settings
from statcraft.oneway_dialogs import (
    OneWayAnovaDialog,
    OneWayComparisonsDialog,
    OneWayGraphsDialog,
    OneWayOptionsDialog,
    OneWayResultsDialog,
    OneWayStorageDialog,
)
from statcraft.office_export import OfficeSnapshot, export_docx, export_pptx


class TestOneWayIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _populate_window(self):
        win = ModernWindow()
        win.presenter.worksheet = Worksheet(
            'FabricDurability',
            [
                Column('Tensile', 'number', [7.0, 7.0, 15.0, 11.0, 9.0, 12.0, 17.0, 12.0, 18.0, 18.0, 14.0, 18.0, 18.0, 19.0, 19.0]),
                Column('Blend', 'text', ['Low', 'Low', 'Low', 'Low', 'Low', 'Med', 'Med', 'Med', 'Med', 'Med', 'High', 'High', 'High', 'High', 'High']),
                Column('LowBlend', 'number', [7.0, 7.0, 15.0, 11.0, 9.0]),
                Column('MedBlend', 'number', [12.0, 17.0, 12.0, 18.0, 18.0]),
                Column('HighBlend', 'number', [14.0, 18.0, 18.0, 19.0, 19.0]),
            ],
        )
        return win

    def test_stacked_dialog_and_children(self):
        win = self._populate_window()
        try:
            dlg = OneWayAnovaDialog(win)
            self.assertEqual(dlg.mode_combo.currentIndex(), 0)  # Stacked mode
            dlg.response_edit.setText('C1')
            dlg.factor_edit.setText('C2')

            # Test Child Dialogs
            # 1. Options
            opt_dlg = OneWayOptionsDialog(dlg, dlg.options)
            opt_dlg.conf_edit.setText('90.0')
            opt_dlg.chk_equal_var.setChecked(False)
            opt_dlg.validate()
            dlg.options = opt_dlg.options
            self.assertAlmostEqual(dlg.options['confidence'], 0.90)
            self.assertFalse(dlg.options['assume_equal_variances'])

            # Reset to 95 and equal var for comparisons test
            dlg.options['confidence'] = 0.95
            dlg.options['assume_equal_variances'] = True

            # 2. Comparisons
            comp_dlg = OneWayComparisonsDialog(dlg, dlg.options, ['Low', 'Med', 'High'])
            comp_dlg.chk_tukey.setChecked(True)
            comp_dlg.chk_fisher.setChecked(True)
            comp_dlg.chk_dunnett.setChecked(True)
            comp_dlg.cbo_control.setCurrentText('Low')
            comp_dlg.validate()
            dlg.options = comp_dlg.options
            self.assertTrue(dlg.options['comparisons']['tukey'])
            self.assertTrue(dlg.options['comparisons']['dunnett'])

            # 3. Graphs
            graph_dlg = OneWayGraphsDialog(dlg, dlg.options)
            graph_dlg.chk_interval.setChecked(True)
            graph_dlg.rad_four.setChecked(True)
            graph_dlg.validate()
            dlg.options = graph_dlg.options
            self.assertTrue(dlg.options['graphs']['interval_plot'])
            self.assertEqual(dlg.options['graphs']['residual_mode'], 'four_in_one')

            # 4. Storage
            stor_dlg = OneWayStorageDialog(dlg, dlg.options)
            stor_dlg.chk_fits.setChecked(True)
            stor_dlg.chk_res.setChecked(True)
            stor_dlg.validate()
            dlg.options = stor_dlg.options
            self.assertTrue(dlg.options['storage']['fits'])
            self.assertTrue(dlg.options['storage']['residuals'])

            # Validate main dialog
            col_count_before = len(win.presenter.worksheet.columns)
            dlg.validate()
            self.assertIsNotNone(dlg.entry)

            # Check that FITS and RESI columns were stored
            col_count_after = len(win.presenter.worksheet.columns)
            self.assertEqual(col_count_after, col_count_before + 2)
            names = [c.name for c in win.presenter.worksheet.columns]
            self.assertIn('FITS', names)
            self.assertIn('RESI', names)

            # Check chart rendering
            self.assertTrue(supported(dlg.entry))
            chart = ChartWidget(dlg.entry)
            self.assertGreaterEqual(len(chart.panels), 2)  # interval + differences + 4in1
            pixmap = chart.grab()
            self.assertFalse(pixmap.isNull())
            self.assertGreater(pixmap.width(), 0)
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()

    def test_unstacked_dialog(self):
        win = self._populate_window()
        try:
            dlg = OneWayAnovaDialog(win)
            dlg.mode_combo.setCurrentIndex(1)  # Unstacked mode
            dlg.responses_edit.setText('C3 C4 C5')
            dlg.validate()
            self.assertIsNotNone(dlg.entry)
            res = dlg.entry['result']
            self.assertEqual(res['analysis'], 'oneway_anova')
            self.assertEqual(res['anova_table']['df_factor'], 2)
            self.assertAlmostEqual(res['anova_table']['f_value'], 9.5889, places=2)
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()

    def test_mpx_save_reopen_and_column_move(self):
        win = self._populate_window()
        try:
            opts = oneway_settings({
                'confidence': 0.95,
                'assume_equal_variances': True,
                'comparisons': {'tukey': True},
            })
            entry = win.presenter.oneway_anova(response_index=0, factor_index=1, options=opts)
            self.assertEqual(entry['recipe']['action'], 'oneway_anova')

            # Move columns: move C1 (Tensile) to after_last
            win.presenter.move_columns([0], destination='after_last')
            # Recheck recipe parameters remapping
            rec = win.presenter.history[-1]['recipe']['parameters']
            # New response index should be updated
            self.assertNotEqual(rec['response_index'], 0)

            # Roundtrip MPX save and reopen
            with tempfile.TemporaryDirectory() as td:
                mpx_path = os.path.join(td, 'test_oneway.mpx')
                win.save_path(mpx_path)
                self.assertTrue(os.path.exists(mpx_path))

                # Reopen
                win2 = ModernWindow()
                try:
                    win2.load_path(mpx_path)
                    self.assertEqual(len(win2.presenter.history), len(win.presenter.history))
                    last_entry = win2.presenter.history[-1]
                    self.assertEqual(last_entry['recipe']['action'], 'oneway_anova')
                    self.assertTrue(supported(last_entry))
                finally:
                    win2.presenter.dirty = False
                    win2.presenter._results_dirty = False
                    win2.close()
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()

    def test_office_export(self):
        win = self._populate_window()
        try:
            opts = oneway_settings({
                'confidence': 0.95,
                'assume_equal_variances': True,
                'comparisons': {'tukey': True},
            })
            entry = win.presenter.oneway_anova(response_index=0, factor_index=1, options=opts)
            with tempfile.TemporaryDirectory() as td:
                docx_path = os.path.join(td, 'oneway_report.docx')
                pptx_path = os.path.join(td, 'oneway_report.pptx')

                from statcraft.oneway_report import text_report
                rep = text_report(entry['result'])
                snap = OfficeSnapshot('One-Way ANOVA', rep)

                export_docx(docx_path, snap)
                self.assertTrue(os.path.exists(docx_path))
                self.assertGreater(os.path.getsize(docx_path), 1000)

                export_pptx(pptx_path, snap)
                self.assertTrue(os.path.exists(pptx_path))
                self.assertGreater(os.path.getsize(pptx_path), 1000)
        finally:
            win.presenter.dirty = False
            win.presenter._results_dirty = False
            win.close()


if __name__ == '__main__':
    unittest.main()
