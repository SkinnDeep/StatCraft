import copy,unittest
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from statcraft.app import Presenter
from statcraft.mixture_joint_dialog import MixtureJointOptimizerDialog
from statcraft.mixture_joint_chart import MixtureJointChart
from statcraft.mixture_joint_optimizer import optimize
from statcraft.mixture_joint_report import text_report
try:
    from .test_mixture_joint_optimizer import model
except (ImportError, ValueError):
    from test_mixture_joint_optimizer import model


class JointOptimizerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def fitted(self):
        unused,ws=model(True,True);p=Presenter();p.worksheet=ws
        e=p.analyze_mixture_process(5,[0,1],[2],4,[3],model='quadratic',total=100.,options={'process_order':2})
        return p,e
    def test_named_actual_unit_roles_and_known_block(self):
        p,e=self.fitted();d=MixtureJointOptimizerDialog(p.worksheet,[e]);self.assertIn('Binder',d.component_table.item(0,0).text());self.assertIn('Temperature',d.process_table.item(0,0).text());self.assertEqual(float(d.process_table.item(0,1).text()),80.)
        values=d.values();self.assertEqual(values['process_bounds'],[{'low':80.,'high':120.}]);self.assertEqual(values['covariate_values'],[6.]);self.assertIn(values['block_value'],e['result']['block_levels']);d.deleteLater()
    def test_validated_dialog_parameters_optimize_complete_model(self):
        p,e=self.fitted();d=MixtureJointOptimizerDialog(p.worksheet,[e]);d.starts.setValue(5);d.validate();self.assertEqual(d.result(),1,d.error.text());params=copy.deepcopy(d.parameters);params.pop('model_recipe');o=optimize(e['result'],**params);self.assertAlmostEqual(o['components'][0],30.,delta=.1);self.assertAlmostEqual(o['processes'][0],105.,delta=.1);self.assertIn('Held block',text_report(o));d.deleteLater()
    def test_bad_bounds_goal_and_starts_stay_in_dialog(self):
        p,e=self.fitted();d=MixtureJointOptimizerDialog(p.worksheet,[e]);d.component_table.setItem(0,1,QTableWidgetItem('80'));d.component_table.setItem(1,1,QTableWidgetItem('80'));d.validate();self.assertIn('fixed-total',d.error.text());self.assertIsNone(d.parameters)
        d._model_changed();d.goal.setCurrentIndex(2);d.validate();self.assertIn('Target',d.error.text())
        d.goal.setCurrentIndex(0);d.use_start_values.setChecked(True);d.process_table.setItem(0,3,QTableWidgetItem('500'));d.validate();self.assertIn('Starting process',d.error.text());d.deleteLater()
    def test_empty_and_deleted_models_do_not_silently_proceed(self):
        p,e=self.fitted();d=MixtureJointOptimizerDialog(p.worksheet,[]);d.validate();self.assertIsNone(d.parameters);self.assertIn('Analyze',d.error.text());d.deleteLater()
        e['source_unavailable']='Deleted source';d=MixtureJointOptimizerDialog(p.worksheet,[e]);d.validate();self.assertIsNone(d.parameters);d.deleteLater()
    def test_chart_hover_and_frame_capture_preserve_numerical_result(self):
        from statcraft.graph_frame import GraphFrame
        p,e=self.fitted();r=optimize(e['result'],covariate_values=[6.],block_value=e['result']['block_reference'],options={'starts':5,'profile_points':9});entry={'title':r['title'],'result':r};before=copy.deepcopy(entry)
        chart=MixtureJointChart(entry);frame=GraphFrame(chart,entry);frame.resize(1050,700);frame.show();self.app.processEvents();self.assertFalse(frame.capture().isNull());self.assertIsNone(chart.error);chart.grab();self.assertTrue(chart.hover_regions);region,info=chart.hover_regions[0];self.assertIn('Strength',chart.hover_text_at(region.boundingRect().center()));self.assertEqual(entry,before);frame.close();frame.deleteLater()

if __name__=='__main__':unittest.main()
