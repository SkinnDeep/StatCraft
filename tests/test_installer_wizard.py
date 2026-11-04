"""Unit tests for StatCraft Windows Setup Wizard and Uninstaller."""
import os
import sys
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["STATCRAFT_TESTING"] = "1"

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from installer_main import InstallerWindow, UninstallerWindow, get_drive_free_space
from statcraft.updater import register_file_associations, unregister_file_associations


class InstallerWizardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_drive_free_space(self):
        target = Path("C:/") if sys.platform == "win32" else Path.home()
        free_gb, total_gb = get_drive_free_space(target)
        self.assertGreater(total_gb, 0.0)

    def test_installer_wizard_flow(self):
        target_dir = Path("C:/StatCraftTest") if sys.platform == "win32" else (Path.home() / "StatCraftTest")
        w = InstallerWindow(target_dir=target_dir)
        w.show()
        self.app.processEvents()

        # Step 0: Welcome
        self.assertEqual(w.stack.currentIndex(), 0)
        self.assertFalse(w.btn_back.isEnabled())
        self.assertTrue(w.btn_next.isEnabled())
        self.assertEqual(w.btn_next.text(), "&Next >")

        # Navigate to Step 1: License Agreement
        w._go_next()
        self.assertEqual(w.stack.currentIndex(), 1)
        self.assertTrue(w.btn_back.isEnabled())
        # By default "I do not accept" is checked, Next should be disabled
        self.assertTrue(w.radio_decline.isChecked())
        self.assertFalse(w.btn_next.isEnabled())

        # Accept license
        w.radio_accept.setChecked(True)
        self.app.processEvents()
        self.assertTrue(w.btn_next.isEnabled())

        # Navigate to Step 2: Destination Location
        w._go_next()
        self.assertEqual(w.stack.currentIndex(), 2)
        self.assertTrue(w.btn_back.isEnabled())
        self.assertTrue(w.btn_next.isEnabled())
        self.assertIn("StatCraftTest", w.txt_dest.text())
        self.assertIn("free disk space", w.lbl_free_space.text())

        # Navigate to Step 3: Additional Tasks
        w._go_next()
        self.assertEqual(w.stack.currentIndex(), 3)
        self.assertTrue(w.chk_desktop.isChecked())
        self.assertTrue(w.chk_start.isChecked())
        self.assertTrue(w.chk_assoc_mpx.isChecked())
        self.assertTrue(w.chk_assoc_mtw.isChecked())
        self.assertTrue(w.chk_assoc_jmp.isChecked())

        # Navigate to Step 4: Ready to Install
        w._go_next()
        self.assertEqual(w.stack.currentIndex(), 4)
        self.assertEqual(w.btn_next.text(), "&Install")
        summary = w.txt_summary.toPlainText()
        self.assertIn("StatCraftTest", summary)
        self.assertIn(".mpx", summary)
        self.assertIn(".jmp", summary)

        # Test Back navigation
        w._go_back()
        self.assertEqual(w.stack.currentIndex(), 3)
        w._go_back()
        self.assertEqual(w.stack.currentIndex(), 2)
        w._go_back()
        self.assertEqual(w.stack.currentIndex(), 1)
        w._go_back()
        self.assertEqual(w.stack.currentIndex(), 0)

        w.close()
        w.deleteLater()
        self.app.processEvents()

    def test_uninstaller_window(self):
        target_dir = Path("C:/StatCraftTest") if sys.platform == "win32" else (Path.home() / "StatCraftTest")
        u = UninstallerWindow(target_dir=target_dir)
        u.show()
        self.app.processEvents()
        self.assertTrue(u.btn_uninstall.isEnabled())
        self.assertTrue(u.btn_cancel.isEnabled())
        self.assertIn("StatCraftTest", u.lbl_prompt.text())
        u.close()
        u.deleteLater()
        self.app.processEvents()

    @unittest.skipUnless(sys.platform == "win32", "Windows registry file associations require Windows OS")
    def test_file_associations_dry_run(self):
        # Register and unregister with dummy test path
        dummy_exe = Path("C:/Windows/notepad.exe")
        ok = register_file_associations(dummy_exe, [".mpx", ".jmp"])
        self.assertTrue(ok)
        ok_uninst = unregister_file_associations([".mpx", ".jmp"])
        self.assertTrue(ok_uninst)

    def test_non_windows_file_associations_safely_ignored(self):
        if sys.platform != "win32":
            self.assertFalse(register_file_associations(Path("/tmp/fake"), [".mpx"]))
            self.assertFalse(unregister_file_associations([".mpx"]))


if __name__ == "__main__":
    unittest.main()
