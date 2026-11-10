import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.session_commands import parse_script_blocks

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestSessionCommandsAndBatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_parse_comments_and_semicolon_subcommands(self):
        script = """
        NOTE Sample Batch Exec Script
        # Comment line
        CAPABILITY C1;
          LSPEC 9.0;
          USPEC 11.0;
          TARGET 10.0.
        LET K1 = MEAN(C1) # Trailing comment
        """
        blocks = parse_script_blocks(script)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][0], "CAPABILITY C1")
        self.assertEqual(blocks[0][1], ["LSPEC 9.0", "USPEC 11.0", "TARGET 10.0"])
        self.assertEqual(blocks[1][0], "LET K1 = MEAN(C1)")

    def test_batch_mtb_script_execution_and_do_loop(self):
        p = Presenter()
        p.worksheet = Worksheet("Batch", [
            Column("Diameter", "number", [9.8, 10.1, 10.0, 9.9, 10.2, 10.0, 9.7, 10.3]),
            Column("Shift", "text", ["Day", "Day", "Night", "Night", "Day", "Day", "Night", "Night"]),
        ])
        script = """
        # Set values and compute capability with subcommands
        SET C3; 1:8.
        NAME C3 'Index'
        LET K1 = MEAN(C1)
        CAPABILITY C1;
          LSPEC 9.5;
          USPEC 10.5;
          TARGET 10.0.
        RANDOM 8 C4;
          WEIBULL 2.0 10.0.
        TALLY C2
        INDICATOR C2
        DO K2 = 1:2
          LET C5 = C1 + K2
        ENDDO
        """
        entries = p.execute_session_script(script)
        self.assertEqual(len(entries), 9)
        self.assertEqual(p.worksheet.columns[2].name, "Index")
        self.assertEqual(p.worksheet.columns[2].values, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        self.assertAlmostEqual(p.worksheet.constants[0].values[0], 10.0, places=4)
        self.assertEqual(len(p.worksheet.columns[3].values), 8)
        self.assertIn("Shift_Day", [c.name for c in p.worksheet.columns])
        self.assertEqual(p.worksheet.columns[4].values[0], 11.8)

    def test_subset_and_erase_commands(self):
        p = Presenter()
        p.worksheet = Worksheet("Main", [
            Column("Val", "number", [5.0, 15.0, 25.0]),
            Column("Temp", "number", [100.0, 200.0, 300.0]),
        ])
        p.execute_session_script("SUBSET; WHERE C1 >= 15; NAME 'Filtered'.")
        self.assertEqual(p.worksheet.name, "Filtered")
        self.assertEqual(p.worksheet.row_count, 2)
        p.execute_session_command("ERASE C2")
        self.assertEqual(p.worksheet.columns[1].values, [])
        self.assertEqual(p.worksheet.columns[1].name, "C2")

    def test_command_line_ui_executes_multiline(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = Worksheet("CmdUI", [Column("X", "number", [1.0, 2.0, 3.0, 4.0, 5.0])])
        win.command_editor.setPlainText("CAPABILITY C1;\n LSPEC 0;\n USPEC 10.")
        win.run_command_line()
        self.assertTrue(any("Capability" in e.get("title", "") for e in win.presenter.history))
        self.assertTrue(hasattr(win, "run_mtb_script_dialog"))
        self.assertTrue(hasattr(win, "round_datetime_dialog"))
        self.assertTrue(hasattr(win, "convert_text_to_datetime_dialog"))
        win.close()

    def test_convert_text_and_round_datetime(self):
        from statcraft.model import display_date
        p = Presenter()
        p.worksheet = Worksheet("Dates", [
            Column("RawDates", "text", ["2026-05-14 14:35:22", "11/09/2026", None]),
        ])
        p.convert_text_to_datetime(0, "", "ParsedDate")
        self.assertEqual(p.worksheet.columns[1].kind, "date")
        self.assertEqual(display_date(p.worksheet.columns[1].values[1]), "2026-11-09")

        p.round_datetime(1, "Month", "MonthStart")
        self.assertEqual(display_date(p.worksheet.columns[2].values[0]), "2026-05-01")
        self.assertEqual(display_date(p.worksheet.columns[2].values[1]), "2026-11-01")


if __name__ == "__main__":
    unittest.main()
