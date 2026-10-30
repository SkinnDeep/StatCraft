import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QTimer,Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox
from statcraft.dotplot_dialogs import DotplotDialog,DotplotTypeDialog,VARIANTS
from statcraft.similar_graph_dialog import create_similar_dialog,run_similar_graphs
from test_dotplot_graphs import document


class DotplotDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_gallery_seven_choices(self):
        d=DotplotTypeDialog();self.assertEqual(set(d.mode_buttons),set(VARIANTS))
        for key,b in d.mode_buttons.items():b.click();self.assertEqual(d.mode,key)

    def test_named_role_transfer_and_stack_switch(self):
        d=DotplotDialog(None,document().worksheet,'multiple_stack_groups');d.variables.setText('C1 C2');d.activate('group')
        for i in range(d.available.count()):
            item=d.available.item(i)
            if item.data(Qt.ItemDataRole.UserRole) in (2,3):item.setSelected(True);self.assertTrue('Batch' in item.text() or 'Shift' in item.text())
        d.transfer();d.scale_order.setCurrentIndex(1);d.stack.setChecked(False);self.assertTrue(d.validate())
        self.assertEqual(d.settings()['group_indices'],[2,3]);self.assertFalse(d.settings()['stack'])

    def test_data_view_and_scale_commit_cancel(self):
        d=DotplotDialog(None,document().worksheet,'one_stack_groups');d.group.setText('C3 C4')
        def view():
            child=self.app.activeModalWidget();child.controls[0].setChecked(False);child.accept()
        QTimer.singleShot(0,view);d.edit_data_view();self.assertEqual(d.color_levels,[1])
        def scale():
            child=self.app.activeModalWidget();child.controls['x_min'].setText('0');child.controls['x_max'].setText('5');child.intervals.setValue(4)
            child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        QTimer.singleShot(0,scale);d.edit_scale();self.assertEqual(d.intervals,4);self.assertEqual(d.presentation_settings()['x_max'],5)
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());d.edit_data_view();self.assertEqual(d.color_levels,[1])

    def test_inline_validation_and_similar_options(self):
        p=document();d=DotplotDialog(None,p.worksheet);d.variables.setText('C1 C2');self.assertFalse(d.validate());self.assertIn('One Y',d.error.text())
        e=p.dotplot_graphs([0,1],'multiple_stack_groups',[2]);d=create_similar_dialog(None,p.worksheet,e);self.assertEqual(d.roles.rowCount(),3)
        def options():
            child=self.app.activeModalWidget();self.assertFalse(child.variables.isEnabled());child.stack.setChecked(False);child.intervals=5;child.validate()
        QTimer.singleShot(0,options);d.edit_options();d.validate();self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        result=run_similar_graphs(p,e,d.recipes(),appearance=d.appearance_settings())[0]
        self.assertFalse(result['recipe']['parameters']['stack']);self.assertEqual(result['recipe']['parameters']['intervals'],5)


if __name__=='__main__':unittest.main()
