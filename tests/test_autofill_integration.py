import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestAutofillIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_presenter_autofill_column(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [10, 20, 30]),
            Column("C2", "text", ["Batch_01", "Batch_02"]),
        ])
        p = Presenter()
        p.worksheet = ws

        # Autofill C1: start=0, sample_len=3, count=2 -> [40, 50]
        p.autofill_column(0, 0, 3, 2)
        self.assertEqual(ws.columns[0].values, [10, 20, 30, 40, 50])

        # Autofill C2: start=0, sample_len=2, count=2 -> ['Batch_03', 'Batch_04']
        p.autofill_column(1, 0, 2, 2)
        self.assertEqual(ws.columns[1].values, ["Batch_01", "Batch_02", "Batch_03", "Batch_04"])

    def test_modern_window_has_autofill(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        self.assertTrue(hasattr(win, "autofill_dialog"))
        win.close()


if __name__ == "__main__":
    unittest.main()
