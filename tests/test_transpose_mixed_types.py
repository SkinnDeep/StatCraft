import unittest
from statcraft.model import Column, Worksheet
from statcraft.data_prep import transpose


class TestTransposeMixedTypes(unittest.TestCase):
    def test_transpose_homogeneous_columns_preserves_type(self):
        ws = Worksheet("Sheet1", [
            Column("A", "number", [10, 20]),
            Column("B", "number", [30, 40]),
        ])
        t_ws = transpose(ws, [0, 1])
        self.assertEqual(len(t_ws.columns), 3)  # Source, Row 1, Row 2
        self.assertEqual(t_ws.columns[1].kind, "number")
        self.assertEqual(t_ws.columns[1].values, [10, 30])
        self.assertEqual(t_ws.columns[2].values, [20, 40])

    def test_transpose_mixed_columns_coerces_to_text(self):
        ws = Worksheet("MixedSheet", [
            Column("ID", "text", ["Sample1", "Sample2"]),
            Column("Score", "number", [95.5, 88.0]),
        ])
        # In past versions, this threw ValueError("Transpose columns of the same data type.")
        t_ws = transpose(ws, [0, 1])
        self.assertEqual(len(t_ws.columns), 3)
        self.assertEqual(t_ws.columns[1].kind, "text")
        self.assertEqual(t_ws.columns[1].values, ["Sample1", "95.5"])
        self.assertEqual(t_ws.columns[2].values, ["Sample2", "88.0"])


if __name__ == "__main__":
    unittest.main()
