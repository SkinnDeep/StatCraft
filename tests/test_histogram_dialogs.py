import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
import unittest

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit

from statcraft.histogram_dialogs import (HistogramDialog, HistogramScaleDialog,
    HistogramTypeDialog, MODES)
from statcraft.model import Column, Worksheet


class HistogramDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.sheet = Worksheet('Data', [Column('Strength (N)', values=[1, 2, 3, 4, 5, 6]),
            Column('Other response', values=[9, 8, 7, 6, 5, 4]),
            Column('Batch label', 'text', ['A', 'A', 'A', 'B', 'B', 'B'])])

    def test_gallery_has_four_exclusive_original_thumbnails(self):
        dialog = HistogramTypeDialog()
        try:
            self.assertEqual(list(dialog.mode_buttons), list(MODES))
            for mode, button in dialog.mode_buttons.items():
                self.assertFalse(button.icon().isNull())
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                self.assertEqual(dialog.mode, mode)
                self.assertEqual(sum(b.isChecked() for b in dialog.mode_buttons.values()), 1)
        finally:
            dialog.close()

    def test_named_multiple_responses_and_numeric_only_available(self):
        dialog = HistogramDialog(None, self.sheet)
        try:
            self.assertEqual(dialog.available.count(), 2)
            self.assertIn('Strength (N)', dialog.available.item(0).text())
            dialog.variables.setText('"Strength (N)" "Other response"')
            self.assertTrue(dialog.validate())
            self.assertEqual(dialog.settings()['response_indices'], [0, 1])
            settings = dialog.settings()
            settings['response_indices'].clear()
            self.assertEqual(dialog.settings()['response_indices'], [0, 1])
        finally:
            dialog.close()

    def test_focus_role_transfer_includes_text_groups(self):
        dialog = HistogramDialog(None, self.sheet, 'groups')
        try:
            dialog.available.item(0).setSelected(True)
            dialog.available.item(1).setSelected(True)
            dialog.transfer()
            dialog.activate('group')
            self.assertEqual(dialog.available.count(), 3)
            dialog.available.item(2).setSelected(True)
            dialog.transfer()
            dialog.arrangement.setCurrentIndex(1)
            self.assertTrue(dialog.validate())
            parameters = dialog.settings()
            self.assertEqual(parameters['response_indices'], [0, 1])
            self.assertEqual(parameters['group_index'], 2)
            self.assertEqual(parameters['layout'], 'panels')
        finally:
            dialog.close()

    def test_invalid_roles_and_fitted_subset_remain_open(self):
        dialog = HistogramDialog(None, self.sheet, 'fit_groups')
        before = deepcopy(self.sheet)
        try:
            dialog.variables.setText('C1')
            dialog.group.setText('C1')
            self.assertFalse(dialog.validate())
            self.assertIn('differ', dialog.error.text())
            self.assertIsNone(dialog.settings())
            dialog.group.setText('C3')
            self.sheet.columns[0].values = [1, 1, 1, 4, 5, 6]
            self.assertFalse(dialog.validate())
            self.assertIn('standard deviation', dialog.error.text())
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
            self.sheet.columns[0].values = before.columns[0].values
            self.assertTrue(dialog.validate())
            self.assertEqual(dialog.settings()['settings']['fit'], 'Normal')
            self.assertEqual(self.sheet, before)
        finally:
            dialog.close()

    def test_scale_control_density_disables_cumulative(self):
        dialog = HistogramScaleDialog({'cumulative': True, 'fit': 'Normal'})
        try:
            dialog.scale.setCurrentText('Density')
            self.assertFalse(dialog.cumulative.isEnabled())
            self.assertFalse(dialog.cumulative.isChecked())
            dialog.bins.setValue(24)
            self.assertEqual(dialog.settings(), {'bins': 24, 'scale': 'Density',
                'cumulative': False, 'fit': 'Normal'})
            dialog.scale.setCurrentText('Percent')
            self.assertTrue(dialog.cumulative.isEnabled())
        finally:
            dialog.close()

    def test_scale_subdialog_acceptance_and_cancellation(self):
        dialog = HistogramDialog(None, self.sheet, initial_columns=[0])
        try:
            def accept_scale():
                child = QApplication.activeModalWidget()
                child.bins.setValue(21)
                child.scale.setCurrentText('Percent')
                child.accept()
            QTimer.singleShot(0, accept_scale)
            dialog.edit_scale()
            self.assertEqual(dialog.histogram_settings['bins'], 21)
            def cancel_scale():
                child = QApplication.activeModalWidget()
                child.bins.setValue(67)
                child.reject()
            QTimer.singleShot(0, cancel_scale)
            dialog.edit_scale()
            self.assertEqual(dialog.histogram_settings['bins'], 21)
            self.assertTrue(dialog.validate())
            self.assertEqual(dialog.settings()['settings']['scale'], 'Percent')
        finally:
            dialog.close()

    def test_labels_subdialog_and_sparse_presentation(self):
        dialog = HistogramDialog(None, self.sheet)
        try:
            self.assertEqual(dialog.presentation_settings(), {})
            def enter_labels():
                child = QApplication.activeModalWidget()
                child.findChildren(QLineEdit)[0].setText('Strength by batch')
                child.findChildren(QLineEdit)[1].setText('Force (N)')
                child.accept()
            QTimer.singleShot(0, enter_labels)
            dialog.edit_labels()
            self.assertEqual(dialog.presentation_settings(),
                {'title': 'Strength by batch', 'x_label': 'Force (N)'})
        finally:
            dialog.close()

    def test_reopen_parameters_and_lock_variable_roles(self):
        parameters = dict(response_indices=[1], variant='fit_groups', group_index=2,
            layout='panels', settings={'bins': 18, 'scale': 'Percent',
                                     'cumulative': False, 'fit': 'Normal'})
        dialog = HistogramDialog(None, self.sheet, parameters=parameters, lock_variables=True)
        try:
            self.assertEqual(dialog.mode, 'fit_groups')
            for widget in (dialog.variables, dialog.group, dialog.available, dialog.select_button):
                self.assertFalse(widget.isEnabled())
            self.assertTrue(dialog.validate())
            self.assertEqual(dialog.settings(), parameters)
        finally:
            dialog.close()


if __name__ == '__main__':
    unittest.main()
