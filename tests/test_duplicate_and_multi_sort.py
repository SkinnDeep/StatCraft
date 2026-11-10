import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter


class TestDuplicateAndMultiSort(unittest.TestCase):
    def test_duplicate_column(self):
        ws = Worksheet("TestSheet", [
            Column("Score", "number", [10, 20, 30]),
            Column("Label", "text", ["A", "B", "C"]),
        ])
        p = Presenter()
        p.worksheet = ws

        # Duplicate Score (column 0)
        new_idx = p.duplicate_column(0)
        self.assertEqual(new_idx, 1)
        self.assertEqual(len(ws.columns), 3)
        self.assertEqual(ws.columns[1].name, "Score (Copy)")
        self.assertEqual(ws.columns[1].values, [10, 20, 30])
        self.assertEqual(ws.columns[2].name, "Label")

    def test_multi_column_sort(self):
        ws = Worksheet("TestSheet", [
            Column("Dept", "text", ["Sales", "Engineering", "Sales", "Engineering"]),
            Column("Salary", "number", [50000, 95000, 60000, 80000]),
            Column("Name", "text", ["Alice", "Bob", "Charlie", "David"]),
        ])
        p = Presenter()
        p.worksheet = ws

        # Sort all columns by Dept ascending, then Salary ascending
        all_cols = [0, 1, 2]
        p.sort_columns(all_cols, [0, 1], descending=False)

        # Engineering: 80000 (David), 95000 (Bob)
        # Sales: 50000 (Alice), 60000 (Charlie)
        self.assertEqual(ws.columns[0].values, ["Engineering", "Engineering", "Sales", "Sales"])
        self.assertEqual(ws.columns[1].values, [80000, 95000, 50000, 60000])
        self.assertEqual(ws.columns[2].values, ["David", "Bob", "Alice", "Charlie"])


if __name__ == "__main__":
    unittest.main()
