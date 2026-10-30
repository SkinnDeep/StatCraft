"""Real focus/selection paths and specification mapping for multiple capability."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from statcraft.model import Worksheet,Column
from statcraft.multiple_capability_dialogs import MultipleCapabilityDialog,MultipleCapabilityOptionsDialog


class MultipleCapabilityDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def setUp(self):
        self.sheet=Worksheet('Capability',[
            Column('Diameter',values=[10,11,10,12,9,11,10,9]),
            Column('Diameter',values=[20,21,20,22,19,21,20,19]),
            Column('Shift','text',['A']*4+['B']*4),
            Column('Subgroup','text',['a','a','b','b','c','c','d','d'])])
        self.dialogs=[]

    def tearDown(self):
        for dialog in self.dialogs:dialog.close()
        self.app.processEvents()

    def dialog(self,method='normal'):
        dialog=MultipleCapabilityDialog(self.sheet,method);self.dialogs.append(dialog)
        dialog.show();dialog.activateWindow();self.app.processEvents();return dialog

    def focus(self,field):
        QTest.mouseClick(field,Qt.MouseButton.LeftButton);self.app.processEvents();self.assertTrue(field.hasFocus())

    def transfer(self,dialog,index,double=False):
        item=next(dialog.col_list.item(i) for i in range(dialog.col_list.count()) if dialog.col_list.item(i).data(Qt.ItemDataRole.UserRole)==index)
        point=dialog.col_list.visualItemRect(item).center()
        QTest.mouseClick(dialog.col_list.viewport(),Qt.MouseButton.LeftButton,pos=point)
        if double:QTest.mouseDClick(dialog.col_list.viewport(),Qt.MouseButton.LeftButton,pos=point)
        else:QTest.mouseClick(dialog.btn_select,Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def ok(self,dialog):QTest.mouseClick(dialog.btn_ok,Qt.MouseButton.LeftButton);self.app.processEvents()

    def test_named_duplicate_variables_selected_with_actual_mouse(self):
        dialog=self.dialog();self.focus(dialog.edit_variables)
        self.assertEqual(dialog.col_list.count(),2)
        self.transfer(dialog,0);self.transfer(dialog,1,double=True)
        self.assertIn('C1: "Diameter"',dialog.edit_variables.text())
        self.assertIn('C2: "Diameter"',dialog.edit_variables.text())
        dialog.edit_lower.setText('8 18');dialog.edit_upper.setText('13 23');dialog.edit_subgroup_sizes.setText('2 2')
        self.ok(dialog)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertIs(dialog.parameters,dialog.selected_params)
        self.assertEqual(dialog.parameters['variable_indices'],[0,1])
        self.assertEqual(dialog.parameters['lower_specs'],[8,18])
        self.assertEqual(dialog.parameters['subgroup_sizes'],[2,2])

    def test_by_focus_filters_categorical_and_optional_ignored_when_off(self):
        dialog=self.dialog();dialog.edit_variables.setText('C1');dialog.edit_lower.setText('8')
        QTest.mouseClick(dialog.chk_by,Qt.MouseButton.LeftButton);self.focus(dialog.edit_by)
        self.assertEqual(dialog.col_list.count(),4)
        self.transfer(dialog,2);self.assertEqual(dialog.values()['by_indices'],[2])
        QTest.mouseClick(dialog.chk_by,Qt.MouseButton.LeftButton)
        dialog.edit_by.setText('nonsense')
        self.assertIsNone(dialog.values()['by_indices'])

    def test_by_requires_one_process_and_specs_broadcast_or_pergroup(self):
        dialog=self.dialog();dialog.edit_variables.setText('C1 C2');dialog.chk_by.setChecked(True);dialog.edit_by.setText('C3');dialog.edit_upper.setText('15')
        with self.assertRaisesRegex(ValueError,'one process'):dialog.values()
        dialog.edit_variables.setText('C1');dialog.edit_lower.setText('8 9');dialog.edit_upper.setText('12 13')
        self.assertEqual(dialog.values()['lower_specs'],[8,9])
        dialog.edit_lower.setText('8 9 10')
        with self.assertRaisesRegex(ValueError,'each variable/group'):dialog.values()

    def test_subgroup_id_focus_and_canonical_indices(self):
        dialog=self.dialog();dialog.edit_variables.setText('C1 C2');dialog.edit_upper.setText('30')
        dialog.subgroup_mode.setCurrentIndex(1);self.focus(dialog.edit_subgroup_ids);self.transfer(dialog,3)
        self.assertIn('Subgroup',dialog.edit_subgroup_ids.text())
        self.assertEqual(dialog.values()['subgroup_indices'],[3])
        dialog.subgroup_mode.setCurrentIndex(0);dialog.edit_subgroup_ids.setText('broken');dialog.edit_subgroup_sizes.setText('2')
        self.assertIsNone(dialog.values()['subgroup_indices'])

    def test_missing_one_sided_specs_preserved_and_both_missing_rejected(self):
        dialog=self.dialog();dialog.edit_variables.setText('C1 C2');dialog.edit_lower.setText('8 *');dialog.edit_upper.setText('* 24')
        values=dialog.values();self.assertEqual(values['lower_specs'],[8,None]);self.assertEqual(values['upper_specs'],[None,24])
        dialog.edit_upper.setText('* *');self.ok(dialog)
        self.assertIsNone(dialog.parameters);self.assertIn('at least one',dialog.error.text())

    def test_invalid_finite_specs_subgroups_and_order(self):
        for attr,value in [('edit_lower','nan'),('edit_upper','inf'),('edit_subgroup_sizes','0'),('edit_subgroup_sizes','2.5'),('edit_lower','25')]:
            with self.subTest(attr=attr,value=value):
                dialog=self.dialog();dialog.edit_variables.setText('C1');dialog.edit_upper.setText('20');getattr(dialog,attr).setText(value)
                self.ok(dialog);self.assertIsNone(dialog.parameters);self.assertTrue(dialog.error.text());dialog.close()

    def test_nonnormal_supported_distribution_and_no_subgroup_options(self):
        dialog=self.dialog('nonnormal');dialog.edit_variables.setText('C1 C2');dialog.edit_lower.setText('8 18')
        dialog.distribution.setCurrentIndex(2);dialog.chk_graphs.setChecked(False)
        values=dialog.values()
        self.assertEqual(values['distribution'],'gamma');self.assertIsNone(values['subgroup_indices'])
        self.assertFalse(values['options']['show_graphs']);self.assertFalse(hasattr(dialog,'btn_options'))

    def test_options_validate_and_emit_engine_enums(self):
        dialog=MultipleCapabilityOptionsDialog();self.dialogs.append(dialog);dialog.show();self.app.processEvents()
        self.assertNotIn('tolerance_k',dialog.controls)
        dialog.controls['confidence_level'].setText('nan');self.ok(dialog);self.assertIsNone(dialog.selected_options)
        dialog.controls['confidence_level'].setText('100');self.ok(dialog);self.assertIsNone(dialog.selected_options)
        dialog.controls['confidence_level'].setText('90');dialog.controls['ci_type'].setCurrentIndex(1);self.ok(dialog)
        self.assertEqual(dialog.selected_options['confidence_level'],90)
        self.assertEqual(dialog.selected_options['ci_type'],'lower')
        self.assertEqual(dialog.selected_options['estimate_method_gt1'],'pooled')

    def test_dialog_parameters_execute_real_engine_both_methods_and_by(self):
        from statcraft.multiple_capability_engine import analyze_multiple_capability
        for method in ('normal','nonnormal'):
            with self.subTest(method=method):
                dialog=self.dialog(method);dialog.edit_variables.setText('C1 C2')
                dialog.edit_lower.setText('8 18');dialog.edit_upper.setText('13 23')
                if method=='normal':
                    dialog.edit_subgroup_sizes.setText('2')
                    options=MultipleCapabilityOptionsDialog();self.dialogs.append(options)
                    options.controls['ci_type'].setCurrentIndex(1);options.controls['include_ci'].setChecked(True)
                    options._on_ok();dialog.options=options.selected_options
                result=analyze_multiple_capability(self.sheet,**dialog.values())
                self.assertEqual(len(result['series']),2)
                self.assertEqual([series['variable_index'] for series in result['series']],[0,1])
        dialog=self.dialog();dialog.edit_variables.setText('C1');dialog.chk_by.setChecked(True)
        dialog.edit_by.setText('C3');dialog.edit_lower.setText('8');dialog.edit_upper.setText('13')
        result=analyze_multiple_capability(self.sheet,**dialog.values())
        self.assertEqual(len(result['series']),2)
        self.assertEqual([len(series['rows']) for series in result['series']],[4,4])

    def test_ambiguous_header_does_not_choose_first_column(self):
        dialog=self.dialog();dialog.edit_variables.setText('Diameter');dialog.edit_upper.setText('20')
        self.ok(dialog);self.assertIsNone(dialog.parameters);self.assertIn('ambiguous',dialog.error.text())


if __name__=='__main__':unittest.main()
