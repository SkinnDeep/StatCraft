"""Mouse/focus regressions for typed, positional MSA variable selection."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog
from statcraft.model import Worksheet,Column
from statcraft.msa_dialogs import (GageRRNestedDialog,GageRRNestedOptionsDialog,
    GageLinearityDialog,AttributeAgreementDialog)


class MsaDialogWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def setUp(self):
        self.sheet=Worksheet('MSA',[
            Column('Part label','text',['A','A','B','B']),
            Column('Operator','text',['X','X','Y','Y']),
            Column('Measurement',values=[1,2,3,4]),
            Column('Measurement',values=[5,6,7,8]),
            Column('Reference',values=[1,1,3,3]),
            Column('Rating','text',['Pass','Fail','Pass','Pass']),
            Column('Standard','text',['Pass','Pass','Pass','Pass']),
            Column('Trial',values=[1,2,1,2]),
            Column('Date','date',[46000,46001,46002,46003])])
        self.dialogs=[]

    def tearDown(self):
        for dialog in self.dialogs:dialog.close()
        self.app.processEvents()

    def show(self,cls):
        dialog=cls(self.sheet);self.dialogs.append(dialog);dialog.show();dialog.activateWindow()
        self.app.processEvents();return dialog

    def focus(self,field):
        QTest.mouseClick(field,Qt.MouseButton.LeftButton);self.app.processEvents()
        self.assertTrue(field.hasFocus())

    def select(self,dialog,index,double=False):
        item=next((dialog.col_list.item(row) for row in range(dialog.col_list.count())
            if dialog.col_list.item(row).data(Qt.ItemDataRole.UserRole)==index),None)
        self.assertIsNotNone(item)
        point=dialog.col_list.visualItemRect(item).center()
        QTest.mouseClick(dialog.col_list.viewport(),Qt.MouseButton.LeftButton,pos=point)
        if double:QTest.mouseDClick(dialog.col_list.viewport(),Qt.MouseButton.LeftButton,pos=point)
        else:QTest.mouseClick(dialog.btn_select,Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def ok(self,dialog):
        QTest.mouseClick(dialog.btn_ok,Qt.MouseButton.LeftButton);self.app.processEvents()

    def test_nested_mouse_select_tracks_each_role_and_duplicate_header_identity(self):
        dialog=self.show(GageRRNestedDialog)
        for field,index in [(dialog.edit_part,0),(dialog.edit_op,1),(dialog.edit_meas,3)]:
            self.focus(field);self.select(dialog,index)
        self.assertIn('C4:',dialog.edit_meas.text())
        self.assertIn('Measurement',dialog.edit_meas.text())
        self.assertEqual(dialog.edit_part.text(),'C1-T: "Part label"')
        self.ok(dialog)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_params['part_col'],0)
        self.assertEqual(dialog.selected_params['operator_col'],1)
        self.assertEqual(dialog.selected_params['measurement_col'],3)

    def test_linearity_double_click_preserves_last_focused_role(self):
        dialog=self.show(GageLinearityDialog)
        self.focus(dialog.edit_ref);self.select(dialog,4,double=True)
        self.focus(dialog.edit_meas);self.select(dialog,3,double=True)
        self.focus(dialog.edit_pv);QTest.keyClicks(dialog.edit_pv,'8')
        self.assertNotIn(8,[dialog.col_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(dialog.col_list.count())])
        self.ok(dialog)
        self.assertEqual(dialog.selected_params['reference_col'],4)
        self.assertEqual(dialog.selected_params['measurement_col'],3)
        self.assertIsNone(dialog.selected_params['part_col'])
        self.assertEqual(dialog.selected_params['process_variation'],8)

    def test_numeric_role_filters_list_and_manual_text_cannot_bypass(self):
        dialog=self.show(GageRRNestedDialog)
        self.focus(dialog.edit_meas)
        indices=[dialog.col_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(dialog.col_list.count())]
        self.assertEqual(indices,[2,3,4,7])
        dialog.edit_part.setText('C1');dialog.edit_op.setText('C2');dialog.edit_meas.setText('C6')
        self.ok(dialog)
        self.assertIsNone(dialog.selected_params)
        self.assertIn('eligible',dialog.error.text())

    def test_ambiguous_header_rejected_and_cnumber_recovers(self):
        dialog=self.show(GageLinearityDialog)
        dialog.edit_ref.setText('Reference');dialog.edit_meas.setText('Measurement')
        self.ok(dialog)
        self.assertIsNone(dialog.selected_params)
        self.assertIn('ambiguous',dialog.error.text())
        dialog.edit_meas.setText('C4');self.ok(dialog)
        self.assertEqual(dialog.selected_params['measurement_col'],3)

    def test_attribute_all_roles_including_optional_use_mouse_select(self):
        dialog=self.show(AttributeAgreementDialog)
        for attr,index in [('edit_meas',5),('edit_sample',0),('edit_app',1),('edit_std',6),('edit_trial',7)]:
            self.focus(getattr(dialog,attr));self.select(dialog,index,double=attr=='edit_std')
        self.ok(dialog)
        self.assertEqual(dialog.selected_params,{'attribute_col':5,'sample_col':0,'appraiser_col':1,'standard_col':6,'trial_col':7})

    def test_attribute_optional_invalid_reference_is_rejected(self):
        dialog=self.show(AttributeAgreementDialog)
        dialog.edit_meas.setText('C6');dialog.edit_sample.setText('C1');dialog.edit_app.setText('C2')
        dialog.edit_std.setText('C99');self.ok(dialog)
        self.assertIsNone(dialog.selected_params)
        dialog.edit_std.clear();self.ok(dialog)
        self.assertIsNone(dialog.selected_params['standard_col'])
        self.assertIsNone(dialog.selected_params['trial_col'])

    def test_linearity_invalid_process_variation_shows_inline_error(self):
        for value in ('nan','inf','0','-2','oops'):
            with self.subTest(value=value):
                dialog=self.show(GageLinearityDialog)
                dialog.edit_ref.setText('C5');dialog.edit_meas.setText('C3');dialog.edit_pv.setText(value)
                self.ok(dialog);self.assertIsNone(dialog.selected_params)
                self.assertIn('positive finite',dialog.error.text())
                dialog.close()

    def test_nested_options_positive_finite_validation(self):
        for attr,value in [('edit_multiplier','nan'),('edit_multiplier','0'),('edit_tolerance','inf'),('edit_tolerance','-1'),('edit_process_stdev','0'),('edit_process_stdev','bad')]:
            with self.subTest(attr=attr,value=value):
                dialog=GageRRNestedOptionsDialog();self.dialogs.append(dialog);dialog.show();self.app.processEvents()
                getattr(dialog,attr).setText(value);self.ok(dialog)
                self.assertIsNone(dialog.selected_options)
                self.assertIn('positive finite',dialog.error.text())
                dialog.close()

    def test_nested_options_reject_programmatic_invalid_values_on_main_ok(self):
        dialog=self.show(GageRRNestedDialog)
        dialog.edit_part.setText('C1');dialog.edit_op.setText('C2');dialog.edit_meas.setText('C3')
        dialog.options['study_multiplier']=float('inf');self.ok(dialog)
        self.assertIsNone(dialog.selected_params)


if __name__=='__main__':unittest.main()
