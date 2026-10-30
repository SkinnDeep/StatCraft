"""Dynamic Taguchi role selection, signal pairing and actual keyboard/mouse paths."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox
from statcraft.dynamic_taguchi_dialog import BuildAnalyzeDynamicTaguchiDialog
from statcraft.model import Column,Worksheet
from statcraft.doe_planner import build_plan


def sheet():
    factors=[Column('Temperature','text',['Low','Low','High','High']),Column('Speed','number',[1,2,1,2])]
    responses=[Column('Response',values=[1,2,3,4]),Column('Response',values=[2.2,3.1,4.4,5.2]),Column('Signal 2 noise 2',values=[2.4,3.3,4.6,5.4]),Column('Signal 3',values=[3.5,4.5,5.5,6.7])]
    return Worksheet('Dynamic study',factors+responses)


class DynamicTaguchiDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def setUp(self):self.dialogs=[]

    def tearDown(self):
        for dialog in self.dialogs:dialog.close();dialog.deleteLater()
        self.app.processEvents()

    def show(self,worksheet=None):
        d=BuildAnalyzeDynamicTaguchiDialog(worksheet or sheet());self.dialogs.append(d);d.show();d.activateWindow();self.app.processEvents();return d

    def configure(self,d):
        d.controls['response_indices'].setText('C3 C4 C5 C6');d.controls['factor_indices'].setText('C1 C2');d.set_signal_values([1,2,2,3]);return d

    def ok(self,d):
        QTest.mouseClick(d.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton);self.app.processEvents()

    def transfer(self,d,key,index):
        QTest.mouseClick(d.controls[key],Qt.MouseButton.LeftButton);self.app.processEvents()
        item=next(d.available.item(row) for row in range(d.available.count()) if d.available.item(row).data(Qt.ItemDataRole.UserRole)==index)
        QTest.mouseClick(d.available.viewport(),Qt.MouseButton.LeftButton,pos=d.available.visualItemRect(item).center())
        QTest.mouseClick(d.select_button,Qt.MouseButton.LeftButton);self.app.processEvents()

    def test_mouse_transfers_show_duplicate_headers_with_unambiguous_addresses(self):
        d=self.show();self.transfer(d,'response_indices',2);self.transfer(d,'response_indices',3);self.transfer(d,'response_indices',4)
        self.assertIn('C3: "Response"',d.controls['response_indices'].text())
        self.assertIn('C4: "Response"',d.controls['response_indices'].text())
        self.assertEqual(d.signal_table.rowCount(),3)
        self.assertIn('C3:',d.signal_table.item(0,0).text());self.assertIn('C4:',d.signal_table.item(1,0).text())
        self.assertFalse(d.signal_table.item(0,0).flags()&Qt.ItemFlag.ItemIsEditable)
        self.transfer(d,'factor_indices',0);self.transfer(d,'factor_indices',1)
        d.set_signal_values([1,2,3]);self.ok(d)
        self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(d.parameters['response_indices'],[2,3,4]);self.assertEqual(d.parameters['factor_indices'],[0,1])

    def test_signal_pairing_survives_selected_response_reorder_and_removal(self):
        d=self.configure(self.show());d.controls['response_indices'].setText('C6 C3 C4')
        self.assertEqual(d.values()['signal_values'],[3,1,2])
        d.controls['response_indices'].setText('C5 C6 C3 C4')
        self.assertEqual(d.values()['signal_values'],[2,3,1,2])

    def test_keyboard_edits_actual_signal_cell_and_enter_accepts(self):
        d=self.configure(self.show());d.signal_table.setCurrentCell(0,1)
        QTest.mouseDClick(d.signal_table.viewport(),Qt.MouseButton.LeftButton,pos=d.signal_table.visualItemRect(d.signal_table.item(0,1)).center())
        QTest.keyClick(d.signal_table,Qt.Key.Key_F2)
        fw = d.signal_table.focusWidget()
        if hasattr(fw, 'selectAll'):
            fw.selectAll()
        else:
            mod = Qt.KeyboardModifier.MetaModifier if sys.platform == 'darwin' else Qt.KeyboardModifier.ControlModifier
            QTest.keyClick(fw, Qt.Key.Key_A, mod)
        QTest.keyClicks(fw,'1.25');QTest.keyClick(fw,Qt.Key.Key_Return);self.app.processEvents()
        self.assertEqual(d.values()['signal_values'][0],1.25)

    def test_invalid_signal_values_are_inline_and_parameters_cleared(self):
        d=self.configure(self.show())
        for values,fragment in [(['',2,2,3],'numeric'),([1,1,1,1],'distinct'),([1,'nan',2,3],'finite'),([1,'inf',2,3],'finite')]:
            with self.subTest(values=values):
                d.set_signal_values(values);self.ok(d);self.assertIsNone(d.parameters);self.assertIn(fragment,d.error.text())

    def test_missing_count_and_source_overlap_are_inline(self):
        d=self.configure(self.show());d.controls['response_indices'].setText('C3 C4');d.set_signal_values([1,2]);self.ok(d)
        self.assertIsNone(d.parameters);self.assertIn('three',d.error.text())
        d.controls['reference_method'].setCurrentIndex(1);d.controls['factor_indices'].setText('C4');self.ok(d)
        self.assertIn('separate',d.error.text())
        with self.assertRaisesRegex(ValueError,'one signal'):d.set_signal_values([1])

    def test_fixed_reference_fields_and_options_are_functional(self):
        d=self.configure(self.show());self.assertFalse(d.controls['reference_signal'].isEnabled())
        d.controls['reference_method'].setCurrentIndex(1);self.assertTrue(d.controls['reference_signal'].isEnabled())
        d.controls['reference_signal'].setText('1.5');d.controls['reference_response'].setText('-2')
        d.controls['adjusted'].setChecked(True);d.controls['log_stdev'].setChecked(True);d.controls['show_graphs'].setChecked(False);d.controls['show_signal_plots'].setChecked(True);d.controls['fit_models'].setChecked(False);d.controls['confidence'].setText('90')
        values=d.values();self.assertEqual(values['options'],{'reference_method':'fixed','reference_signal':1.5,'reference_response':-2.,'adjusted':True,'log_stdev':True,'confidence':.9,'fit_models':False,'show_graphs':False,'show_signal_plots':True})
        d.controls['response_indices'].setText('C3 C4');d.set_signal_values([1,2]);self.assertEqual(len(d.values()['response_indices']),2)

    def test_free_intercept_ignores_disabled_reference_text_without_erasing_it(self):
        d=self.configure(self.show());d.controls['reference_signal'].setText('nonsense');d.controls['reference_response'].setText('nan')
        values=d.values();self.assertEqual(values['options']['reference_signal'],0.)
        self.assertEqual(d.controls['reference_signal'].text(),'nonsense')
        d.controls['reference_method'].setCurrentIndex(1);self.ok(d);self.assertIsNone(d.parameters)

    def test_bad_confidence_does_not_accept_and_clears_previous_parameters(self):
        d=self.configure(self.show());d.parameters={'old':True}
        for value in ['0','100','nan']:
            d.controls['confidence'].setText(value);self.ok(d);self.assertIsNone(d.parameters);self.assertTrue(d.error.text())

    def test_verified_authored_control_factors_autofill_but_stale_metadata_does_not(self):
        ws=build_plan('taguchi',[{'name':name,'kind':'text','levels':['Low','High']} for name in 'ABC'],randomize=False)
        d=self.show(ws);self.assertIn('C5-T: "A"',d.controls['factor_indices'].text())
        ws.columns[4],ws.columns[5]=ws.columns[5],ws.columns[4];other=self.show(ws)
        self.assertEqual(other.controls['factor_indices'].text(),'')

    def test_ambiguous_header_text_fails_then_address_succeeds(self):
        d=self.configure(self.show());d.controls['response_indices'].setText('Response');self.ok(d)
        self.assertIn('ambiguous',d.error.text());self.assertIsNone(d.parameters)
        d.controls['response_indices'].setText('C3 C4 C5 C6');self.assertEqual(d.values()['signal_values'],[1,2,2,3])

    def test_form_values_execute_actual_engine(self):
        from statcraft.dynamic_taguchi_analysis import analyze
        d=self.configure(self.show())
        for fixed in (False,True):
            d.controls['reference_method'].setCurrentIndex(int(fixed));d.controls['adjusted'].setChecked(True)
            result=analyze(d.worksheet,**d.values());self.assertEqual(result['analysis'],'dynamic_taguchi_analysis');self.assertEqual(result['n_runs'],4)
            self.assertEqual(result['options']['reference_method'],'fixed' if fixed else 'none')


if __name__=='__main__':unittest.main()
