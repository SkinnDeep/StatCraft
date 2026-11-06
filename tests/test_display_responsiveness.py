import unittest
from PySide6.QtWidgets import QApplication

from statcraft.modern_app import ModernWindow


class TestDisplayResponsiveness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_resizes_to_minimum_dimensions_safely(self):
        window = ModernWindow()
        window.closeEvent = lambda event: event.accept()

        # Check minimum window size accommodates laptop / 1024x768 screens
        min_size = window.minimumSize()
        self.assertLessEqual(min_size.width(), 1024)
        self.assertLessEqual(min_size.height(), 768)

        # Explicitly resize to constrained screen dimension
        window.resize(1024, 768)
        self.assertGreaterEqual(window.width(), 900)
        self.assertGreaterEqual(window.height(), 500)

        # In unified StatCraft, mode buttons are retired/hidden, theme toggle is enabled
        self.assertTrue(window.btn_mode_minitab.isHidden())
        self.assertTrue(window.btn_mode_jmp.isHidden())
        self.assertTrue(window.btn_mode_r.isHidden())
        self.assertTrue(window.btn_theme_toggle.isEnabled())

        # Test mode switching at minimum screen dimension
        window.set_ui_mode("jmp")
        self.assertEqual(window._ui_mode, "jmp")
        window.set_ui_mode("r")
        self.assertEqual(window._ui_mode, "r")
        window.set_ui_mode("minitab")
        self.assertEqual(window._ui_mode, "minitab")

        window.close()


if __name__ == "__main__":
    unittest.main()
