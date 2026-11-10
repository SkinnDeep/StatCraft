import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestFindReplaceMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_replace_action_exists_on_edit_menu(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        self.assertTrue(hasattr(win, "replace_action"))
        self.assertIsNotNone(win.replace_action)
        self.assertIn("Replace", win.replace_action.text())
        self.assertEqual(win.replace_action.shortcut().toString(), "Ctrl+H")

        win.close()


if __name__ == "__main__":
    unittest.main()
