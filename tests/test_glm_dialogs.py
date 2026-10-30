import tempfile,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.modern_app import ModernWindow
from statcraft.glm import settings
from statcraft.glm_dialogs import GeneralLinearModelDialog,ModelTermsDialog,ModelSettingsDialog
from statcraft.glm_smoke import model_fixture,verify_general_linear_model
from statcraft.verification_fonts import load_verification_fonts


class GeneralLinearModelDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False);load_verification_fonts(cls.app)

    def setUp(self):
        self.p=Presenter();self.p.worksheet=model_fixture();self.w=ModernWindow(self.p);self.w.show();self.app.processEvents()

    def tearDown(self):
        self.p.dirty=False;self.p._results_dirty=False;self.w.close();self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_factor_selector_shows_named_text_columns_and_response_numeric_only(self):
        d=GeneralLinearModelDialog(self.w);self.assertEqual(d.available.count(),2);d.activate('factor_indices')
        self.assertIn('Material',d.available.item(1).text());d.available.item(1).setSelected(True);d.transfer();self.assertIn('Material',d.controls['factor_indices'].text())

    def test_bad_selection_keeps_dialog_and_document_unchanged(self):
        d=GeneralLinearModelDialog(self.w);d.controls['response_index'].setText('C1');d.controls['factor_indices'].setText('C1');d.validate()
        self.assertTrue(d.error.text());self.assertEqual(self.p.history,[]);self.assertFalse(self.p.dirty)

    def test_terms_hierarchy_validation_and_reorder(self):
        d=ModelTermsDialog(self.w,['A','B'],[[0],[1]]);d.order.setValue(2);d.add_order();d.selected.setCurrentRow(0);d.move(1)
        self.assertEqual(d.chosen(),[[1],[0],[0,1]]);d.remove();d.validate();self.assertIn('lower-order',d.error.text())

    def test_cancel_child_does_not_apply_options(self):
        original=settings();d=ModelSettingsDialog(self.w,'Options',original);d.controls['confidence'].setValue(80);d.reject()
        self.assertIsNone(d.options);self.assertEqual(original['confidence'],.95)

    def test_results_options_are_effective(self):
        d=GeneralLinearModelDialog(self.w);d.controls['response_index'].setText('C1');d.controls['factor_indices'].setText('C2 C3');d.options['coefficients']=False;d.validate()
        self.assertFalse(d.error.text());self.assertEqual(self.w.result_tabs.tabText(self.w.result_tabs.currentIndex()),'Report')
        from statcraft.app import format_entry
        self.assertNotIn('Coefficients',format_entry(d.entry));self.assertIn('Analysis of Variance',format_entry(d.entry))

    def test_saved_setup_restores_after_column_move(self):
        self.p.general_linear_model(0,[1,2],[3],options=dict(settings(),graphs='fitted'));self.p.move_columns([2],'before_column',0)
        d=GeneralLinearModelDialog(self.w);self.assertIn('C1-T',d.controls['factor_indices'].text());self.assertEqual(d.options['graphs'],'fitted')

    def test_complete_clickable_ui_mpx_workflow(self):
        with tempfile.TemporaryDirectory() as temp:verify_general_linear_model(self.app,self.p,self.w,temp,lambda *args:None)


if __name__=='__main__':unittest.main()
