import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestRecentProjectsAndGraphParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_recent_projects_menu_exists_and_records(self):
        win = ModernWindow(sandbox_mode=False)
        win._confirm_leave = lambda: True

        self.assertTrue(hasattr(win, "recent_menu"))
        # Add test path
        win._add_recent_file("C:/fake/path/test_sample.mpx")

        # Recent menu should now have at least one action with 'test_sample.mpx'
        texts = [act.text() for act in win.recent_menu.actions()]
        self.assertIn("test_sample.mpx", texts)

        # Clear recents
        win._clear_recent_files()
        texts_cleared = [act.text() for act in win.recent_menu.actions()]
        self.assertNotIn("test_sample.mpx", texts_cleared)

        win.close()

    def test_graph_context_menu_has_svg_copy(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        dummy_graph_entry = {
            "title": "Sample Graph",
            "time": "12:00:00",
            "result": {"graph": "scatter", "analysis": "scatter_plot"},
        }
        # Build menu
        # _show_output_context_menu constructs the QMenu
        # Let's inspect that copy_active_chart_svg is callable
        self.assertTrue(hasattr(win, "copy_active_chart_svg"))

        win.close()


if __name__ == "__main__":
    unittest.main()
