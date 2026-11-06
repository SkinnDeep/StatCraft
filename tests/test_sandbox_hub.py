import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from statcraft.sandbox_hub import StatCraftSandboxHub, get_git_status_info

class TestSandboxHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_git_info_retrieval(self):
        info = get_git_status_info()
        self.assertIn("branch", info)
        self.assertIn("commit", info)
        self.assertIn("message", info)

    def test_git_info_fallback(self):
        # Pass non-existent directory to trigger fallback
        info = get_git_status_info(Path("C:/nonexistent_dir_123456"))
        self.assertEqual(info["branch"], "local-dev")
        self.assertEqual(info["commit"], "source")
        self.assertEqual(info["message"], "Local development working tree")

    def test_sandbox_hub_widget(self):
        hub = StatCraftSandboxHub()
        self.assertIsNotNone(hub.btn_launch)
        self.assertIn("Launch Live Sandbox", hub.btn_launch.text())

        # Test diagnostics copy
        with patch.object(QApplication, "clipboard") as mock_cb:
            cb_inst = MagicMock()
            mock_cb.return_value = cb_inst
            hub.copy_diagnostics()
            cb_inst.setText.assert_called_once()
            self.assertIn("StatCraft Live Sandbox Diagnostics", cb_inst.setText.call_args[0][0])

        # Test open_scratch_dir creates directory
        scratch = hub.repo_root / ".sandbox_workspace"
        if sys_platform_win := True:
            with patch("os.startfile"):
                hub.open_scratch_dir()
                self.assertTrue(scratch.is_dir())

        hub.close()

if __name__ == "__main__":
    unittest.main()
