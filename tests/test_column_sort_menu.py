import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestColumnSortMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_direct_sort_actions_on_context_menu(self):
        ws = Worksheet("SortSheet", [
            Column("Values", "number", [30.0, 10.0, 20.0]),
            Column("Labels", "text", ["C", "A", "B"]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Select column 0
        win.select_worksheet_column(0)
        menu = win.build_worksheet_context_menu()
        action_texts = [act.text() for act in menu.actions()]

        # Ensure direct Sort Ascending and Sort Descending actions are directly on the menu
        has_sort_asc = any("Sort Ascending" in t or "Smallest to Largest" in t for t in action_texts)
        has_sort_desc = any("Sort Descending" in t or "Largest to Smallest" in t for t in action_texts)
        self.assertTrue(has_sort_asc, f"Expected direct sort ascending action in {action_texts}")
        self.assertTrue(has_sort_desc, f"Expected direct sort descending action in {action_texts}")

        # Find the sort ascending action and trigger it
        sort_asc_act = next(act for act in menu.actions() if "Sort Ascending" in act.text() or "Smallest to Largest" in act.text())
        sort_asc_act.trigger()

        # Check that rows are sorted ascending
        self.assertEqual(win.presenter.worksheet.columns[0].values, [10.0, 20.0, 30.0])
        self.assertEqual(win.presenter.worksheet.columns[1].values, ["A", "B", "C"])

        win.close()


if __name__ == "__main__":
    unittest.main()
