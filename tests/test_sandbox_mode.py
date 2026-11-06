import unittest
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow

class TestSandboxMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sandbox_ui_elements(self):
        win = ModernWindow(sandbox_mode=True)
        self.assertTrue(getattr(win, "sandbox_mode", False))
        self.assertIn("LIVE SANDBOX", win.windowTitle())
        self.assertIsNotNone(getattr(win, "sandbox_banner", None))
        self.assertFalse(win.sandbox_banner.isHidden())
        win.closeEvent = lambda e: e.accept()
        win.close()

    def test_standard_mode_no_sandbox(self):
        win = ModernWindow(sandbox_mode=False)
        self.assertFalse(getattr(win, "sandbox_mode", False))
        self.assertNotIn("LIVE SANDBOX", win.windowTitle())
        self.assertIsNone(getattr(win, "sandbox_banner", None))
        win.closeEvent = lambda e: e.accept()
        win.close()

if __name__ == "__main__":
    unittest.main()
