import unittest
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet


class TestSmartPaste(unittest.TestCase):
    def setUp(self):
        ws = Worksheet("Sheet1", [
            Column("C1", "number", [None, None]),
            Column("C2", "number", [None, None]),
        ])
        self.p = Presenter()
        self.p.worksheet = ws

    def test_smart_paste_with_headers_at_row_0(self):
        clipboard = "Yield\tOperator\n98.5\tOpA\n99.2\tOpB\n97.8\tOpA\n"
        self.p.paste(0, 0, clipboard)

        ws = self.p.worksheet
        self.assertEqual(len(ws.columns), 2)
        # Column 0 should have header "Yield", type "number", values 98.5, 99.2, 97.8
        self.assertEqual(ws.columns[0].name, "Yield")
        self.assertEqual(ws.columns[0].kind, "number")
        self.assertEqual(ws.columns[0].values, [98.5, 99.2, 97.8])

        # Column 1 should have header "Operator", type "text", values OpA, OpB, OpA
        self.assertEqual(ws.columns[1].name, "Operator")
        self.assertEqual(ws.columns[1].kind, "text")
        self.assertEqual(ws.columns[1].values, ["OpA", "OpB", "OpA"])

    def test_paste_pure_numbers_at_row_0_does_not_consume_first_row(self):
        clipboard = "10.5\t20.5\n30.5\t40.5\n"
        self.p.paste(0, 0, clipboard)

        ws = self.p.worksheet
        self.assertEqual(ws.columns[0].kind, "number")
        self.assertEqual(ws.columns[0].values, [10.5, 30.5])
        self.assertEqual(ws.columns[1].values, [20.5, 40.5])


if __name__ == "__main__":
    unittest.main()
