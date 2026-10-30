import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from statcraft.histogram_options_dialog import HistogramOptionsDialog


class HistogramOptionsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_missing_source_cannot_be_reconstructed_from_bins(self):
        dialog = HistogramOptionsDialog({'result': {'graph_data': [[0, 1], [5]]}})
        try:
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
            self.assertFalse(dialog.validate())
            self.assertIsNone(dialog.settings())
            self.assertIn('Rerun', dialog.error.text())
        finally:
            dialog.close()

    def test_accept_preserves_entry_and_returns_detached_settings(self):
        entry = {'result': {'histogram_source': [0, 1, 2]},
                 'histogram_settings': {'bins': 3, 'scale': 'Percent', 'fit': 'Normal'}}
        dialog = HistogramOptionsDialog(entry)
        try:
            self.assertEqual(dialog.bins.value(), 3)
            self.assertEqual(dialog.bins.minimum(), 2)
            self.assertEqual(dialog.bins.maximum(), 1000)
            self.assertTrue(dialog.validate())
            accepted = dialog.settings()
            self.assertEqual(accepted['scale'], 'Percent')
            accepted['bins'] = 9
            self.assertEqual(dialog.settings()['bins'], 3)
            self.assertNotIn('cumulative', entry['histogram_settings'])
        finally:
            dialog.close()

    def test_invalid_combination_is_inline_error(self):
        dialog = HistogramOptionsDialog({'result': {'histogram_source': [0, 1, 2]}})
        try:
            dialog.scale.setCurrentText('Density')
            dialog.cumulative.setChecked(True)
            self.assertFalse(dialog.validate())
            self.assertIn('Frequency or Percent', dialog.error.text())
            self.assertIsNone(dialog.settings())
        finally:
            dialog.close()


if __name__ == '__main__':
    unittest.main()
