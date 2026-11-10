import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter


class TestMissingSentinels(unittest.TestCase):
    def test_missing_sentinels_return_none_for_number(self):
        sentinels = ["", "*", "NA", "na", "N/A", "n/a", "NaN", "nan", "None", ".", "-"]
        for s in sentinels:
            val = Presenter.parse_cell(s, "number")
            self.assertIsNone(val, f"Sentinel {s!r} should parse to None")

    def test_set_cell_with_missing_sentinels(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [1.0, 2.0, 3.0], metadata={"auto_type": True}),
        ])
        p = Presenter()
        p.worksheet = ws

        # Setting 'NA' or '*' should store None, keeping kind as number
        p.set_cell(1, 0, "NA")
        self.assertIsNone(ws.columns[0].values[1])
        self.assertEqual(ws.columns[0].kind, "number")

        p.set_cell(2, 0, "-")
        self.assertIsNone(ws.columns[0].values[2])
        self.assertEqual(ws.columns[0].kind, "number")

    def test_auto_type_converts_number_to_text_when_text_entered(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [10.5, None], metadata={"auto_type": True}),
        ])
        p = Presenter()
        p.worksheet = ws

        # User enters 'Batch A' into row 1
        p.set_cell(1, 0, "Batch A")
        self.assertEqual(ws.columns[0].kind, "text")
        self.assertEqual(ws.columns[0].values[0], "10.5")
        self.assertEqual(ws.columns[0].values[1], "Batch A")


if __name__ == "__main__":
    unittest.main()
