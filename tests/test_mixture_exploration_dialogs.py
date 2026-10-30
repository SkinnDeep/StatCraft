"""Actual Qt selection/editing and canonical saved-model mixture dialog contracts."""
import copy,math,unittest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column
from statcraft.mixture_exploration_dialogs import MixtureContourDialog,MixtureOptimizerDialog
from statcraft.verification_fonts import load_verification_fonts
from test_mixture_taguchi_workflows import mixture


def four_components():
    p=Presenter();p.create_doe_plan(kind='simplex_centroid',factors=[dict(name=name,low=0,high=1) for name in ('Binder','Resin','Filler','Solvent')],replicates=2,name='Four-part blend')
    values=[]
    for row in range(p.worksheet.row_count):
        amounts=[p.worksheet.columns[i].values[row] for i in (4,5,6,7)]
        values.append(sum((i+1)*10*amount for i,amount in enumerate(amounts))+.02*math.sin(row))
    p.worksheet.columns.append(Column('Strength',values=values));e=p.analyze_mixture(8,[4,5,6,7],model='linear')
    return p,e


class MixtureExplorationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_contour_selects_named_model_and_canonical_positions(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureContourDialog(p.worksheet,[e])
        self.assertIn('C5',d.axes[0].currentText());self.assertIn('A',d.axes[0].currentText())
        self.assertTrue(all(d.hold_table.item(row,1).text()=='Varies' for row in range(3)))
        d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertEqual(d.parameters['component_positions'],[0,1,2])
        self.assertEqual(d.parameters['hold_values'],[]);self.assertEqual(d.parameters['options']['levels'],8);d.deleteLater()

    def test_duplicate_contour_axes_are_rejected_inline(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureContourDialog(p.worksheet,[e])
        d.axes[2].setCurrentIndex(0);d.validate();self.assertIsNone(d.parameters);self.assertIn('distinct',d.error.text());d.deleteLater()

    def test_held_amount_keyboard_edit_and_axis_change_keep_model_positions(self):
        p,e=four_components();d=MixtureContourDialog(p.worksheet,[e]);d.show();self.app.processEvents()
        item=d.hold_table.item(3,1);d.hold_table.setCurrentItem(item);d.hold_table.editItem(item);QTest.keyClick(d.hold_table.focusWidget(),Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(d.hold_table.focusWidget(),'0.2');QTest.keyClick(d.hold_table.focusWidget(),Qt.Key.Key_Return)
        self.app.processEvents();self.assertEqual(d.hold_table.item(3,1).text(),'0.2')
        self.assertEqual(d.values()['hold_values'],[{'position':3,'value':.2}])
        d.axes[2].setCurrentIndex(3);self.assertTrue(d.hold_table.item(2,1).flags()&Qt.ItemFlag.ItemIsEditable)
        d.hold_table.item(2,1).setText('.1');self.assertEqual(d.values()['hold_values'],[{'position':2,'value':.1}])
        d.axes[2].setCurrentIndex(2);self.assertEqual(d.hold_table.item(3,1).text(),'0.2');d.close();d.deleteLater()

    def test_invalid_held_amount_and_impossible_slice_are_rejected(self):
        p,e=four_components();d=MixtureContourDialog(p.worksheet,[e]);d.hold_table.item(3,1).setText('nan');d.validate()
        self.assertIsNone(d.parameters);self.assertIn('finite',d.error.text())
        d.hold_table.item(3,1).setText('2');d.validate();self.assertIsNone(d.parameters);d.deleteLater()

    def test_optimizer_goals_target_toggle_and_numeric_confidence(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e])
        self.assertFalse(d.target.isEnabled());self.assertEqual(d.values()['goal'],'maximize')
        d.goal.setCurrentIndex(1);self.assertEqual(d.values()['goal'],'minimize')
        d.goal.setCurrentIndex(2);self.assertTrue(d.target.isEnabled());d.target.setText('22.5');d.confidence.setText('90')
        d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertEqual(d.parameters['target'],22.5)
        self.assertEqual(d.parameters['options']['confidence'],.9);d.deleteLater()

    def test_optimizer_fixed_component_bound_and_tightened_region(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e])
        self.assertIn('C5',d.bounds_table.item(0,0).text());self.assertIn('A',d.bounds_table.item(0,0).text())
        d.bounds_table.item(0,1).setText('.2');d.bounds_table.item(0,2).setText('.2')
        d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertEqual(d.parameters['bounds'][0],{'low':.2,'high':.2});d.deleteLater()

    def test_optimizer_bounds_cannot_expand_fitted_region_or_break_total(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e])
        d.bounds_table.item(0,1).setText('0');d.validate();self.assertIsNone(d.parameters);self.assertIn('fitted lower',d.error.text())
        for row in range(3):d.bounds_table.item(row,1).setText('.5')
        d.validate();self.assertIsNone(d.parameters);self.assertIn('feasible',d.error.text());d.deleteLater()

    def test_nonfinite_target_confidence_and_bound_errors_are_inline(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e]);d.goal.setCurrentIndex(2)
        d.target.setText('nan');d.validate();self.assertIsNone(d.parameters);self.assertIn('finite',d.error.text())
        d.target.setText('20');d.confidence.setText('100');d.validate();self.assertIsNone(d.parameters);self.assertIn('between',d.error.text())
        d.confidence.setText('95');d.bounds_table.item(0,2).setText('inf');d.validate();self.assertIsNone(d.parameters);self.assertIn('finite',d.error.text());d.deleteLater()

    def test_latest_model_is_selected_and_model_switch_refreshes_bounds(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');other=copy.deepcopy(e);other['title']='Later model'
        other['result']['component_bounds'][0]['low']=.15
        d=MixtureOptimizerDialog(p.worksheet,[e,other]);self.assertEqual(d.model.currentIndex(),1)
        self.assertEqual(d.bounds_table.item(0,1).text(),'0.15');d.model.setCurrentIndex(0)
        self.assertEqual(float(d.bounds_table.item(0,1).text()),.1);d.deleteLater()

    def test_no_model_and_deleted_source_model_have_clear_messages(self):
        p=mixture()
        for kind in (MixtureContourDialog,MixtureOptimizerDialog):
            d=kind(p.worksheet,[]);d.validate();self.assertIsNone(d.parameters);self.assertIn('Analyze a mixture',d.error.text());d.deleteLater()
        e=p.analyze_mixture(7,[4,5,6],model='linear');e['source_unavailable']='deleted'
        d=MixtureOptimizerDialog(p.worksheet,[e]);d.validate();self.assertIsNone(d.parameters);self.assertIn('deleted',d.error.text());d.deleteLater()

    def test_two_components_cannot_make_ternary_axes(self):
        p,e=four_components();e=copy.deepcopy(e);e['recipe']['parameters']['component_indices']=e['recipe']['parameters']['component_indices'][:2];e['result']['component_bounds']=e['result']['component_bounds'][:2]
        d=MixtureContourDialog(p.worksheet,[e]);d.validate();self.assertIsNone(d.parameters);self.assertIn('three',d.error.text());d.deleteLater()

    def test_optimizer_start_controls_enable_cells_and_return_actual_model_order(self):
        from statcraft.mixture_exploration import optimize
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e])
        self.assertEqual(d.starts.value(),16);self.assertEqual(d.max_iterations.value(),300)
        self.assertFalse(d.use_start_values.isChecked());self.assertFalse(d.bounds_table.item(0,3).flags()&Qt.ItemFlag.ItemIsEnabled)
        self.assertIsNone(d.values()['options']['start_values'])
        d.show();self.app.processEvents();QTest.mouseClick(d.use_start_values,Qt.MouseButton.LeftButton,pos=QPoint(8,d.use_start_values.height()//2))
        self.assertTrue(d.bounds_table.item(0,3).flags()&Qt.ItemFlag.ItemIsEditable)
        for row,value in enumerate((.2,.3,.5)):d.bounds_table.item(row,3).setText(str(value))
        d.starts.setValue(7);d.max_iterations.setValue(88);params=d.values()
        self.assertEqual(params['options']['start_values'],[.2,.3,.5]);self.assertEqual(params['options']['starts'],7)
        self.assertEqual(params['options']['max_iterations'],88)
        result=optimize(e['result'],params['goal'],params['target'],params['bounds'],params['options'])
        self.assertEqual(result['options']['start_values'],[.2,.3,.5]);d.close();d.deleteLater()

    def test_optimizer_start_values_reject_wrong_total_or_tightened_bounds(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e])
        d.use_start_values.setChecked(True)
        for row in range(3):d.bounds_table.item(row,3).setText('.2')
        d.validate();self.assertIsNone(d.parameters);self.assertIn('fixed total',d.error.text())
        for row,value in enumerate((.2,.3,.5)):d.bounds_table.item(row,3).setText(str(value))
        d.bounds_table.item(0,1).setText('.25');d.validate();self.assertIsNone(d.parameters);self.assertIn('optimizer bounds',d.error.text())
        d.use_start_values.setChecked(False);d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertIsNone(d.parameters['options']['start_values']);d.deleteLater()

    def test_search_budgets_are_bounded_and_blank_active_starts_get_inline_error(self):
        p=mixture();e=p.analyze_mixture(7,[4,5,6],model='linear');d=MixtureOptimizerDialog(p.worksheet,[e])
        self.assertEqual((d.starts.minimum(),d.starts.maximum()),(1,64));self.assertEqual((d.max_iterations.minimum(),d.max_iterations.maximum()),(10,2000))
        d.use_start_values.setChecked(True);d.validate();self.assertIsNone(d.parameters);self.assertIn('Starting amount',d.error.text())
        d.use_start_values.setChecked(False);self.assertFalse(d.bounds_table.item(0,3).flags()&Qt.ItemFlag.ItemIsEditable);d.deleteLater()

