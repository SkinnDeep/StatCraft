import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMessageBox
from statcraft.modern_app import ModernWindow
from statcraft.updater import STATCRAFT_VERSION
from statcraft.updater_dialog import CheckForUpdatesDialog, UpdateDownloadWorker

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

    def test_check_for_updates_dialog_in_app_flow(self):
        info = {
            "update_available": True,
            "current_version": "112.0.0",
            "latest_version": "113.0.0",
            "release_name": "StatCraft v113.0.0",
            "release_notes": "Improved in-app updating and statistical tests.",
            "setup_download_url": "https://example.com/StatCraft-Setup-v113.0.0.exe",
        }
        dlg = CheckForUpdatesDialog(initial_info=info, auto_download=False)
        self.assertFalse(dlg.btn_action.isHidden())
        self.assertTrue(dlg.btn_action.isEnabled())
        self.assertEqual(dlg.btn_action.text(), "Download & Install Update")
        self.assertIn("v113.0.0", dlg.status_lbl.text())

        # Test download progress updates UI without launching browser
        dlg._on_download_progress(5000000, 10000000)
        self.assertEqual(dlg.prog_bar.value(), 50)
        self.assertIn("50%", dlg.status_lbl.text())

        # Test download finished prompts to launch installer
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dlg._on_download_finished("C:/fake/path/StatCraft-Setup.exe")
            self.assertEqual(dlg.btn_action.text(), "Install & Restart")

        # Test launching installer
        with patch("subprocess.Popen") as mock_popen:
            with patch.object(QApplication, "quit") as mock_quit:
                dlg._launch_installer("C:/fake/path/StatCraft-Setup.exe")
                mock_popen.assert_called_once_with(["C:/fake/path/StatCraft-Setup.exe"])
                mock_quit.assert_called_once()

        dlg.close()

if __name__ == "__main__":
    unittest.main()
