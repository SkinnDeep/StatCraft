import os
import tempfile
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.modern_app import ModernWindow


class TestModernMinitabWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_complete_minitab_quality_workflow(self):
        window = ModernWindow()
        window.closeEvent = lambda event: event.accept()

        # 1. Load multi-worksheet benchmark sample project
        window.load_connect_sample_project()
        self.assertEqual(len(window.presenter.worksheets), 3)

        # 2. Select Gage R&R result
        history = window.presenter.history
        self.assertGreaterEqual(len(history), 3)
        gage_entry = next(e for e in history if e.get("recipe", {}).get("action") == "gage_rr")
        window.show_result(gage_entry)

        # 3. Verify R Script is copyable
        conn = gage_entry.get("connected_analysis")
        self.assertIsNotNone(conn)
        r_script = conn.get("r_script")
        self.assertIn("aov(", r_script)

        # 4. Append to ReportPad
        window.append_connected_report_to_report_pad(gage_entry)
        report_text = window._workspace.pad.toPlainText()
        self.assertGreater(len(report_text), 100)
        self.assertIn("Gage", report_text)

        # 5. Save and reload project cleanly
        with tempfile.NamedTemporaryFile(suffix=".mpx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            window.presenter.save(tmp_path)
            self.assertTrue(os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        window.close()


if __name__ == "__main__":
    unittest.main()
