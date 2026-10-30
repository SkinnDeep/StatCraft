import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QTimer,Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox
from statcraft.boxplot_dialogs import BoxplotDialog,BoxplotTypeDialog,MODES
from statcraft.similar_graph_dialog import create_similar_dialog,run_similar_graphs
from test_boxplot_graphs import document


class BoxplotDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_gallery_four_choices_and_titles(self):
        dialog=BoxplotTypeDialog();self.assertEqual(set(dialog.mode_buttons),set(MODES))
        for key,button in dialog.mode_buttons.items():button.click();self.assertEqual(dialog.mode,key)

    def test_group_roles_transfer_and_variable_order(self):
        p=document();dialog=BoxplotDialog(None,p.worksheet,'multiple_groups')
        dialog.variables.setText('C1 C2');dialog.activate('group')
        for i in range(dialog.available.count()):
            if dialog.available.item(i).data(Qt.ItemDataRole.UserRole) in (2,3):dialog.available.item(i).setSelected(True)
        dialog.transfer();dialog.scale_order.setCurrentIndex(1);self.assertTrue(dialog.validate())
        self.assertEqual(dialog.settings()['group_indices'],[2,3]);self.assertEqual(dialog.settings()['variable_position'],'inner')

    def test_one_y_validation_is_inline_and_nonmutating(self):
        p=document();dialog=BoxplotDialog(None,p.worksheet,'one');dialog.variables.setText('C1 C2')
        self.assertFalse(dialog.validate());self.assertIn('One Y',dialog.error.text());self.assertFalse(p.history)
        dialog.variables.setText('C1');self.assertTrue(dialog.validate())

    def test_display_scale_accept_and_cancel(self):
        p=document();dialog=BoxplotDialog(None,p.worksheet)
        def display():
            child=self.app.activeModalWidget();child.controls['mean_symbol'].setChecked(True);child.accept()
        QTimer.singleShot(0,display);dialog.edit_data_view();self.assertTrue(dialog.display['mean_symbol'])
        def scale():
            child=self.app.activeModalWidget();child.controls['y_min'].setText('0');child.controls['y_max'].setText('250')
            child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        QTimer.singleShot(0,scale);dialog.edit_scale();self.assertEqual(dialog.presentation_settings()['y_max'],250)
        QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject());dialog.edit_data_view();self.assertTrue(dialog.display['mean_symbol'])

    def test_similar_mapping_and_options_preserve_display(self):
        p=document();entry=p.boxplot_graphs([0,1],'multiple_groups',[2],display={'individual':True})
        dialog=create_similar_dialog(None,p.worksheet,entry);self.assertEqual(dialog.roles.rowCount(),3)
        def options():
            child=self.app.activeModalWidget();self.assertFalse(child.variables.isEnabled());child.display['mean_connect']=True;child.validate()
        QTimer.singleShot(0,options);dialog.edit_options();dialog.validate()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        copied=run_similar_graphs(p,entry,dialog.recipes(),appearance=dialog.appearance_settings())[0]
        self.assertTrue(copied['result']['panels'][0]['display']['mean_connect']);self.assertTrue(copied['result']['panels'][0]['display']['individual'])


if __name__=='__main__':unittest.main()
