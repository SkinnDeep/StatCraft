import unittest

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.connect import create_connected_analysis_from_entry


class TestUniversalRFallback(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet("GenericStudy", [
            Column("Values", "number", [12.0, 15.0, 14.0, 19.0, 22.0, 18.0, 25.0]),
            Column("Group", "text", ["A", "A", "A", "B", "B", "B", "B"]),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_run_chart_produces_connected_analysis_and_r_script(self):
        # Run a niche/exploratory procedure: run chart
        self.presenter.run_chart(0)
        entry = self.presenter.history[-1]

        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn, "Even non-flagship procedures must produce a ConnectedAnalysis")
        self.assertIsNotNone(conn.r_script)
        self.assertGreater(len(conn.r_script), 50)
        self.assertIn('df[["Values"]]', conn.r_script)
        self.assertIn("plot(", conn.r_script)

    def test_two_variances_produces_connected_analysis_and_r_script(self):
        # Run two variances test
        self.presenter.two_variances({"mode": 0, "samples_col": 0, "subscripts_col": 1})
        entry = self.presenter.history[-1]

        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn)
        self.assertIn("var.test", conn.r_script)
        self.assertIn("Values", conn.r_script)
        self.assertIn("Group", conn.r_script)


if __name__ == "__main__":
    unittest.main()
