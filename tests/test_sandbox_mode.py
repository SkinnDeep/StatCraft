import unittest
from unittest.mock import MagicMock, patch
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
        self.assertTrue(hasattr(win, "sandbox_workspace"))
        self.assertTrue(win.sandbox_workspace.is_dir())

        # Test dynamic theme restyling
        win.set_dark_mode(True)
        self.assertIn("#78350f", win.sandbox_banner.styleSheet())
        win.set_dark_mode(False)
        self.assertIn("#fef3c7", win.sandbox_banner.styleSheet())

        # Test diagnostics copy
        with patch.object(QApplication, "clipboard") as mock_cb:
            cb_inst = MagicMock()
            mock_cb.return_value = cb_inst
            win._copy_sandbox_diagnostics()
            cb_inst.setText.assert_called_once()
            self.assertIn("StatCraft Live Sandbox", cb_inst.setText.call_args[0][0])

        win.closeEvent = lambda e: e.accept()
        win.close()

    def test_standard_mode_no_sandbox(self):
        win = ModernWindow(sandbox_mode=False)
        self.assertFalse(getattr(win, "sandbox_mode", False))
        self.assertNotIn("LIVE SANDBOX", win.windowTitle())
        self.assertIsNone(getattr(win, "sandbox_banner", None))
        win.closeEvent = lambda e: e.accept()
        win.close()

    def test_startup_updates_suppressed_in_sandbox(self):
        win = ModernWindow(sandbox_mode=True)
        # Verify _check_startup_updates returns immediately without error
        win._check_startup_updates()
        self.assertFalse(hasattr(win, "_startup_worker"))
        win.closeEvent = lambda e: e.accept()
        win.close()

if __name__ == "__main__":
    unittest.main()
