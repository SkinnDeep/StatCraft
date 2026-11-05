"""Unit tests for JMP Process Screening platform."""
import unittest
import numpy as np

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.process_screening_engine import calculate_process_screening
from statcraft.process_screening_report import (
    format_process_screening_report,
    get_process_screening_tables,
)


class TestProcessScreening(unittest.TestCase):
    def setUp(self):
        np.random.seed(123)
        # Process 1: Very stable and capable (mean=50, sd=1)
        c1 = list(np.random.normal(50.0, 1.0, 50))
        # Process 2: Drifting / Unstable (mean starts at 20 and shifts to 26)
        c2 = list(np.random.normal(20.0, 1.0, 25)) + list(np.random.normal(26.0, 1.0, 25))
        # Process 3: Stable but high variance / low capability
        c3 = list(np.random.normal(100.0, 8.0, 50))

        self.worksheet = Worksheet("ScreeningData", [
            Column("Proc_Stable", values=c1),
            Column("Proc_Drifting", values=c2),
            Column("Proc_HighVar", values=c3),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.worksheet

    def test_screening_engine_calculations(self):
        cols_data = [
            {"name": "Proc_Stable", "index": 0, "values": self.worksheet.columns[0].values},
            {"name": "Proc_Drifting", "index": 1, "values": self.worksheet.columns[1].values},
            {"name": "Proc_HighVar", "index": 2, "values": self.worksheet.columns[2].values},
        ]
        specs = {
            "Proc_Stable": {"lsl": 45.0, "target": 50.0, "usl": 55.0},
            "Proc_Drifting": {"lsl": 15.0, "target": 20.0, "usl": 25.0},
            "Proc_HighVar": {"lsl": 90.0, "target": 100.0, "usl": 110.0},
        }

        res = calculate_process_screening(cols_data, specs_dict=specs)
        self.assertEqual(res["total_screened"], 3)
        self.assertIn("processes", res)

        proc_map = {p["process"]: p for p in res["processes"]}

        # Proc_Stable should have low Stability Index near 1.0 and high Ppk
        p1 = proc_map["Proc_Stable"]
        self.assertLess(p1["stability_index"], 1.30)
        self.assertGreaterEqual(p1["ppk"], 1.33)
        self.assertEqual(p1["status_label"], "Capable & Stable")

        # Proc_Drifting should have high Stability Index (due to mean shift) and alarms
        p2 = proc_map["Proc_Drifting"]
        self.assertGreater(p2["stability_index"], 1.40)
        self.assertGreater(p2["alarms_count"], 0)

    def test_presenter_integration_and_recipe(self):
        entry = self.presenter.process_screening(
            variable_indices=[0, 1, 2],
            subgroup_size=1,
        )
        self.assertIn("result", entry)
        res = entry["result"]
        self.assertEqual(res["analysis"], "process_screening")
        self.assertEqual(entry["recipe"]["action"], "process_screening")

        # Report checks
        text = format_process_screening_report(res)
        self.assertIn("Process Screening Dashboard", text)
        self.assertIn("Proc_Stable", text)
        self.assertIn("Proc_Drifting", text)

        tables = get_process_screening_tables(res)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["title"], "Process Screening Summary Scorecard")
        self.assertEqual(tables[1]["title"], "Process Screening Metrics Table")

    def test_screening_widget_instantiation(self):
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        entry = self.presenter.process_screening(variable_indices=[0, 1, 2])
        from statcraft.process_screening_chart import ProcessScreeningWidget
        widget = ProcessScreeningWidget(entry)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.table.rowCount(), 3)


if __name__ == "__main__":
    unittest.main()
