import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QTimer,QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox
from statcraft.categorical_points_dialogs import CategoricalTypeDialog,CategoricalPlotDialog,IntervalOptionsDialog
from statcraft.similar_graph_dialog import create_similar_dialog,run_similar_graphs
from test_categorical_points import document


class CategoricalDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_two_families_four_gallery_choices(self):
        for family in ('individual','interval'):
            d=CategoricalTypeDialog(family);self.assertEqual(len(d.mode_buttons),4)
            for mode,b in d.mode_buttons.items():b.click();self.assertEqual(d.mode,mode)

    def test_named_multiple_group_roles_and_order(self):
        d=CategoricalPlotDialog(None,document().worksheet,'individual','multiple_groups');d.variables.setText('C1 C2');d.activate('group')
        for i in range(d.available.count()):
            item=d.available.item(i)
            if item.data(Qt.ItemDataRole.UserRole) in (2,3):item.setSelected(True)
        d.transfer();d.scale_order.setCurrentIndex(1);self.assertTrue(d.validate());self.assertEqual(d.settings()['group_indices'],[2,3])

    def test_data_view_display_jitter_and_attribute_assignment(self):
        d=CategoricalPlotDialog(None,document().worksheet,'individual','one_groups');d.variables.setText('C1');d.group.setText('C3 C4')
        def configure():
            child=self.app.activeModalWidget();child.controls['mean_symbol'].setChecked(True);child.controls['median_connect'].setChecked(True);child.jitter.setValue(.2);child.colors[0].setChecked(False);child.accept()
        QTimer.singleShot(0,configure);d.edit_data_view();self.assertTrue(d.display['mean_symbol']);self.assertEqual(d.color_levels,[1]);self.assertEqual(d.jitter,.2)

    def test_interval_options_commit_and_data_view_cancel_restores_child_edits(self):
        d=CategoricalPlotDialog(None,document().worksheet,'interval')
        def options():
            child=self.app.activeModalWidget();child.pooled.setChecked(True);child.bonferroni.setChecked(True);child.confidence.setValue(90);child.validate()
        QTimer.singleShot(0,options);d.edit_interval();self.assertEqual(d.interval_options['confidence'],.9);self.assertTrue(d.interval_options['pooled'])
        original=dict(d.interval_options)
        def cancel():
            child=self.app.activeModalWidget();d.interval_options['confidence']=.8;child.reject()
        QTimer.singleShot(0,cancel);d.edit_data_view();self.assertEqual(d.interval_options,original)

    def test_standard_error_disables_unsupported_side_and_bonferroni(self):
        d=IntervalOptionsDialog({'side':'upper','bonferroni':True});d.method.setCurrentIndex(1);self.assertFalse(d.side.isEnabled());self.assertFalse(d.bonferroni.isChecked());self.assertTrue(d.validate());self.assertEqual(d.options['side'],'two-sided')

    def test_inline_failure_and_similar_preserves_options(self):
        p=document();d=CategoricalPlotDialog(None,p.worksheet);d.variables.setText('C1 C2');self.assertFalse(d.validate());self.assertIn('One Y',d.error.text())
        e=p.categorical_points([0,1],plot_type='interval',variant='multiple_groups',group_indices=[2],interval_options={'pooled':True})
        d=create_similar_dialog(None,p.worksheet,e);self.assertEqual(d.roles.rowCount(),3)
        def options():
            child=self.app.activeModalWidget();self.assertFalse(child.variables.isEnabled());child.display['individual']=True;child.interval_options['bonferroni']=True;child.validate()
        QTimer.singleShot(0,options);d.edit_options();d.validate();self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        result=run_similar_graphs(p,e,d.recipes(),appearance=d.appearance_settings())[0]
        self.assertTrue(result['recipe']['parameters']['interval_options']['bonferroni']);self.assertTrue(result['recipe']['parameters']['display']['individual'])


if __name__=='__main__':unittest.main()
