import copy
import unittest
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget, QDialog, QTableWidgetItem
from statcraft.model import Worksheet, Column
from statcraft.prediction import settings, model_spec
from statcraft.prediction_dialogs import PredictDialog, PredictOptionsDialog, PredictResultsDialog


class PresenterStub:
    def __init__(self):
        self.worksheet = Worksheet('Study', [Column('Response', 'number', [2, 5, 5, 9, 10]),
            Column('Temperature', 'number', [1, 2, 3, 4, 5]),
            Column('Batch', 'text', ['A', 'B', 'A', 'B', 'A']),
            Column('New temperature', 'number', [2, 3])])
        self.recipe = dict(action='multiple_regression', parameters=dict(response_index=0,
            predictor_indices=[1], confidence=.95))
        self.history = [dict(title='Fit', worksheet_name='Study', recipe=copy.deepcopy(self.recipe))]
        self.calls = []; self.failure = None

    def result_worksheet(self, entry):
        if entry.get('worksheet_name') != self.worksheet.name:
            raise ValueError('Different worksheet')
        return self.worksheet

    def predict_model(self, model_recipe, **p):
        if self.failure:
            raise ValueError(self.failure)
        self.calls.append((model_recipe, p))
        return dict(title='Prediction', recipe=dict(action='predict_model', parameters=dict(model_recipe=model_recipe, **p)))


class WindowStub(QWidget):
    def __init__(self):
        super().__init__(); self.presenter = PresenterStub(); self.events = []
    def refresh(self): self.events.append('refresh')
    def show_result(self, entry): self.events.append(('show', entry))


class PredictionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self): self.window = WindowStub()

    def tearDown(self):
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_no_models_and_family_filter_disable_ok(self):
        dialog = PredictDialog(self.window, 'glm')
        self.assertEqual(dialog.model_selector.count(), 0)
        self.assertIn('Fit a supported', dialog.error.text())
        dialog.validate(); self.assertEqual(self.window.presenter.calls, [])

    def test_source_unavailable_and_other_sheet_excluded(self):
        self.window.presenter.history[0]['source_unavailable'] = True
        self.assertEqual(PredictDialog(self.window).model_selector.count(), 0)
        self.window.presenter.history[0].pop('source_unavailable')
        self.window.presenter.history[0]['worksheet_name'] = 'Other'
        self.assertEqual(PredictDialog(self.window).model_selector.count(), 0)

    def test_named_predictor_and_identity_chooser(self):
        dialog = PredictDialog(self.window, 'regression')
        self.assertEqual(dialog.model_selector.currentData(), 0)
        self.assertIn('Temperature', dialog.values_grid.horizontalHeaderItem(0).text())
        self.assertEqual(dialog.model_recipe, self.window.presenter.recipe)
        self.assertIn('Response: Response', dialog.model_description())
        self.assertIn('current worksheet', dialog.model_description())

    def test_simple_regression_history_is_normalized_and_eligible(self):
        self.window.presenter.history[0]['recipe'] = dict(action='inference', parameters=dict(
            method='linear_regression', indices=[1, 0], mu=0, confidence=.95))
        dialog = PredictDialog(self.window, 'regression')
        self.assertEqual(dialog.model_selector.count(), 1)
        self.assertEqual(dialog.model_recipe, self.window.presenter.recipe)

    def test_large_model_history_refits_only_selected_model_and_caches_it(self):
        self.window.presenter.history *= 100
        with patch('statcraft.prediction_dialogs.model_spec', wraps=model_spec) as fit:
            dialog = PredictDialog(self.window)
            self.assertEqual(dialog.model_selector.count(), 1)
            self.assertEqual(fit.call_count, 1)
            dialog.change_model()
            self.assertEqual(fit.call_count, 1)
            dialog.model_selector.setCurrentIndex(0)
            self.assertEqual(fit.call_count, 1)

    def test_bad_selected_model_reports_inline_without_fitting_history(self):
        with patch('statcraft.prediction_dialogs.model_spec', side_effect=ValueError('Model singular')) as fit:
            dialog = PredictDialog(self.window)
            self.assertEqual(fit.call_count, 1)
            self.assertIn('singular', dialog.error.text())
            dialog.validate()
            self.assertEqual(self.window.presenter.calls, [])

    def test_manual_multiple_rows_and_result_dispatch(self):
        dialog = PredictDialog(self.window)
        dialog.values_grid.setItem(0, 0, QTableWidgetItem('2.5'))
        dialog.values_grid.setItem(2, 0, QTableWidgetItem('3.5'))
        dialog.validate()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.window.presenter.calls[0][1]['values'], [[2.5], [None], [3.5]])
        self.assertIsNone(self.window.presenter.calls[0][1]['new_indices'])
        self.assertEqual(self.window.events, ['refresh', ('show', dialog.entry)])

    def test_column_transfer_uses_named_reference_and_position(self):
        dialog = PredictDialog(self.window)
        dialog.input_mode.setCurrentIndex(1)
        self.assertEqual(dialog.available.count(), 3)
        dialog.available.setCurrentRow(2); dialog.transfer()
        self.assertIn('New temperature', dialog.columns_grid.item(0, 0).text())
        self.assertEqual(dialog.read_inputs(), (None, [3]))
        dialog.validate()
        self.assertEqual(self.window.presenter.calls[0][1]['input_mode'], 'columns')

    def test_manual_finite_and_empty_validation_do_not_mutate(self):
        dialog = PredictDialog(self.window)
        before = copy.deepcopy(self.window.presenter.worksheet)
        for value in ('nan', 'inf', 'bad', ''):
            dialog.values_grid.setItem(0, 0, QTableWidgetItem(value)); dialog.validate()
            self.assertTrue(dialog.error.text()); self.assertIsNone(dialog.entry)
        self.assertEqual(before, self.window.presenter.worksheet)
        self.assertEqual(self.window.events, [])

    def test_wrong_column_kind_rejected(self):
        dialog = PredictDialog(self.window); dialog.input_mode.setCurrentIndex(1)
        dialog.columns_grid.setItem(0, 0, QTableWidgetItem('C3'))
        dialog.validate(); self.assertIn('eligible', dialog.error.text())
        self.assertEqual(self.window.presenter.calls, [])

    def test_clear_row_does_not_clear_other_rows(self):
        dialog = PredictDialog(self.window)
        for row in (0, 1): dialog.values_grid.setItem(row, 0, QTableWidgetItem(str(row+1)))
        dialog.values_grid.setCurrentCell(0, 0); dialog.clear_row()
        self.assertEqual(dialog.read_inputs(), ([[None], [2.0]], None))

    def test_last_row_input_adds_another_blank_prediction_row(self):
        dialog = PredictDialog(self.window)
        dialog.values_grid.setItem(7, 0, QTableWidgetItem('5'))
        self.assertEqual(dialog.values_grid.rowCount(), 9)
        dialog.values_grid.setItem(8, 0, QTableWidgetItem('6'))
        self.assertEqual(dialog.values_grid.rowCount(), 10)
        self.assertEqual(dialog.read_inputs(), ([[None]]*7+[[5.0], [6.0]], None))

    def test_manual_row_expansion_stops_at_ui_limit(self):
        dialog = PredictDialog(self.window)
        dialog.values_grid.setRowCount(dialog.MAX_MANUAL_ROWS)
        dialog.values_grid.setItem(dialog.MAX_MANUAL_ROWS-1, 0, QTableWidgetItem('5'))
        self.assertEqual(dialog.values_grid.rowCount(), dialog.MAX_MANUAL_ROWS)
        dialog.values_grid.setRowCount(dialog.MAX_MANUAL_ROWS+1)
        dialog.validate(); self.assertIn('500 rows', dialog.error.text())
        self.assertEqual(self.window.presenter.calls, [])

    def test_large_saved_manual_input_stays_unloaded_with_explicit_message(self):
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='values', values=[[2]]*20000,
                 new_indices=None, options=settings())
        self.window.presenter.history.append(dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p)))
        dialog = PredictDialog(self.window)
        self.assertEqual(dialog.values_grid.rowCount(), 8)
        self.assertIn('input rows have not been loaded', dialog.error.text())
        self.assertIn('worksheet columns', dialog.error.text())
        self.assertIsNone(dialog.values_grid.item(0, 0))
        dialog.validate(); self.assertEqual(self.window.presenter.calls, [])

    def test_switch_factor_model_to_numeric_removes_stale_widgets(self):
        from statcraft.glm import settings as glm_settings
        glm_recipe = dict(action='general_linear_model', parameters=dict(response_index=0,
            factor_indices=[2], covariate_indices=[1], terms=[[0], [1]], options=glm_settings()))
        self.window.presenter.history.append(dict(worksheet_name='Study', recipe=glm_recipe))
        dialog = PredictDialog(self.window)
        self.assertIsNotNone(dialog.values_grid.cellWidget(0, 0))
        dialog.values_grid.setRowCount(30)
        dialog.model_selector.setCurrentIndex(0)
        self.assertEqual(dialog.values_grid.rowCount(), 8)
        self.assertEqual(dialog.values_grid.columnCount(), 1)
        self.assertIsNone(dialog.values_grid.cellWidget(0, 0))
        dialog.values_grid.setItem(0, 0, QTableWidgetItem('7'))
        self.assertEqual(dialog.read_inputs(), ([[7.0]], None))

    def test_invalid_saved_column_mapping_is_not_restored(self):
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='columns', values=None,
                 new_indices=[99], options=settings())
        self.window.presenter.history.append(dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p)))
        dialog = PredictDialog(self.window)
        self.assertEqual(dialog.input_mode.currentData(), 'values')

    def test_model_setup_and_options_restore_for_active_worksheet(self):
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='values', values=[[4.5]],
                 new_indices=None, options=settings())
        self.window.presenter.history.append(dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p)))
        dialog = PredictDialog(self.window)
        self.assertEqual(dialog.read_inputs(), ([[4.5]], None))
        self.assertEqual(dialog.options, settings())

    def test_retained_prediction_can_supply_model_without_original_fit_history(self):
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='values', values=[[4.5]],
                 new_indices=None, options=settings())
        entry = dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p))
        self.window.presenter.history = [entry]
        dialog = PredictDialog(self.window)
        self.assertEqual(dialog.model_selector.count(), 1)
        self.assertEqual(dialog.model_recipe, self.window.presenter.recipe)
        self.assertEqual(dialog.read_inputs(), ([[4.5]], None))
        entry['source_unavailable'] = True
        self.assertEqual(PredictDialog(self.window).model_selector.count(), 0)

    def test_predictions_do_not_duplicate_identical_model_setup(self):
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='values', values=[[4.5]],
                 new_indices=None, options=settings())
        self.window.presenter.history += [dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p))]*10
        self.assertEqual(PredictDialog(self.window).model_selector.count(), 1)

    def test_column_mapping_restores(self):
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='columns', values=None,
                 new_indices=[3], options=settings())
        self.window.presenter.history.append(dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p)))
        dialog = PredictDialog(self.window)
        self.assertEqual(dialog.read_inputs(), (None, [3]))

    def test_partial_missing_values_restore_as_blank_cells(self):
        spec = dict(model_title='General Linear Model', response_name='Response', predictor_names=['Batch','Temperature'],
            predictors=[dict(name='Batch', index=2, kind='text', role='factor', levels=['A','B']),
                        dict(name='Temperature', index=1, kind='number', role='covariate', levels=[])])
        p = dict(model_recipe=self.window.presenter.recipe, input_mode='values', values=[['A', None], [None, None], [None, 3]],
                 new_indices=None, options=settings())
        self.window.presenter.history.append(dict(worksheet_name='Study', recipe=dict(action='predict_model', parameters=p)))
        with patch('statcraft.prediction_dialogs.model_spec', return_value=spec):
            dialog = PredictDialog(self.window)
        self.assertEqual(dialog.values_grid.item(0, 1).text(), '')
        self.assertEqual(dialog.read_inputs(), ([['A', None], [None, None], [None, 3.0]], None))

    def test_engine_error_stays_in_dialog(self):
        dialog = PredictDialog(self.window); dialog.values_grid.setItem(0, 0, QTableWidgetItem('2'))
        self.window.presenter.failure = 'Model no longer estimable.'
        dialog.validate(); self.assertIn('estimable', dialog.error.text())
        self.assertIsNone(dialog.entry); self.assertEqual(self.window.events, [])

    def test_options_validation_and_cancel_transaction(self):
        original = settings(); child = PredictOptionsDialog(self.window, original)
        child.confidence.setText('100'); child.validate()
        self.assertIsNone(child.options); self.assertTrue(child.error.text())
        child.reject(); self.assertEqual(original, settings())

    def test_options_commit_confidence_side_and_intervals(self):
        child = PredictOptionsDialog(self.window, settings())
        child.confidence.setText('90'); child.side.setCurrentIndex(1); child.intervals.setCurrentIndex(1)
        child.validate()
        self.assertEqual(child.options['confidence'], .9)
        self.assertEqual(child.options['side'], 'lower')
        self.assertEqual(child.options['intervals'], 'confidence')

    def test_results_commit_and_cancel(self):
        original = settings(); child = PredictResultsDialog(self.window, original)
        child.equation.setChecked(False); child.reject()
        self.assertIsNone(child.options); self.assertTrue(original['show_equation'])
        child.validate(); self.assertFalse(child.options['show_equation']); self.assertTrue(child.options['show_table'])

    def test_children_cancel_does_not_modify_main_options(self):
        dialog = PredictDialog(self.window); before = dict(dialog.options)
        with patch.object(PredictOptionsDialog, 'exec', return_value=QDialog.DialogCode.Rejected):
            dialog.configure_options()
        with patch.object(PredictResultsDialog, 'exec', return_value=QDialog.DialogCode.Rejected):
            dialog.configure_results()
        self.assertEqual(dialog.options, before)

    def test_factor_controls_preserve_text_and_numeric_levels(self):
        spec = dict(model_title='General Linear Model', response_name='Response', predictor_names=['Batch','Temperature'],
            predictors=[dict(name='Batch', index=2, kind='text', role='factor', levels=['A','B']),
                        dict(name='Temperature', index=1, kind='number', role='factor', levels=[1,2])])
        with patch('statcraft.prediction_dialogs.model_spec', return_value=spec):
            dialog = PredictDialog(self.window)
        dialog.values_grid.cellWidget(0, 0).setCurrentIndex(2)
        dialog.values_grid.cellWidget(0, 1).setCurrentIndex(1)
        self.assertEqual(dialog.read_inputs(), ([['B', 1.0]], None))
        dialog.values_grid.cellWidget(1, 0).setCurrentIndex(1)
        self.assertEqual(dialog.read_inputs(), ([['B', 1.0], ['A', None]], None))


if __name__ == '__main__': unittest.main()
