import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.variable_dialogs import ProcedureDialog

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestDialogStateMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_procedure_dialog_remembers_state(self):
        ws = Worksheet("BatchData", [
            Column("Strength", "number", [10.5, 12.0, 14.2]),
            Column("Temp", "number", [150.0, 160.0, 155.0]),
        ])
        specs = [
            dict(key="response", label="Response:", kinds=("number",)),
            dict(key="predictor", label="Predictor:", kinds=("number",)),
        ]
        fields = [
            dict(key="conf_level", label="Confidence:", default="95.0"),
            dict(key="plot_fits", label="Plot fits:", boolean=True, default=False),
        ]

        # First run: fill values and validate
        dlg1 = ProcedureDialog(None, "Regression Test", ws, specs, fields)
        dlg1.controls["response"].setText("C1")
        dlg1.controls["predictor"].setText("C2")
        dlg1.controls["conf_level"].setText("99.0")
        dlg1.controls["plot_fits"].setChecked(True)
        dlg1.validate()
        self.assertEqual(dlg1.parameters["response"], 0)
        self.assertEqual(dlg1.parameters["predictor"], 1)
        dlg1.close()

        # Second run: open new dialog on same worksheet (e.g. via Ctrl+E)
        dlg2 = ProcedureDialog(None, "Regression Test", ws, specs, fields)
        # Should be pre-populated with previous values!
        self.assertEqual(dlg2.controls["response"].text(), "C1")
        self.assertEqual(dlg2.controls["predictor"].text(), "C2")
        self.assertEqual(dlg2.controls["conf_level"].text(), "99.0")
        self.assertTrue(dlg2.controls["plot_fits"].isChecked())
        dlg2.close()


if __name__ == "__main__":
    unittest.main()
