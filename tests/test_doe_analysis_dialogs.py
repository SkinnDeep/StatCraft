"""Physical column identity, real focus transfer and authored DOE metadata forms."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QDialog
from statcraft.doe_planner import build_plan
from statcraft.doe_analysis_dialogs import BuildAnalyzeMixtureDialog,BuildAnalyzeTaguchiDialog
from statcraft.model import Column


def mixture_sheet():
    sheet=build_plan('simplex_centroid',[{'name':name,'low':0,'high':2} for name in 'ABC'],centers=1,randomize=False,options={'total':2})
    a,b,c=[col.values for col in sheet.columns[4:7]]
    y=[10+x+2*z+3*w+2*x*z+.01*(i%3) for i,(x,z,w) in enumerate(zip(a,b,c))]
    sheet.columns.extend([Column('Strength',values=y),Column('Strength',values=[value+.2 for value in y])])
    return sheet


def taguchi_sheet():
    sheet=build_plan('taguchi',[{'name':name,'kind':'text','levels':['Low','High']} for name in 'ABC'],replicates=2,randomize=False)
    first=sheet.columns[4].values
    sheet.columns.extend([Column('Noise 1',values=[10+(2 if value=='High' else 0)+.1*i for i,value in enumerate(first)]),Column('Noise 2',values=[11+(2 if value=='High' else 0)+.2*i for i,value in enumerate(first)])])
    return sheet


class DoeAnalysisDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def setUp(self):self.dialogs=[]

    def tearDown(self):
        for dialog in self.dialogs:dialog.close()
        self.app.processEvents()

    def show(self,cls,sheet):
        dialog=cls(sheet);self.dialogs.append(dialog);dialog.show();dialog.activateWindow();self.app.processEvents();return dialog

    def select(self,dialog,key,index,double=False):
        field=dialog.controls[key];QTest.mouseClick(field,Qt.MouseButton.LeftButton);self.app.processEvents()
        item=next(dialog.available.item(i) for i in range(dialog.available.count()) if dialog.available.item(i).data(Qt.ItemDataRole.UserRole)==index)
        pos=dialog.available.visualItemRect(item).center();QTest.mouseClick(dialog.available.viewport(),Qt.MouseButton.LeftButton,pos=pos)
        if double:QTest.mouseDClick(dialog.available.viewport(),Qt.MouseButton.LeftButton,pos=pos)
        else:QTest.mouseClick(dialog.select_button,Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def ok(self,dialog):
        button=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        QTest.mouseClick(button,Qt.MouseButton.LeftButton);self.app.processEvents()

    def test_mixture_metadata_autofills_verified_slots_total_and_bounds(self):
        dialog=self.show(BuildAnalyzeMixtureDialog,mixture_sheet())
        self.assertIn('C5: "A"',dialog.controls['component_indices'].text())
        self.assertEqual(dialog.controls['total'].text(),'2')
        self.select(dialog,'response_index',8);self.ok(dialog)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.parameters['response_index'],8)
        self.assertEqual(dialog.parameters['component_indices'],[4,5,6])
        self.assertEqual(dialog.parameters['options']['bounds'],[{'low':0,'high':2}]*3)
        self.assertEqual(dialog.parameters['options']['confidence'],.95)

    def test_duplicate_response_header_resolves_explicit_slot(self):
        dialog=self.show(BuildAnalyzeMixtureDialog,mixture_sheet())
        dialog.controls['response_index'].setText('Strength');self.ok(dialog)
        self.assertIsNone(dialog.parameters);self.assertIn('ambiguous',dialog.error.text())
        self.select(dialog,'response_index',8,double=True);self.ok(dialog)
        self.assertEqual(dialog.parameters['response_index'],8)

    def test_mixture_overlap_nonpositive_total_and_bad_confidence_inline(self):
        dialog=self.show(BuildAnalyzeMixtureDialog,mixture_sheet());dialog.controls['response_index'].setText('C5');self.ok(dialog)
        self.assertIsNone(dialog.parameters);self.assertIn('separate',dialog.error.text())
        dialog.controls['response_index'].setText('C8')
        for key,value in [('total','0'),('total','nan'),('confidence','100'),('confidence','inf')]:
            with self.subTest(key=key,value=value):
                dialog.controls['total'].setText('2');dialog.controls['confidence'].setText('95');dialog.controls[key].setText(value)
                self.ok(dialog);self.assertIsNone(dialog.parameters);self.assertTrue(dialog.error.text())

    def test_stale_metadata_never_selects_name_match_from_another_slot(self):
        sheet=mixture_sheet();sheet.columns[4],sheet.columns[5]=sheet.columns[5],sheet.columns[4]
        dialog=self.show(BuildAnalyzeMixtureDialog,sheet)
        self.assertEqual(dialog.controls['component_indices'].text(),'')
        self.assertEqual(dialog.controls['total'].text(),'1')
        dialog.controls['component_indices'].setText('C5 C6 C7');dialog.controls['response_index'].setText('C8');dialog.controls['total'].setText('2')
        self.assertIsNone(dialog.values()['options']['bounds'])

    def test_mixture_options_use_canonical_models_and_functional_graph_toggle(self):
        dialog=self.show(BuildAnalyzeMixtureDialog,mixture_sheet());dialog.controls['response_index'].setText('C8')
        dialog.controls['model'].setCurrentIndex(2);dialog.controls['show_graphs'].setChecked(False);dialog.controls['title'].setText('Blend strength')
        values=dialog.values();self.assertEqual(values['model'],'special_cubic');self.assertFalse(values['options']['show_graphs'])
        self.assertEqual(values['options']['title'],'Blend strength')

    def test_taguchi_metadata_and_mouse_transfers_repeated_response_columns(self):
        dialog=self.show(BuildAnalyzeTaguchiDialog,taguchi_sheet())
        self.assertIn('C5-T: "A"',dialog.controls['factor_indices'].text())
        self.select(dialog,'response_indices',7);self.select(dialog,'response_indices',8,double=True)
        self.ok(dialog)
        self.assertEqual(dialog.parameters['response_indices'],[7,8]);self.assertEqual(dialog.parameters['factor_indices'],[4,5,6])
        self.assertEqual(dialog.parameters['options']['sn_type'],'larger')
        self.assertTrue(dialog.parameters['options']['fit_models'])

    def test_taguchi_numeric_response_filter_and_source_overlap(self):
        sheet=taguchi_sheet();dialog=self.show(BuildAnalyzeTaguchiDialog,sheet)
        self.assertFalse(any('-T:' in dialog.available.item(i).text() for i in range(dialog.available.count())))
        dialog.controls['response_indices'].setText('C5');self.ok(dialog)
        self.assertIsNone(dialog.parameters);self.assertIn('eligible',dialog.error.text())
        dialog.controls['response_indices'].setText('C8');dialog.controls['factor_indices'].setText('C8');self.ok(dialog)
        self.assertIsNone(dialog.parameters);self.assertIn('separate',dialog.error.text())

    def test_taguchi_options_classic_nominal_log_stdev_and_no_graphs(self):
        dialog=self.show(BuildAnalyzeTaguchiDialog,taguchi_sheet());dialog.controls['response_indices'].setText('C8 C9')
        dialog.controls['sn_type'].setCurrentIndex(2);dialog.controls['log_stdev'].setChecked(True);dialog.controls['show_graphs'].setChecked(False);dialog.controls['fit_models'].setChecked(False)
        self.assertEqual(dialog.values()['options'],{'sn_type':'nominal','log_stdev':True,'fit_models':False,'show_graphs':False})

    def test_form_parameters_execute_real_mixture_and_taguchi_engines(self):
        from statcraft.mixture_analysis import fit
        from statcraft.taguchi_analysis import analyze
        sheet=mixture_sheet();dialog=self.show(BuildAnalyzeMixtureDialog,sheet)
        dialog.controls['response_index'].setText('C8')
        result=fit(sheet,**dialog.values())
        self.assertEqual(result['analysis'],'mixture_model')
        self.assertEqual(result['component_indices'],[4,5,6])
        sheet=taguchi_sheet();dialog=self.show(BuildAnalyzeTaguchiDialog,sheet)
        dialog.controls['response_indices'].setText('C8 C9')
        for sn_type in range(3):
            with self.subTest(sn_type=sn_type):
                dialog.controls['sn_type'].setCurrentIndex(sn_type)
                result=analyze(sheet,**dialog.values())
                self.assertEqual(result['analysis'],'taguchi_analysis')
                self.assertEqual(result['options']['sn_type'],['larger','smaller','nominal'][sn_type])

    def test_taguchi_stale_metadata_is_not_autofilled(self):
        sheet=taguchi_sheet();sheet.columns[4].name='Renamed control'
        dialog=self.show(BuildAnalyzeTaguchiDialog,sheet)
        self.assertEqual(dialog.controls['factor_indices'].text(),'')


if __name__=='__main__':unittest.main()
