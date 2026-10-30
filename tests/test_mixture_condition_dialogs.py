"""Actual holding-value controls, coded conversion and source-bound dialogs."""
import copy,math,unittest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QTableWidgetItem,QLineEdit
from statcraft.app import Presenter
from statcraft.model import Column
from statcraft.mixture_condition_dialogs import MixtureProcessContourDialog,MixtureProcessOptimizerDialog
from statcraft.mixture_condition import condition,contour,optimize
from statcraft.verification_fonts import load_verification_fonts
from test_mixture_process_workflows import study
from test_mixture_exploration import compositions


def fitted(process=True,block=True,covariate=True,numeric_block=False,coding=None):
    p=study()
    if numeric_block:
        p.worksheet.columns[4].kind='number';p.worksheet.columns[4].values=[1 if value=='Morning' else 2 for value in p.worksheet.columns[4].values]
    options={'process_coding':coding} if coding else None
    e=p.analyze_mixture_process(6,[0,1,2],[3] if process else [],4 if block else None,[5] if covariate else [],model='linear',total=100.,options=options)
    return p,e


class MixtureConditionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_default_coded_process_has_visible_actual_preview_and_explicit_roles(self):
        p,e=fitted();d=MixtureProcessContourDialog(p.worksheet,[e])
        self.assertTrue(d.coded_process.isChecked());self.assertEqual(d.condition_table.rowCount(),3)
        self.assertIn('C4:',d.condition_table.item(0,0).text());self.assertIn('Temperature',d.condition_table.item(0,0).text())
        self.assertEqual(float(d.condition_table.item(0,1).text()),0.);self.assertEqual(float(d.condition_table.item(0,2).text()),75.)
        values=d.values();self.assertEqual(values['process_values'],[75.]);self.assertEqual(values['covariate_values'],[6.])
        self.assertIn(values['block_value'],e['result']['block_levels']);self.assertFalse(d.condition_table.item(0,2).flags()&Qt.ItemFlag.ItemIsEditable)
        actual=contour(e['result'],**{k:v for k,v in values.items() if k!='model_recipe'})
        self.assertTrue(actual['triangles']);d.deleteLater()

    def test_actual_mouse_units_toggle_converts_without_reinterpreting_condition(self):
        p,e=fitted();d=MixtureProcessContourDialog(p.worksheet,[e]);d.show();self.app.processEvents()
        d.condition_table.item(0,1).setText('1');self.assertEqual(d.values()['process_values'],[100.])
        QTest.mouseClick(d.coded_process,Qt.MouseButton.LeftButton,pos=QPoint(7,d.coded_process.height()//2))
        self.assertFalse(d.coded_process.isChecked());self.assertEqual(float(d.condition_table.item(0,1).text()),100.)
        self.assertEqual(d.values()['process_values'],[100.])
        QTest.mouseClick(d.coded_process,Qt.MouseButton.LeftButton,pos=QPoint(7,d.coded_process.height()//2))
        self.assertEqual(float(d.condition_table.item(0,1).text()),1.);self.assertEqual(d.values()['process_values'],[100.]);d.deleteLater()

    def test_keyboard_coded_entry_commits_actual_value_and_covariate_stays_raw(self):
        p,e=fitted();d=MixtureProcessContourDialog(p.worksheet,[e]);d.show();self.app.processEvents()
        item=d.condition_table.item(0,1);d.condition_table.setCurrentItem(item);d.condition_table.editItem(item);self.app.processEvents()
        editor=d.condition_table.findChild(QLineEdit);self.assertIsNotNone(editor)
        QTest.keyClick(editor,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(editor,'0.4');QTest.keyClick(editor,Qt.Key.Key_Return);self.app.processEvents()
        d.condition_table.item(1,1).setText('7');self.assertEqual(d.values()['process_values'],[85.]);self.assertEqual(d.values()['covariate_values'],[7.])
        d.coded_process.setChecked(False);self.assertEqual(d.values()['covariate_values'],[7.]);d.deleteLater()

    def test_numeric_and_text_block_choices_preserve_raw_types(self):
        for numeric in (False,True):
            p,e=fitted(numeric_block=numeric);d=MixtureProcessOptimizerDialog(p.worksheet,[e]);combo=d.condition_table.cellWidget(2,1)
            combo.setCurrentIndex(0);value=d.values()['block_value']
            self.assertEqual(value,e['result']['block_levels'][0]);self.assertIsInstance(value,(int,float) if numeric else str)
            self.assertEqual(d.condition_table.item(2,2).text(),str(value));d.deleteLater()

    def test_no_model_deleted_source_and_wrong_model_are_inline_errors(self):
        p,e=fitted()
        for entries in ([],[dict(e,source_unavailable='Deleted source')],[dict(e,recipe=dict(e['recipe'],action='analyze_mixture'))]):
            d=MixtureProcessContourDialog(p.worksheet,entries);d.validate();self.assertIsNone(d.parameters);self.assertTrue(d.error.text());d.deleteLater()

    def test_invalid_setting_and_unselected_block_do_not_accept(self):
        p,e=fitted();d=MixtureProcessOptimizerDialog(p.worksheet,[e]);d.condition_table.item(0,1).setText('nan');d.validate()
        self.assertIsNone(d.parameters);self.assertIn('finite',d.error.text());self.assertEqual(d.condition_table.item(0,2).text(),'Invalid value')
        d.condition_table.item(0,1).setText('0');d.condition_table.cellWidget(2,1).setCurrentIndex(-1);d.validate()
        self.assertIsNone(d.parameters);self.assertIn('block',d.error.text());d.deleteLater()

    def test_model_switch_resets_to_new_coding_midpoint_and_named_columns(self):
        p,e=fitted();other=p.analyze_mixture_process(6,[0,1,2],[3],4,[5],model='linear',total=100.,options={'process_coding':[{'low':0.,'high':100.}]})
        d=MixtureProcessContourDialog(p.worksheet,[e,other]);self.assertEqual(d.model.currentIndex(),1);self.assertEqual(d.values()['process_values'],[50.])
        d.condition_table.item(0,1).setText('1');d.model.setCurrentIndex(0)
        self.assertEqual(float(d.condition_table.item(0,1).text()),0.);self.assertEqual(d.values()['process_values'],[75.]);d.deleteLater()

    def test_optional_roles_remain_explicit_none_or_typed_values(self):
        for process,block,cov in ((True,False,False),(False,True,False),(False,False,True)):
            p,e=fitted(process,block,cov);d=MixtureProcessOptimizerDialog(p.worksheet,[e]);v=d.values()
            self.assertEqual(v['process_values'] is None,not process);self.assertEqual(v['covariate_values'] is None,not cov);self.assertEqual(v['block_value'] is None,not block)
            self.assertEqual(d.coded_process.isEnabled(),process);d.deleteLater()

    def test_actual_optimization_uses_fixed_roles_and_search_settings(self):
        p,e=fitted();d=MixtureProcessOptimizerDialog(p.worksheet,[e]);d.starts.setValue(2);d.use_start_values.setChecked(True)
        for i,value in enumerate((20.,30.,50.)):d.bounds_table.item(i,3).setText(str(value))
        d.condition_table.item(0,1).setText('1');d.goal.setCurrentIndex(2);d.target.setText('25');d.validate();self.assertEqual(d.result(),1,d.error.text())
        v=d.parameters;self.assertEqual(v['options']['start_values'],[20.,30.,50.]);self.assertEqual(v['process_values'],[100.])
        result=optimize(e['result'],**{k:value for k,value in v.items() if k!='model_recipe'})
        self.assertAlmostEqual(sum(result['components']),100.);self.assertIn('conditioning',result);d.deleteLater()

    def test_infeasible_bounds_and_duplicate_axes_are_rejected(self):
        p,e=fitted();d=MixtureProcessOptimizerDialog(p.worksheet,[e])
        for i in range(3):d.bounds_table.item(i,1).setText('60')
        d.validate();self.assertIsNone(d.parameters);self.assertIn('feasible',d.error.text());d.deleteLater()
        d=MixtureProcessContourDialog(p.worksheet,[e]);d.axes[1].setCurrentIndex(0);d.validate();self.assertIsNone(d.parameters);self.assertIn('distinct',d.error.text());d.deleteLater()

    def test_extrapolated_process_is_explicit_and_allowed_with_warning(self):
        p,e=fitted();d=MixtureProcessContourDialog(p.worksheet,[e]);d.condition_table.item(0,1).setText('3')
        values=d.values();self.assertEqual(values['process_values'],[150.])
        fitted_slice=condition(e['result'],values['process_values'],values['covariate_values'],values['block_value'])
        self.assertTrue(any('extrapolat' in str(note).lower() or 'observed' in str(note).lower() for note in fitted_slice['conditioning']['warnings']));d.deleteLater()

    def test_current_headers_follow_physical_source_remap(self):
        p,e=fitted();p.move_columns([3],'before_c1');p.rename_column(0,'Temperature renamed')
        d=MixtureProcessContourDialog(p.worksheet,[e]);self.assertIn('C1:',d.condition_table.item(0,0).text());self.assertIn('Temperature renamed',d.condition_table.item(0,0).text())
        self.assertEqual(d.values()['model_recipe']['parameters']['process_indices'],[0]);d.deleteLater()

    def test_four_component_holds_preserve_amount_across_axis_switches(self):
        p=Presenter();rows=[]
        for point in compositions(3,4):
            for t in (50.,75.,100.):
                x=[v/3 for v in point];y=sum((10+10*i)*value for i,value in enumerate(x))+((t-75)/25)*sum((i+1)*value for i,value in enumerate(x))+.03*math.sin(len(rows))
                rows.append([v*100 for v in x]+[t,y])
        p.worksheet.columns=[Column(name,values=[r[i] for r in rows]) for i,name in enumerate(('A','B','C','D','Temperature','Yield'))]
        e=p.analyze_mixture_process(5,[0,1,2,3],[4],model='linear',total=100.)
        d=MixtureProcessContourDialog(p.worksheet,[e]);d.hold_table.item(3,1).setText('20');v=d.values()
        self.assertEqual(v['hold_values'],[{'position':3,'value':20.}]);self.assertEqual(v['process_values'],[75.])
        d.axes[2].setCurrentIndex(3);d.axes[2].setCurrentIndex(2)
        self.assertEqual(d.values()['hold_values'],[{'position':3,'value':20.}]);d.deleteLater()
