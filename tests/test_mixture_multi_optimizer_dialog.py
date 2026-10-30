"""Live multiresponse mixture goals, shared bounds, keyboard and recipe contracts."""
import copy,math,unittest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column
from statcraft.mixture_multi_optimizer_dialog import MixtureMultiOptimizerDialog
from statcraft.verification_fonts import load_verification_fonts


def study():
    p=Presenter();p.create_doe_plan(kind='simplex_centroid',factors=[dict(name=n,low=.1,high=.8) for n in ('Binder','Resin','Additive')],replicates=3,name='Shared mixture responses')
    first=[];second=[]
    for row in range(p.worksheet.row_count):
        a,b,c=[p.worksheet.columns[i].values[row] for i in (4,5,6)]
        first.append(10*a+20*b+30*c+.01*math.sin(row));second.append(30*a+20*b+10*c+.015*math.cos(row))
    p.worksheet.columns.extend([Column('Strength',values=first),Column('Cost',values=second)])
    a=p.analyze_mixture(7,[4,5,6],model='linear');b=p.analyze_mixture(8,[4,5,6],model='quadratic')
    return p,[a,b]


class MixtureMultiOptimizerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_named_default_models_and_canonical_response_recipes(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries)
        self.assertIn('Strength',d.response_table.cellWidget(0,0).currentText());self.assertIn('Cost',d.response_table.cellWidget(1,0).currentText())
        self.assertIn('C5',d.bounds_table.item(0,0).text());self.assertIn('Binder',d.bounds_table.item(0,0).text())
        params=d.values();self.assertEqual(len(params['responses']),2)
        self.assertEqual(params['responses'][0]['model_recipe'],entries[0]['recipe'])
        self.assertEqual(params['responses'][0]['goal'],'maximize');self.assertIsNone(params['responses'][0]['upper'])
        self.assertEqual(params['options']['confidence'],.95);self.assertEqual(params['options']['starts'],16);d.deleteLater()

    def test_latest_distinct_physical_response_fit_is_preselected(self):
        p,entries=study();new=p.analyze_mixture(7,[4,5,6],model='quadratic');d=MixtureMultiOptimizerDialog(p.worksheet,entries+[new])
        indexes=[d.response_table.cellWidget(r,0).currentIndex() for r in range(2)]
        self.assertEqual(set(indexes),{1,2});self.assertNotEqual(d.values()['responses'][0]['model_recipe']['parameters']['response_index'],d.values()['responses'][1]['model_recipe']['parameters']['response_index']);d.deleteLater()

    def test_goal_cells_enable_only_relevant_bounds_and_normalize_unused(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries);goal=d.response_table.cellWidget(0,1)
        self.assertFalse(d.response_table.item(0,4).flags()&Qt.ItemFlag.ItemIsEditable)
        goal.setCurrentIndex(1);self.assertFalse(d.response_table.item(0,2).flags()&Qt.ItemFlag.ItemIsEditable)
        spec=d.values()['responses'][0];self.assertIsNone(spec['lower']);self.assertLess(spec['target'],spec['upper'])
        goal.setCurrentIndex(2);spec=d.values()['responses'][0];self.assertLess(spec['lower'],spec['target']);self.assertLess(spec['target'],spec['upper']);d.deleteLater()

    def test_duplicate_physical_response_rejected_even_different_fit(self):
        p,entries=study();new=p.analyze_mixture(7,[4,5,6],model='quadratic');d=MixtureMultiOptimizerDialog(p.worksheet,entries+[new])
        d.response_table.cellWidget(0,0).setCurrentIndex(0);d.response_table.cellWidget(1,0).setCurrentIndex(2);d.validate()
        self.assertIsNone(d.parameters);self.assertIn('different physical response',d.error.text());d.deleteLater()

    def test_incompatible_component_order_and_total_rejected(self):
        p,entries=study();reverse=p.analyze_mixture(8,[6,5,4],model='linear');d=MixtureMultiOptimizerDialog(p.worksheet,[entries[0],reverse]);d.validate()
        self.assertIsNone(d.parameters);self.assertIn('same order',d.error.text());d.deleteLater()
        wrong=copy.deepcopy(entries[1]);wrong['recipe']['parameters']['total']=100
        d=MixtureMultiOptimizerDialog(p.worksheet,[entries[0],wrong]);d.validate();self.assertIsNone(d.parameters);self.assertIn('same total',d.error.text());d.deleteLater()

    def test_deleted_source_and_empty_model_lists_have_inline_errors(self):
        p,entries=study();dead=copy.deepcopy(entries[0]);dead['source_unavailable']='deleted'
        for selected,message in (([dead,entries[1]],'deleted'),([],'at least two')):
            d=MixtureMultiOptimizerDialog(p.worksheet,selected);d.validate();self.assertIsNone(d.parameters);self.assertIn(message,d.error.text());d.deleteLater()

    def test_invalid_goal_weight_importance_and_confidence_are_inline(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries)
        d.response_table.item(0,5).setText('0');d.validate();self.assertIn('Weight',d.error.text());self.assertIsNone(d.parameters)
        d.response_table.item(0,5).setText('1');d.response_table.item(0,6).setText('11');d.validate();self.assertIn('importance',d.error.text())
        d.response_table.item(0,6).setText('1');d.response_table.item(0,3).setText('-100');d.validate();self.assertIn('lower < target',d.error.text())
        d.response_table.cellWidget(0,1).setCurrentIndex(2);d.confidence.setText('100');d.validate();self.assertIn('Confidence',d.error.text());d.deleteLater()

    def test_shared_intersection_bounds_and_fixed_component_values(self):
        p,entries=study();wide=p.analyze_mixture(8,[4,5,6],model='linear',options={'bounds':[{'low':.05,'high':.9}]*3})
        d=MixtureMultiOptimizerDialog(p.worksheet,[entries[0],wide]);self.assertEqual(d.values()['bounds'],[{'low':.1,'high':.8}]*3)
        d.bounds_table.item(0,1).setText('.2');d.bounds_table.item(0,2).setText('.2');self.assertEqual(d.values()['bounds'][0],{'low':.2,'high':.2})
        d.bounds_table.item(1,2).setText('.9');d.validate();self.assertIn('shared fitted',d.error.text());d.deleteLater()

    def test_invalid_total_and_disjoint_shared_regions_rejected(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries)
        for row in range(3):d.bounds_table.item(row,1).setText('.4')
        d.validate();self.assertIsNone(d.parameters);self.assertIn('fixed mixture total',d.error.text());d.deleteLater()
        a=copy.deepcopy(entries[0]);b=copy.deepcopy(entries[1]);a['result']['component_bounds'][0]={'low':.7,'high':.8};b['result']['component_bounds'][0]={'low':.1,'high':.2}
        d=MixtureMultiOptimizerDialog(p.worksheet,[a,b]);d.validate();self.assertIn('do not intersect',d.error.text());d.deleteLater()

    def test_start_checkbox_mouse_toggle_and_values_validate_total_and_bounds(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries);d.show();self.app.processEvents()
        self.assertFalse(d.bounds_table.item(0,3).flags()&Qt.ItemFlag.ItemIsEditable)
        QTest.mouseClick(d.use_start_values,Qt.MouseButton.LeftButton,pos=QPoint(6,d.use_start_values.height()//2));self.app.processEvents()
        self.assertTrue(d.use_start_values.isChecked());self.assertTrue(d.bounds_table.item(0,3).flags()&Qt.ItemFlag.ItemIsEditable)
        for row,value in enumerate((.2,.3,.5)):d.bounds_table.item(row,3).setText(str(value))
        self.assertEqual(d.values()['options']['start_values'],[.2,.3,.5]);d.bounds_table.item(0,3).setText('.8');d.validate();self.assertIn('fixed total',d.error.text());d.close();d.deleteLater()

    def test_numeric_goal_cell_keyboard_edit_is_used_and_limits_bounded(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries);d.show();self.app.processEvents()
        item=d.response_table.item(0,6);d.response_table.setCurrentItem(item);d.response_table.editItem(item);self.app.processEvents()
        QTest.keyClick(d.response_table.focusWidget(),Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier);QTest.keyClicks(d.response_table.focusWidget(),'2.5');QTest.keyClick(d.response_table.focusWidget(),Qt.Key.Key_Tab);self.app.processEvents()
        self.assertEqual(d.values()['responses'][0]['importance'],2.5)
        self.assertEqual((d.starts.minimum(),d.starts.maximum()),(1,64));self.assertEqual((d.max_iterations.minimum(),d.max_iterations.maximum()),(10,2000));d.close();d.deleteLater()

    def test_response_add_remove_is_bounded_and_uses_selected_row(self):
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries)
        self.assertFalse(d.remove_button.isEnabled())
        for unused in range(7):d.add_response()
        self.assertEqual(d.response_table.rowCount(),8);self.assertFalse(d.add_button.isEnabled())
        d.response_table.setCurrentCell(3,2);d.remove_response();self.assertEqual(d.response_table.rowCount(),7);self.assertTrue(d.add_button.isEnabled())
        for unused in range(6):d.remove_response()
        self.assertEqual(d.response_table.rowCount(),2);self.assertFalse(d.remove_button.isEnabled());d.deleteLater()

    def test_dialog_parameters_execute_actual_multi_optimizer(self):
        from statcraft.mixture_multi_optimizer import optimize
        p,entries=study();d=MixtureMultiOptimizerDialog(p.worksheet,entries);params=d.values()
        specs=[{k:v for k,v in item.items() if k!='model_recipe'} for item in params['responses']]
        models=[entries[d.response_table.cellWidget(row,0).currentIndex()]['result'] for row in range(2)]
        result=optimize(models,specs,params['bounds'],params['options'])
        self.assertEqual(result['analysis'],'mixture_multi_optimization');self.assertAlmostEqual(sum(result['components']),1.);d.deleteLater()
