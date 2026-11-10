import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.variable_dialogs import ProcedureDialog

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestDialogAutoAdvance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_single_variable_selection_advances_to_next_field(self):
        ws = Worksheet("BatchData", [
            Column("Yield", "number", [98.0, 99.0]),
            Column("Temp", "number", [150.0, 160.0]),
            Column("Pressure", "number", [30.0, 32.0]),
        ])
        specs = [
            dict(key="response", label="Response:", kinds=("number",)),
            dict(key="factor", label="Factor:", kinds=("number",)),
        ]
        dlg = ProcedureDialog(None, "Two Variable Dialog", ws, specs, ())
        self.assertEqual(dlg.active_key, "response")

        # Select first item ("C1 Yield") and trigger transfer
        dlg.available.setCurrentRow(0)
        dlg.transfer()

        # "response" field should have C1
        self.assertIn("C1", dlg.controls["response"].text())
        # Active key should now have automatically advanced to "factor"!
        self.assertEqual(dlg.active_key, "factor")

        # Select second item ("C2 Temp") and trigger transfer
        dlg.available.setCurrentRow(1)
        dlg.transfer()

        # "factor" field should now have C2, and response was not overwritten!
        self.assertIn("C1", dlg.controls["response"].text())
        self.assertIn("C2", dlg.controls["factor"].text())

        dlg.close()


if __name__ == "__main__":
    unittest.main()
