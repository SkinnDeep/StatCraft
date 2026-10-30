import copy
import unittest
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from statcraft.model import Worksheet, Column
from statcraft.gage_rr import settings
from statcraft.gage_rr_dialogs import GageRRDialog, GageRROptionsDialog


class PresenterStub:
    def __init__(self):
        self.worksheet = Worksheet('Gage worksheet', [
            Column('Part ID', 'text', ['P1', 'P1', 'P2', 'P2']),
            Column('Inspector', 'text', ['A', 'B', 'A', 'B']),
            Column('Diameter', 'number', [1.1, 1.2, 2.1, 2.2]),
            Column('Measured on', 'date', [45000, 45000, 45001, 45001])])
        self.native_project = None
        self.history = []
        self.calls = []
        self.failure = None

    def gage_rr(self, **parameters):
        if self.failure:
            raise ValueError(self.failure)
        self.calls.append(parameters)
        return {'title': 'Gage R&R Study', 'recipe': {'action': 'gage_rr', 'parameters': parameters}}

    def result_worksheet(self, entry):
        if entry.get('worksheet_name') != self.worksheet.name:
            raise ValueError('Unavailable worksheet.')
        return self.worksheet


class WindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.presenter = PresenterStub()
        self.events = []

    def refresh(self):
        self.events.append('refresh')

    def show_result(self, entry):
        self.events.append(('show', entry))


class GageRRDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.window = WindowStub()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def choose(self, dialog):
        for key, reference in [('part_index', 'C1'), ('operator_index', 'C2'), ('measurement_index', 'C3')]:
            dialog.controls[key].setText(reference)

    def test_named_eligible_columns_follow_focused_role(self):
        dialog = GageRRDialog(self.window)
        self.assertEqual(dialog.available.count(), 3)
        self.assertIn('Part ID', dialog.available.item(0).text())
        dialog.available.item(0).setSelected(True)
        dialog.transfer()
        self.assertIn('C1-T: "Part ID"', dialog.controls['part_index'].text())
        dialog.activate('measurement_index')
        self.assertEqual(dialog.available.count(), 1)
        self.assertIn('Diameter', dialog.available.item(0).text())
        self.assertEqual(dialog.windowTitle(), 'Gage R&R Study (Crossed)')

    def test_distinct_roles_error_preserves_document(self):
        dialog = GageRRDialog(self.window)
        self.choose(dialog)
        dialog.controls['operator_index'].setText('C1')
        before = copy.deepcopy(self.window.presenter.worksheet)
        dialog.validate()
        self.assertIn('separate columns', dialog.error.text())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(self.window.presenter.calls, [])
        self.assertEqual(self.window.presenter.worksheet, before)

    def test_text_measurement_is_rejected(self):
        dialog = GageRRDialog(self.window)
        self.choose(dialog)
        dialog.controls['measurement_index'].setText('C1')
        dialog.validate()
        self.assertIn('eligible', dialog.error.text())
        self.assertEqual(self.window.presenter.calls, [])

    def test_engine_validation_stays_open_without_results(self):
        self.window.presenter.failure = 'Each part/operator cell needs repeated measurements.'
        dialog = GageRRDialog(self.window)
        self.choose(dialog)
        dialog.validate()
        self.assertIn('repeated measurements', dialog.error.text())
        self.assertEqual(self.window.events, [])
        self.assertIsNone(dialog.entry)

    def test_supported_options_apply_and_result_is_shown_after_refresh(self):
        dialog = GageRRDialog(self.window)
        self.choose(dialog)
        dialog.options = settings({'study_multiplier': 5.15, 'tolerance': 8,
                                   'process_stdev': 2, 'interaction_alpha': .1,
                                   'remove_interaction': False})
        dialog.validate()
        self.assertFalse(dialog.error.text())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.window.presenter.calls[0]['options']['tolerance'], 8)
        self.assertEqual(self.window.events, ['refresh', ('show', dialog.entry)])

    def test_options_validation_and_cancel_are_transactional(self):
        initial = settings()
        original = dict(initial)
        child = GageRROptionsDialog(self.window, initial)
        child.controls['tolerance'].setText('-3')
        child.validate()
        self.assertTrue(child.error.text())
        self.assertIsNone(child.options)
        child.controls['tolerance'].setText('8')
        child.reject()
        self.assertIsNone(child.options)
        self.assertEqual(initial, original)

    def test_options_confirm_values_and_optional_empty_values(self):
        child = GageRROptionsDialog(self.window, settings())
        child.controls['study_multiplier'].setText('5.15')
        child.controls['tolerance'].setText('8')
        child.controls['process_stdev'].setText('2.3')
        child.controls['interaction_alpha'].setText('.1')
        child.controls['remove_interaction'].setChecked(False)
        child.validate()
        self.assertEqual(child.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(child.options, settings({'study_multiplier': 5.15, 'tolerance': 8,
            'process_stdev': 2.3, 'interaction_alpha': .1, 'remove_interaction': False}))
        reopened = GageRROptionsDialog(self.window, child.options)
        self.assertEqual(float(reopened.controls['study_multiplier'].text()), 5.15)
        reopened.controls['process_stdev'].clear()
        reopened.controls['tolerance'].clear()
        reopened.validate()
        self.assertIsNone(reopened.options['process_stdev'])
        self.assertIsNone(reopened.options['tolerance'])

    def test_child_cancel_and_main_cancel_do_not_mutate_data(self):
        dialog = GageRRDialog(self.window)
        self.choose(dialog)
        original = dict(dialog.options)
        before = copy.deepcopy(self.window.presenter.worksheet)
        with patch('statcraft.gage_rr_dialogs.GageRROptionsDialog.exec', return_value=QDialog.DialogCode.Rejected):
            dialog.configure_options()
        self.assertEqual(dialog.options, original)
        dialog.reject()
        self.assertEqual(self.window.presenter.worksheet, before)
        self.assertEqual(self.window.presenter.calls, [])

    def test_last_setup_restores_named_roles_and_options_for_same_sheet(self):
        values = {'part_index': 0, 'operator_index': 1, 'measurement_index': 2,
                  'options': settings({'tolerance': 8})}
        self.window.presenter.history.append({'worksheet_name': 'Gage worksheet',
            'worksheet_id': None, 'recipe': {'action': 'gage_rr', 'parameters': values}})
        dialog = GageRRDialog(self.window)
        self.assertIn('Part ID', dialog.controls['part_index'].text())
        self.assertIn('Diameter', dialog.controls['measurement_index'].text())
        self.assertEqual(dialog.options['tolerance'], 8)


if __name__ == '__main__':
    unittest.main()
