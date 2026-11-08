import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMessageBox
from statcraft.modern_app import ModernWindow
from statcraft.updater import STATCRAFT_VERSION

class TestStartupUpdater(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_status_update_button_present(self):
        win = ModernWindow(sandbox_mode=False)
        self.assertTrue(hasattr(win, "status_update_btn"))
        self.assertTrue(win.status_update_btn.isHidden())
        win.closeEvent = lambda e: e.accept()
        win.close()

    def test_on_startup_update_finished_up_to_date(self):
        win = ModernWindow(sandbox_mode=False)
        info = {
            "update_available": False,
            "current_version": STATCRAFT_VERSION,
            "latest_version": STATCRAFT_VERSION,
        }
        win._on_startup_update_finished(info)
        self.assertTrue(win.status_update_btn.isHidden())
        self.assertIn("up to date", win.statusBar().currentMessage())
        win.closeEvent = lambda e: e.accept()
        win.close()

    @patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No)
    def test_on_startup_update_finished_update_available(self, mock_msg):
        win = ModernWindow(sandbox_mode=True)
        info = {
            "update_available": True,
            "current_version": "112.0.0",
            "latest_version": "113.0.0",
            "release_name": "StatCraft v113.0.0",
        }
        win._on_startup_update_finished(info)
        self.assertFalse(win.status_update_btn.isHidden())
        self.assertEqual(win.status_update_btn.text(), "Update: v113.0.0")
        self.assertIn("v113.0.0", win.statusBar().currentMessage())
        mock_msg.assert_called_once()
        win.closeEvent = lambda e: e.accept()
        win.close()

if __name__ == "__main__":
    unittest.main()
