import unittest
from PySide6.QtWidgets import QApplication

from statcraft.modern_app import ModernWindow


class TestStatCraftUnifiedUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_unified_window_layout(self):
        window = ModernWindow()
        window.closeEvent = lambda event: event.accept()

        # Verify UI default mode is permanent native StatCraft (minitab)
        self.assertEqual(window._ui_mode, "minitab")

        # Verify the top toolbar has theme toggle
        self.assertIsNotNone(window.btn_theme_toggle)
        self.assertTrue(window.btn_theme_toggle.isEnabled())

        # Verify mode toggle buttons are hidden from primary toolbar
        self.assertTrue(window.btn_mode_minitab.isHidden())
        self.assertTrue(window.btn_mode_jmp.isHidden())
        self.assertTrue(window.btn_mode_r.isHidden())

        # Verify standard Minitab menubar structure exists and is populated
        menu_titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
        self.assertIn("File", menu_titles)
        self.assertIn("Stat", menu_titles)
        self.assertIn("Graph", menu_titles)
        self.assertIn("Calc", menu_titles)
        self.assertIn("Help", menu_titles)

        window.close()


if __name__ == "__main__":
    unittest.main()
