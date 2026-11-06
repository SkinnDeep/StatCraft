import unittest
from PySide6.QtWidgets import QApplication

from statcraft.modern_app import ModernWindow
from statcraft.connect import ConnectedAnalysis


class TestConnectTour(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_load_connect_sample_project(self):
        window = ModernWindow()
        window.closeEvent = lambda event: event.accept()

        window.load_connect_sample_project()

        # Should have 3 worksheets loaded
        sheets = window.presenter.worksheets
        sheet_names = [s.name for s in sheets]
        self.assertIn("DOE_Battery", sheet_names)
        self.assertIn("GageRR_Gasket", sheet_names)
        self.assertIn("SPC_PistonRings", sheet_names)

        # Should have history entries for each procedure with connected analysis
        history = window.presenter.history
        self.assertGreaterEqual(len(history), 3)

        # Verify that connected analyses exist for the loaded results
        conn_types = [
            e.get("connected_analysis", {}).get("analysis_type")
            for e in history if e.get("connected_analysis")
        ]
        self.assertTrue(any(t in ("twoway_anova", "general_linear_model", "multiple_regression") for t in conn_types))
        self.assertIn("gage_rr", conn_types)
        self.assertIn("xbar_r", conn_types)

        window.close()


if __name__ == "__main__":
    unittest.main()
