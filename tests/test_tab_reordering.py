import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.mpx import Project
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestTabReordering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_tab_movable_and_reordering(self):
        ws1 = Worksheet("SheetA", [Column("C1", "number", [1])])
        ws2 = Worksheet("SheetB", [Column("C1", "number", [2])])
        proj = Project(name="TestProj", worksheets=[ws1, ws2], active_index=0)
        proj.statcraft_owned = True

        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.native_project = proj
        win.presenter.worksheet = ws1
        win.refresh()

        # Check tabs are movable
        self.assertTrue(win.worksheet_tabs.isMovable())

        # Move tab 0 to position 1
        win._on_worksheet_tab_moved(0, 1)

        # Order in project should now be SheetB, SheetA
        self.assertEqual(proj.worksheets[0].name, "SheetB")
        self.assertEqual(proj.worksheets[1].name, "SheetA")

        win.close()


if __name__ == "__main__":
    unittest.main()
