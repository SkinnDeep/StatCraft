import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,unittest
from PySide6.QtCore import Qt,QPoint,QPointF,QMimeData,QCoreApplication,QEvent,QTimer
from PySide6.QtGui import QDragEnterEvent,QDropEvent,QKeyEvent
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox
from statcraft.graph_builder_dialog import GraphBuilderDialog,MIME
from statcraft.graph_builder import TYPES
from statcraft.verification_fonts import load_verification_fonts
from statcraft.similar_graph_dialog import create_similar_dialog,run_similar_graphs
from test_graph_builder import document


class BuilderDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)
    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_empty_preview_disabled_and_named_filterable_columns(self):
        p=document();d=GraphBuilderDialog(None,p.worksheet);self.assertFalse(d.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled());self.assertEqual(d.gallery.count(),9)
        d.search.setText('Strength');self.assertFalse(d.available.item(1).isHidden());self.assertTrue(d.available.item(0).isHidden());self.assertIn('Strength',d.available.item(1).text())

    def test_assignment_preview_create_and_no_source_history_changes(self):
        p=document();d=GraphBuilderDialog(None,p.worksheet);self.assertTrue(d.assign_columns('response_indices',[1]));self.assertTrue(d.update_preview());self.assertFalse(p.history)
        d.title.setText('Measurements');d.bins.setValue(6);self.assertTrue(d.validate());self.assertEqual(d.result(),QDialog.DialogCode.Accepted);self.assertEqual(d.settings()['options']['bins'],6)

    def test_cross_role_move_invalid_type_and_atomic_single_x_drop(self):
        d=GraphBuilderDialog(None,document().worksheet);d.set_graph_type('scatter');d.assign_columns('response_indices',[1]);d.assign_columns('x_index',[1]);self.assertEqual(d.mapping['response_indices'],[])
        before=dict((k,list(v)) for k,v in d.mapping.items());self.assertFalse(d.assign_columns('x_index',[0,2]));self.assertEqual(d.mapping,before);self.assertFalse(d.assign_columns('response_indices',[3]))
        d.set_graph_type('histogram');self.assertEqual(d.active_role,'response_indices');self.assertEqual(d.mapping['x_index'],[])

    def test_qt_drop_events_and_delete_key_remove_real_role_items(self):
        d=GraphBuilderDialog(None,document().worksheet);d.show();self.app.processEvents();role=d.roles['response_indices'];mime=QMimeData();mime.setData(MIME,json.dumps([1]).encode())
        enter=QDragEnterEvent(QPoint(10,10),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(role.viewport(),enter);self.assertTrue(enter.isAccepted())
        drop=QDropEvent(QPointF(10,10),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier);QApplication.sendEvent(role.viewport(),drop)
        self.assertEqual(d.mapping['response_indices'],[1]);role.item(0).setSelected(True)
        QApplication.sendEvent(role,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Delete,Qt.KeyboardModifier.NoModifier));self.assertEqual(d.mapping['response_indices'],[])

    def test_live_debounce_and_invalid_mapping_clears_stale_preview(self):
        d=GraphBuilderDialog(None,document().worksheet);d.assign_columns('response_indices',[1]);d.update_preview();self.assertIsNotNone(d.preview_entry)
        d.bins.setValue(8);self.assertTrue(d.timer.isActive());self.assertFalse(d.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled());d.update_preview()
        d.clear_mappings();self.assertFalse(d.update_preview());self.assertIsNone(d.preview_entry);self.assertFalse(d.validate())

    def test_all_nine_builder_previews_render(self):
        d=GraphBuilderDialog(None,document().worksheet);d.show();self.app.processEvents()
        for kind in TYPES:
            d.clear_mappings();d.set_graph_type(kind);d.assign_columns('response_indices',[3] if kind=='bar_chart' else [1,2] if kind=='matrix_plot' else [1])
            if kind=='scatter':d.assign_columns('x_index',[0])
            if kind=='time_series':d.assign_columns('x_index',[5])
            self.assertTrue(d.update_preview(),(kind,d.error.text()));self.app.processEvents();self.assertFalse(d.preview_frame.capture().isNull());self.assertIsNone(d.preview_chart.error,kind)

    def test_similar_roles_and_locked_builder_options(self):
        p=document();e=p.graph_builder('scatter',[1],0,[3]);d=create_similar_dialog(None,p.worksheet,e);self.assertEqual(d.roles.rowCount(),3)
        def options():
            child=self.app.activeModalWidget();self.assertFalse(child.gallery.isEnabled());self.assertFalse(child.available.isEnabled());self.assertFalse(child.assign_columns('response_indices',[2]));child.fit.setChecked(True);child.validate()
        QTimer.singleShot(0,options);d.edit_options();d.validate();self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        result=run_similar_graphs(p,e,d.recipes(),appearance=d.appearance_settings())[0];self.assertTrue(result['recipe']['parameters']['options']['fit']);self.assertEqual(result['result']['scatter_mode'],'regression_groups')


if __name__=='__main__':unittest.main()
