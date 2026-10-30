import tempfile,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts
from statcraft.workspace_state import REPORT


class OutputWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.p=Presenter();self.p.worksheet=Worksheet('Measurements',[Column('Run',values=list(range(1,9))),Column('Strength',values=[12,15,13,18,17,20,22,21])])
        self.w=ModernWindow(self.p);self.w.show();self.app.processEvents()
        self.ws=self.w._workspace

    def tearDown(self):
        self.p.dirty=False;self.p._results_dirty=False;self.w.close();self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def graph(self):
        e=self.p.scatter_plot(0,1);self.w.show_result(e);self.app.processEvents();return e

    def test_multiple_named_tabs_and_close_are_non_destructive(self):
        a=self.graph();b=self.graph();self.assertEqual(self.ws.tabs.count(),2)
        self.assertEqual(self.ws.tabs.tabText(1),b['title']);dirty=self.p.dirty
        self.ws.close_current();self.assertEqual(len(self.p.history),2);self.assertEqual(self.p.dirty,dirty)
        self.assertIs(self.w.selected_entry,a);self.assertEqual(self.ws.tabs.count(),1)
        self.ws.reopen();self.assertIs(self.w.selected_entry,b);self.assertEqual(self.ws.tabs.count(),2)

    def test_close_all_retains_results_and_navigator_reopens(self):
        a=self.graph();self.graph();self.ws.close_all()
        self.assertEqual(self.ws.tabs.count(),0);self.assertEqual(len(self.p.history),2);self.assertIsNone(self.w.selected_entry)
        self.w.show_result(a);self.assertEqual(self.ws.tabs.count(),1)

    def test_tab_reorder_close_others_and_cycle(self):
        entries=[self.graph() for _ in range(3)];keys=[e['entry_id'] for e in entries]
        self.ws.tabs.moveTab(0,2);self.assertEqual(self.ws.state['open_ids'],keys[1:]+keys[:1])
        self.ws.close_all(keys[0]);self.assertEqual(self.ws.state['open_ids'],[keys[0]])
        self.ws.reopen();self.ws.cycle(1);self.assertEqual(len(self.ws.state['open_ids']),2)

    def test_per_result_zoom_selected_view_and_scroll_are_restored(self):
        a=self.graph();self.w.set_zoom(200);page=self.w.result_tabs.currentWidget()
        page.horizontalScrollBar().setValue(80);self.app.processEvents();expected=page.horizontalScrollBar().value()
        self.graph();self.w.show_result(a);self.app.processEvents()
        self.assertEqual(self.w._zoom_percent,200);self.assertEqual(self.w.result_tabs.currentWidget().horizontalScrollBar().value(),expected)
        self.w.result_tabs.setCurrentIndex(2);self.w.set_zoom(150);self.graph();self.w.show_result(a)
        self.assertEqual(self.w.result_tabs.tabText(self.w.result_tabs.currentIndex()),'Text export');self.assertEqual(self.w._zoom_percent,150)

    def test_report_pad_preserves_manual_edits_and_supports_office_snapshot(self):
        a=self.graph();self.w.send_output_to_report(a);self.ws.pad.appendPlainText('Operator note with Ω <literal>')
        self.assertEqual(self.ws.state['active'],REPORT);self.assertTrue(self.p.dirty)
        self.graph();self.ws.show_pad();self.assertIn('Operator note',self.ws.pad.toPlainText())
        snapshot=self.w._office_snapshot();self.assertEqual(snapshot.title,'ReportPad');self.assertFalse(snapshot.png)
        self.assertIn('Ω <literal>',snapshot.report)

    def test_workspace_and_report_restore_from_mpx_with_active_tab(self):
        a=self.graph();self.w.set_zoom(150);self.w.send_output_to_report(a);self.ws.pad.appendPlainText('Review this result')
        self.w.set_zoom(125)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'workspace.mpx';self.w.save_path(path);self.w.load_path(path);self.app.processEvents()
            self.assertEqual(self.ws.state['active'],REPORT);self.assertIn('Review this result',self.ws.pad.toPlainText())
            self.assertEqual(self.ws.tabs.count(),2);self.assertEqual(self.w._zoom_percent,125)
            self.w.show_result(self.p.history[0]);self.assertEqual(self.w._zoom_percent,150)

    def test_delete_prunes_tab_and_reopen_stack(self):
        a=self.graph();b=self.graph();self.w.delete_selected_output(b);self.ws.rebuild()
        self.assertNotIn(b['entry_id'],self.ws.state['open_ids']);self.assertNotIn(b,self.p.history)
        self.assertIs(self.w.selected_entry,a)

    def test_new_document_discards_old_report_without_cross_project_leak(self):
        self.graph();self.ws.pad.setPlainText('Old report')
        self.p.new();self.w._show_welcome();self.w.refresh()
        self.assertEqual(self.ws.tabs.count(),0);self.assertFalse(self.ws.pad.toPlainText())
