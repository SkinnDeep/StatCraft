import unittest
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet


class StatCraftWorkflowTests(unittest.TestCase):
    def test_default_new_worksheet_has_16_columns(self):
        p = Presenter()
        p.add_worksheet("Second")
        self.assertEqual(len(p.worksheet.columns), 16)
        self.assertEqual([c.name for c in p.worksheet.columns], ["C" + str(i) for i in range(1, 17)])

    def test_cut_insert_move_delete_and_erase_are_undoable(self):
        p = Presenter()
        p.worksheet = Worksheet("Data", [
            Column("A", values=[10, 20, 30]),
            Column("B", values=[1, 2, 3]),
            Column("C", values=[4, 5, 6]),
        ])
        clip = p.cut_block(0, 1, 0, 0)
        self.assertEqual(clip, "10\n20\n")
        self.assertEqual(p.worksheet.columns[0].values, [None, None, 30])
        p.undo()
        self.assertEqual(p.worksheet.columns[0].values, [10, 20, 30])

        p.insert_cells(1, 0, 1, 2)
        self.assertEqual(p.worksheet.columns[0].values, [10, None, None, 20, 30])
        self.assertEqual(p.worksheet.columns[2].values, [4, 5, 6])
        p.undo()
        self.assertEqual(p.worksheet.columns[0].values, [10, 20, 30])

        p.insert_rows(1, 1)
        self.assertEqual(p.worksheet.columns[2].values, [4, None, 5, 6])
        p.undo()
        self.assertEqual(p.worksheet.columns[2].values, [4, 5, 6])

        p.insert_columns(1, 2)
        self.assertEqual([c.name for c in p.worksheet.columns], ["A", "C2", "C3", "B", "C"])
        p.undo()
        self.assertEqual([c.name for c in p.worksheet.columns], ["A", "B", "C"])

        p.move_columns([2], "before_c1")
        self.assertEqual([c.name for c in p.worksheet.columns], ["C", "A", "B"])
        p.move_columns([0], "before_column", 2)
        self.assertEqual([c.name for c in p.worksheet.columns], ["A", "C", "B"])
        p.undo(); p.undo()
        self.assertEqual([c.name for c in p.worksheet.columns], ["A", "B", "C"])

        p.delete_rows([0, 2])
        self.assertEqual(p.worksheet.columns[0].values, [20])
        p.undo()
        self.assertEqual(p.worksheet.columns[0].values, [10, 20, 30])

        p.erase_variables([1])
        self.assertEqual(p.worksheet.columns[1].name, "C2")
        self.assertEqual(p.worksheet.columns[1].values, [])
        p.undo()
        self.assertEqual(p.worksheet.columns[1].name, "B")
        self.assertEqual(p.worksheet.columns[1].values, [1, 2, 3])

    def test_sort_rank_assign_formula_and_find(self):
        p = Presenter()
        p.worksheet = Worksheet("SortRank", [
            Column("Score", values=[30, 10, 20, 10]),
            Column("Label", "text", ["c", "a1", "b", "a2"]),
            Column("Out"),
        ])
        p.sort_columns([0, 1], 0, descending=False)
        self.assertEqual(p.worksheet.columns[0].values, [10, 10, 20, 30])
        self.assertEqual(p.worksheet.columns[1].values, ["a1", "a2", "b", "c"])

        p.rank_column(0, "C3")
        self.assertEqual(p.worksheet.columns[2].values, [1.5, 1.5, 3, 4])

        p.assign_formula(2, "C1 * 2 + 1")
        self.assertEqual(p.worksheet.columns[2].values, [21, 21, 41, 61])
        self.assertEqual(p.worksheet.columns[2].metadata.get("formula"), "C1 * 2 + 1")

        self.assertEqual(p.find_cell("a2", 0, 0), (1, 1))
        self.assertEqual(p.find_cell("41", 0, 0, whole_word=True), (2, 2))
        self.assertIsNone(p.find_cell("nonexistent", 0, 0))

    def test_worksheet_info_description_and_session_commands(self):
        p = Presenter()
        p.worksheet = Worksheet("Experiment", [
            Column("X", values=[1, 2, 3, 4]),
            Column("Y", values=[2, 4, 6, 8]),
            Column("Z"),
        ])
        p.set_worksheet_description("Alice", "2026-10-15", "Pilot study")
        info = p.worksheet_information()["result"]
        self.assertEqual(info["creator"], "Alice")
        self.assertEqual(info["variables_table"][0]["count"], 4)

        p.execute_session_command("LET C3 = C1 + C2")
        self.assertEqual(p.worksheet.columns[2].values, [3, 6, 9, 12])
        p.execute_session_command("NAME C3 'Total'")
        self.assertEqual(p.worksheet.columns[2].name, "Total")
        desc_entry = p.execute_session_command("DESCRIBE C1 C3")
        self.assertEqual(len(desc_entry["result"]["columns"]), 2)
        reg_entry = p.execute_session_command("REGRESS C2 C1")
        self.assertAlmostEqual(reg_entry["result"]["r_squared"], 1.0)

    def test_cell_formatting_conditional_rules_replace_subset_and_output_management(self):
        p = Presenter()
        p.worksheet = Worksheet("Manufacturing", [
            Column("Strength", values=[10.0, 20.0, 30.0, 100.0, 15.0]),
            Column("Batch", "text", ["A", "B", "A", "C", "B"]),
        ])
        count = p.replace_cells("A", "Alpha", whole_word=True)
        self.assertEqual(count, 2)
        self.assertEqual(p.worksheet.columns[1].values, ["Alpha", "B", "Alpha", "C", "B"])
        p.undo()
        self.assertEqual(p.worksheet.columns[1].values, ["A", "B", "A", "C", "B"])

        p.set_cell_comment(0, 0, "First reading")
        self.assertEqual(p.worksheet.columns[0].metadata["cell_comments"]["0"], "First reading")
        p.set_cell_highlight([1, 2], [0], "#f8d7da")
        self.assertEqual(p.worksheet.columns[0].metadata["cell_highlights"]["1"], "#f8d7da")
        p.clear_cell_formats([1], [0])
        self.assertNotIn("1", p.worksheet.columns[0].metadata["cell_highlights"])

        p.set_column_format(0, "fixed", 3)
        self.assertEqual(p.worksheet.columns[0].metadata["format"], {"mode": "fixed", "decimals": 3})

        p.apply_conditional_formatting(0, "greater_than", 50, color="#fff3cd")
        from statcraft.conditional_formatting import effective_highlights
        self.assertEqual(effective_highlights(p.worksheet.columns[0])["3"], "#fff3cd")
        self.assertNotIn("3",p.worksheet.columns[0].metadata["cell_highlights"])
        p.clear_conditional_formatting([0])
        self.assertEqual(p.worksheet.columns[0].metadata['cell_highlights'],{'2':'#f8d7da'})

        sub = p.subset_worksheet("Top3", mode="include", row_indices=[0, 1, 2])
        self.assertEqual(sub.name, "Top3")
        self.assertEqual(sub.columns[0].values, [10.0, 20.0, 30.0])

        entry = p.describe_column(0)
        p.rename_result(entry, "Custom Strength Summary")
        self.assertEqual(entry["title"], "Custom Strength Summary")
        p.update_result_metadata(entry, title="Edited Title", xlabel="Load (N)", ylabel="Count")
        self.assertEqual(entry["title"], "Edited Title")
        self.assertEqual(entry["result"]["xlabel"], "Load (N)")
        self.assertTrue(p.delete_result(entry))
        self.assertNotIn(entry, p.history)


if __name__ == "__main__":
    unittest.main()
