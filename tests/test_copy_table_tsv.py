import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestCopyTableTSV(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_text_to_tsv_conversion(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        pipe_table = "Components | Fit | SE Fit | Lower CI | Upper CI\nComp1 | 12.5 | 0.42 | 11.6 | 13.4"
        tsv = win._text_to_tsv(pipe_table)
        lines = tsv.strip().split("\n")
        self.assertEqual(lines[0], "Components\tFit\tSE Fit\tLower CI\tUpper CI")
        self.assertEqual(lines[1], "Comp1\t12.5\t0.42\t11.6\t13.4")

        space_table = "Source       DF   Adj SS   Adj MS\nRegression    2    45.12    22.56\nError        10    15.90     1.59"
        tsv_space = win._text_to_tsv(space_table)
        lines_space = tsv_space.strip().split("\n")
        self.assertEqual(lines_space[0], "Source\tDF\tAdj SS\tAdj MS")
        self.assertEqual(lines_space[1], "Regression\t2\t45.12\t22.56")

        win.close()


if __name__ == "__main__":
    unittest.main()
