import unittest
from PySide6.QtWidgets import QApplication, QPushButton

from statcraft.model import Worksheet, Column
from statcraft.modern_app import ModernWindow
from statcraft.connect_hub import ConnectBridgeWidget


class TestConnectHud(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_connect_bridge_banner_present_on_connected_results(self):
        window = ModernWindow()
        ws = Worksheet("ChemStudy", [
            Column("Yield", "number", [80.0, 85.0, 88.0, 92.0]),
            Column("Temp", "number", [150.0, 160.0, 170.0, 180.0]),
        ])
        window.presenter.worksheet = ws
        window.presenter.two_sample_t({"data_format": 1, "sample1_col": 0, "sample2_col": 1})
        entry = window.presenter.history[-1]

        window.show_result(entry)

        # Find the ConnectBridgeWidget inside the result view
        bridges = window.findChildren(ConnectBridgeWidget)
        self.assertGreaterEqual(len(bridges), 1, "ConnectBridgeWidget should be embedded in the result view")

        bridge = bridges[0]
        buttons = bridge.findChildren(QPushButton)
        button_texts = [b.text() for b in buttons]

        self.assertTrue(any("Minitab" in t for t in button_texts), f"Expected Minitab button, got {button_texts}")
        self.assertTrue(any("JMP" in t for t in button_texts), f"Expected JMP button, got {button_texts}")
        self.assertTrue(any("R Workbench" in t for t in button_texts), f"Expected R Workbench button, got {button_texts}")
        self.assertTrue(any("ReportPad" in t for t in button_texts), f"Expected ReportPad button, got {button_texts}")

        window.close()


if __name__ == "__main__":
    unittest.main()
