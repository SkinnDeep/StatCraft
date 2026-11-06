import unittest
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

    def test_sandbox_hub_widget(self):
        hub = StatCraftSandboxHub()
        self.assertIsNotNone(hub.btn_launch)
        self.assertIn("Launch Live Sandbox", hub.btn_launch.text())
        hub.close()

if __name__ == "__main__":
    unittest.main()
