import os
import sys
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QPlainTextEdit
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestPart4Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_duplicate_column_action(self):
        ws = Worksheet("Sheet1", [Column("VarA", "number", [1, 2, 3])])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        win.duplicate_column_action(0)
        self.assertEqual(len(win.presenter.worksheet.columns), 2)
        self.assertEqual(win.presenter.worksheet.columns[1].name, "VarA (Copy)")
        self.assertEqual(win.presenter.worksheet.columns[1].values, [1, 2, 3])

        win.close()

    def test_output_tab_cycling(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        self.assertTrue(hasattr(win, "next_output_tab"))
        self.assertTrue(hasattr(win, "prev_output_tab"))

        # Add dummy tabs
        t1 = QPlainTextEdit("Tab 1")
        t2 = QPlainTextEdit("Tab 2")
        win.result_tabs.addTab(t1, "Tab 1")
        win.result_tabs.addTab(t2, "Tab 2")
        count = win.result_tabs.count()
        win.result_tabs.setCurrentIndex(0)

        win.next_output_tab()
        self.assertEqual(win.result_tabs.currentIndex(), 1)
        win.prev_output_tab()
        self.assertEqual(win.result_tabs.currentIndex(), 0)
        win.prev_output_tab()
        self.assertEqual(win.result_tabs.currentIndex(), count - 1)

        win.close()

    def test_clear_session_output_method(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.history.append({"title": "A", "time": "1", "result": {}})
        self.assertEqual(len(win.presenter.history), 1)

        old_q = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        try:
            win.clear_session_output()
            self.assertEqual(len(win.presenter.history), 0)
        finally:
            QMessageBox.question = old_q

        win.close()

    def test_column_header_tooltips_with_formula_and_desc(self):
        ws = Worksheet("Sheet1", [
            Column("X", "number", [10, 20], metadata={"formula": "C2 * 2", "description": "Target measure"})
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        item = win.table.horizontalHeaderItem(0)
        self.assertIsNotNone(item)
        tooltip = item.toolTip()
        self.assertIn("Formula: C2 * 2", tooltip)
        self.assertIn("Description: Target measure", tooltip)

        win.close()

    def test_duplicate_sheet_action_in_menu(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        self.assertTrue(hasattr(win, "duplicate_sheet_action"))
        win.close()

    def test_clear_formats_full_column(self):
        ws = Worksheet("Sheet1", [
            Column("X", "number", [1, 2, 3, 4, 5], metadata={
                "cell_highlights": {"0": "#ff0000", "4": "#00ff00"},
                "cell_comments": {"0": "note"}
            })
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Simulate selecting column 0
        win._selected_columns = lambda: [0]
        # Trigger clear formats
        win.presenter.clear_cell_formats(list(range(5)), [0])
        self.assertEqual(win.presenter.worksheet.columns[0].metadata.get("cell_highlights", {}), {})
        self.assertEqual(win.presenter.worksheet.columns[0].metadata.get("cell_comments", {}), {})

        win.close()

    def test_save_graph_as_svg(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        win.presenter.set_cell(0, 0, "1")
        win.presenter.set_cell(1, 0, "2")
        win.presenter.set_cell(2, 0, "3")
        win.presenter.set_cell(0, 1, "2")
        win.presenter.set_cell(1, 1, "4")
        win.presenter.set_cell(2, 1, "6")
        entry = win.presenter.scatter_plot(0, 1)
        win.show_result(entry)

        with tempfile.TemporaryDirectory() as td:
            svg_path = Path(td) / "test.svg"
            old_save = QFileDialog.getSaveFileName
            QFileDialog.getSaveFileName = staticmethod(lambda *args, **kwargs: (str(svg_path), "Scalable Vector Graphic (*.svg)"))
            try:
                win.save_graph_as(entry)
                self.assertTrue(svg_path.exists())
                svg_text = svg_path.read_text(encoding="utf-8")
                self.assertIn("<svg", svg_text)
                self.assertIn("</svg>", svg_text)
            finally:
                QFileDialog.getSaveFileName = old_save

        win.presenter.dirty = False
        win.close()

    def test_find_output_context(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        editor = QPlainTextEdit("Analysis of Variance\nSource DF Adj SS\nFactor 2 15.4")
        win.result_tabs.addTab(editor, "ANOVA Output")
        win.result_tabs.setCurrentWidget(editor)

        # Mock _find_in_text_dialog
        called = []
        win._find_in_text_dialog = lambda target: called.append(target)
        win.find_dialog()
        self.assertEqual(len(called), 1)
        self.assertIs(called[0], editor)

        win.close()

    def test_export_all_graphs_empty_notice(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.history.clear()

        info_called = []
        old_info = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *args, **kwargs: info_called.append(True))
        try:
            win.export_all_graphs_dialog()
            self.assertEqual(len(info_called), 1)
        finally:
            QMessageBox.information = old_info

        win.close()


if __name__ == "__main__":
    unittest.main()
