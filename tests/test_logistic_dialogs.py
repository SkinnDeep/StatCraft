import copy
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget, QDialog
from statcraft.model import Worksheet, Column
from statcraft.logistic import settings
from statcraft.logistic_dialogs import BinaryLogisticDialog, LogisticSettingsDialog


class PresenterStub:
    def __init__(self):
        self.worksheet=Worksheet('Study',[
            Column('Pass or fail','text',['Pass','Fail','Pass','Fail']),
            Column('Temperature','number',[10,20,30,40]),
            Column('Material type','text',['A','B','A','B']),
            Column('Events','number',[2,3,5,7]),
            Column('Trials','number',[10,10,10,10]),
            Column('Numeric response','number',[0,1,0,1])])
        self.native_project=None; self.history=[]; self.calls=[]; self.failure=None
    def fit_binary_logistic(self,**values):
        if self.failure: raise ValueError(self.failure)
        self.calls.append(copy.deepcopy(values))
        entry=dict(worksheet_name=self.worksheet.name,worksheet_id=None,
            recipe=dict(action='fit_binary_logistic',parameters=copy.deepcopy(values)))
        self.history.append(entry); return entry


class WindowStub(QWidget):
    def __init__(self):
        super().__init__(); self.presenter=PresenterStub(); self.events=[]
    def refresh(self): self.events.append('refresh')
    def show_result(self,entry): self.events.append(('show',entry))


class BinaryLogisticDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self): self.window=WindowStub(); self.p=self.window.presenter
    def tearDown(self):
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete); self.app.processEvents()
    def ready(self):
        d=BinaryLogisticDialog(self.window); d.controls['response_index'].setText('C1')
        d.controls['continuous_indices'].setText('C2'); return d
    def test_named_variable_lists_filter_by_role(self):
        d=self.ready(); self.assertIn('Pass or fail',d.available.item(0).text())
        d.activate('continuous_indices'); self.assertEqual(d.available.count(),4)
        self.assertIn('Temperature',d.available.item(0).text())
        d.activate('categorical_indices'); self.assertEqual(d.available.count(),6)
        d.available.item(2).setSelected(True); d.transfer()
        self.assertIn('Material type',d.controls['categorical_indices'].text())
    def test_text_event_preserves_exact_value(self):
        d=self.ready(); d.select_event('Pass'); d.validate()
        self.assertFalse(d.error.text()); self.assertEqual(self.p.calls[0]['event'],'Pass')
        self.assertIsNone(self.p.calls[0]['trials_index']); self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(self.window.events[0],'refresh')
    def test_numeric_event_preserves_number(self):
        d=self.ready(); d.controls['response_index'].setText('C6'); d.select_event(1)
        # Numeric column cells retain their stored numeric type in the combo.
        d.validate(); self.assertEqual(self.p.calls[0]['event'],1)
        self.assertIsInstance(self.p.calls[0]['event'],(int,float))
    def test_zero_numeric_event_survives_restore_and_grouped_mode_ignores_it(self):
        d=self.ready(); d.controls['response_index'].setText('C6'); d.select_event(0); d.validate()
        self.assertEqual(self.p.calls[0]['event'],0)
        restored=BinaryLogisticDialog(self.window)
        self.assertEqual(restored.event.currentData(),0)
        self.assertIsNotNone(restored.event.currentData())
        restored.response_format.setCurrentIndex(1)
        self.assertFalse(restored.event.isEnabled())
        restored.controls['response_index'].setText('C4'); restored.controls['trials_index'].setText('C5')
        restored.validate(); self.assertIsNone(self.p.calls[-1]['event'])
    def test_grouped_ignores_individual_event(self):
        d=self.ready(); d.select_event('Pass'); d.response_format.setCurrentIndex(1)
        d.controls['response_index'].setText('C4'); d.controls['trials_index'].setText('C5')
        self.assertFalse(d.event.isEnabled()); d.validate()
        self.assertEqual(self.p.calls[0]['trials_index'],4); self.assertIsNone(self.p.calls[0]['event'])
    def test_individual_ignores_hidden_invalid_trials(self):
        d=self.ready(); d.controls['trials_index'].setText('this is invalid')
        d.validate(); self.assertIsNone(self.p.calls[0]['trials_index'])
    def test_grouped_requires_numeric_counts_and_trials(self):
        d=self.ready(); d.response_format.setCurrentIndex(1); d.validate()
        self.assertTrue(d.error.text()); self.assertEqual(self.p.calls,[])
        d.controls['response_index'].setText('C4'); d.validate()
        self.assertIn('trials',d.error.text()); self.assertEqual(self.p.calls,[])
    def test_grouped_rejects_same_count_and_trials(self):
        d=self.ready(); d.response_format.setCurrentIndex(1)
        d.controls['response_index'].setText('C4'); d.controls['trials_index'].setText('C4'); d.validate()
        self.assertIn('separate',d.error.text()); self.assertEqual(self.p.calls,[])
    def test_at_least_one_distinct_predictor(self):
        d=self.ready(); d.controls['continuous_indices'].clear(); d.validate()
        self.assertIn('1–8',d.error.text()); self.assertEqual(self.p.calls,[])
        d.controls['continuous_indices'].setText('C2'); d.controls['categorical_indices'].setText('C2'); d.validate()
        self.assertIn('distinct',d.error.text()); self.assertEqual(self.p.calls,[])
    def test_categorical_only_is_valid(self):
        d=self.ready(); d.controls['continuous_indices'].clear(); d.controls['categorical_indices'].setText('C3'); d.validate()
        self.assertFalse(d.error.text()); self.assertEqual(self.p.calls[0]['continuous_indices'],[])
    def test_terms_order_categorical_before_continuous(self):
        d=self.ready(); d.controls['categorical_indices'].setText('C3'); values,indices=d.roles()
        self.assertEqual(indices,[2,1]); self.assertEqual(d.terms,[[0],[1]])
        d.terms=[[0],[1],[0,1]]; d.validate()
        self.assertEqual(self.p.calls[0]['terms'],[[0],[1],[0,1]])
    def test_changing_roles_resets_old_interactions(self):
        d=self.ready(); d.controls['categorical_indices'].setText('C3'); d.roles(); d.terms=[[0],[1],[0,1]]
        d.controls['categorical_indices'].clear(); d.roles(); self.assertEqual(d.terms,[[0]])
    def test_presenter_error_stays_open_without_refresh(self):
        d=self.ready(); self.p.failure='Complete separation'; d.validate()
        self.assertEqual(d.error.text(),'Complete separation'); self.assertEqual(self.window.events,[])
        self.assertEqual(d.result(),QDialog.DialogCode.Rejected)
    def test_main_cancel_never_mutates_presenter(self):
        d=self.ready(); d.reject(); self.assertEqual(self.p.calls,[]); self.assertEqual(self.window.events,[])
    def test_options_work_and_cancel_does_not_mutate(self):
        original=settings(); d=LogisticSettingsDialog(self.window,'Options',original)
        d.controls['confidence'].setValue(90); d.controls['threshold'].setValue(.7); d.reject()
        self.assertIsNone(d.options); self.assertEqual(original,settings())
        d.validate(); self.assertEqual(d.options['confidence'],.9); self.assertEqual(d.options['threshold'],.7)
    def test_graphs_and_results_settings(self):
        d=LogisticSettingsDialog(self.window,'Graphs',settings()); d.controls['graphs'].setCurrentIndex(1); d.validate()
        self.assertEqual(d.options['graphs'],'four')
        self.assertEqual(d.controls['graphs'].currentText(),'Four-panel diagnostic dashboard')
        d=LogisticSettingsDialog(self.window,'Results',settings())
        for key in ('method','response_information','coefficients','odds_ratios','equation','model_summary'): d.controls[key].setChecked(False)
        d.controls['diagnostics'].setCurrentIndex(2); d.validate()
        self.assertEqual(d.options['diagnostics'],'all'); self.assertFalse(d.options['coefficients'])
    def test_configure_child_cancel_preserves_main_settings(self):
        d=self.ready(); original=copy.deepcopy(d.options)
        with patch('statcraft.logistic_dialogs.LogisticSettingsDialog.exec',return_value=QDialog.DialogCode.Rejected): d.configure('Options')
        self.assertEqual(d.options,original)
    def test_restore_supported_recipe_with_names_event_and_options(self):
        d=self.ready(); d.select_event('Fail'); d.controls['categorical_indices'].setText('C3')
        d.roles(); d.terms=[[0],[1],[0,1]]; d.options['graphs']='four'; d.validate()
        restored=BinaryLogisticDialog(self.window)
        self.assertIn('Pass or fail',restored.controls['response_index'].text())
        self.assertIn('Material type',restored.controls['categorical_indices'].text())
        self.assertEqual(restored.event.currentData(),'Fail'); self.assertEqual(restored.terms,[[0],[1],[0,1]])
        self.assertEqual(restored.options['graphs'],'four')
    def test_restore_grouped_mode(self):
        d=self.ready(); d.response_format.setCurrentIndex(1)
        d.controls['response_index'].setText('C4'); d.controls['trials_index'].setText('C5'); d.validate()
        restored=BinaryLogisticDialog(self.window)
        self.assertEqual(restored.response_format.currentData(),'grouped')
        self.assertIn('Trials',restored.controls['trials_index'].text()); self.assertFalse(restored.event.isEnabled())
    def test_other_worksheet_history_not_restored(self):
        d=self.ready(); d.validate(); self.p.history[-1]['worksheet_name']='Other'
        restored=BinaryLogisticDialog(self.window); self.assertEqual(restored.controls['response_index'].text(),'')
    def test_native_worksheet_identity_restores_after_rename(self):
        d=self.ready(); d.validate(); entry=self.p.history[-1]; entry['worksheet_id']='stable-id'
        self.p.native_project=SimpleNamespace(worksheet_ids=['stable-id'],active_index=0)
        self.p.worksheet.name='Renamed Study'
        self.p.result_worksheet=lambda result:self.p.worksheet if result.get('worksheet_id')=='stable-id' else None
        restored=BinaryLogisticDialog(self.window)
        self.assertIn('Pass or fail',restored.controls['response_index'].text())
    def test_result_resolver_rejects_different_worksheet(self):
        d=self.ready(); d.validate()
        self.p.result_worksheet=lambda result:Worksheet('Other',[])
        restored=BinaryLogisticDialog(self.window)
        self.assertEqual(restored.controls['response_index'].text(),'')
    def test_supported_options_only(self):
        d=self.ready(); self.assertEqual(set(d.option_buttons),{'Model','Options','Graphs','Results'})
        self.assertEqual(d.windowTitle(),'Fit Binary Logistic Model')


if __name__=='__main__': unittest.main()
