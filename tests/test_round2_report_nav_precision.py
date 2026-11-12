import os
import sys
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QTableWidget

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from statcraft.modern_app import ModernWindow


class TestRound2ReportNavAndPrecision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = ModernWindow(None)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        cb = QApplication.clipboard()
        if cb is not None:
            cb.clear()
            self.app.processEvents()
        self.window.presenter.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_navigator_filter_and_tab_corner_chrome(self):
        self.assertTrue(hasattr(self.window, "navigator_filter"))
        p = self.window.presenter
        p.history.append({"origin": "statcraft", "title": "Descriptive Statistics: Yield", "worksheet_name": p.worksheet.name, "time": "t1", "result": {"analysis": "summary", "text": "N=10"}})
        p.history.append({"origin": "statcraft", "title": "Simple Regression: Y versus Temp", "worksheet_name": p.worksheet.name, "time": "t2", "result": {"analysis": "regression", "text": "R-Sq=90%"}})
        self.window.refresh()
        self.app.processEvents()

        self.window.navigator_filter.setText("Regression")
        self.app.processEvents()

        top = self.window.navigator.topLevelItem(0)
        self.assertFalse(top.isHidden())
        child_titles = {top.child(i).text(0): top.child(i).isHidden() for i in range(top.childCount())}
        self.assertTrue(any("Descriptive" in k and hidden for k, hidden in child_titles.items()))
        self.assertTrue(any("Regression" in k and not hidden for k, hidden in child_titles.items()))

        self.window.navigator_filter.clear()
        self.app.processEvents()
        self.assertFalse(any(top.child(i).isHidden() for i in range(top.childCount())))

        # tab_corner_widget fixed compact chrome height
        self.assertLessEqual(self.window.tab_corner_widget.maximumHeight(), 28)
        self.assertGreaterEqual(self.window.tab_corner_widget.height(), 20)

    def test_report_find_across_labels_and_tables(self):
        entry = {
            "title": "Regression Report",
            "worksheet_name": "Worksheet 1",
            "time": "now",
            "origin": "statcraft",
            "result": {
                "analysis": "regression",
                "summary": "Model Summary for Yield",
                "coefficients": [
                    {"name": "Intercept", "estimate": 12.3456, "p_value": 0.0001},
                    {"name": "Temp", "estimate": 0.5678, "p_value": 0.0123},
                ],
                "graphs": [],
            },
        }
        self.window.presenter.history.append(entry)
        self.window.show_result(entry)
        self.app.processEvents()

        scroll = self.window.result_tabs.widget(0)
        self.assertTrue(isinstance(scroll, QScrollArea) or hasattr(scroll, "content"))
        self.assertTrue(hasattr(self.window, "_find_in_report_widget"))

        res1 = self.window._find_in_report_widget(scroll, "Intercept")
        self.assertTrue(res1["found"])
        self.assertGreaterEqual(res1["total"], 1)

        # Cycling forward should still succeed and report wrap or index progression
        res2 = self.window._find_in_report_widget(scroll, "0.5678")
        self.assertTrue(res2["found"])

        miss = self.window._find_in_report_widget(scroll, "NO_SUCH_TOKEN_XYZ")
        self.assertFalse(miss["found"])
        self.assertEqual(miss["total"], 0)

    def test_result_table_decimal_places_quick_toggle_and_clipboard(self):
        table = self.window._result_table(
            ["Term", "Coef", "P-Value"],
            [["Intercept", 12.345678, 0.000123], ["Temp", 0.5, 0.25]],
        )
        self.assertIsInstance(table, QTableWidget)
        coef_item = table.item(0, 1)
        self.assertIsNotNone(coef_item.data(Qt.ItemDataRole.UserRole))
        self.assertAlmostEqual(float(coef_item.data(Qt.ItemDataRole.UserRole)), 12.345678, places=6)
        default_text = coef_item.text()

        self.window.set_result_table_decimals(table, 2)
        self.assertEqual(table.item(0, 1).text(), "12.35")
        self.assertEqual(table.item(0, 2).text(), "0.00")
        self.assertEqual(table.item(0, 0).text(), "Intercept")

        self.window.step_result_table_decimals(table, 2)
        self.assertEqual(table.item(0, 1).text(), "12.3457")
        self.assertEqual(table.item(0, 2).text(), "0.0001")

        # Copying must export the updated formatted text rather than stale raw display
        self.window._copy_result_table(table, ["Term", "Coef", "P-Value"], delim="\t")
        clip_text = QApplication.clipboard().text()
        self.assertIn("12.3457", clip_text)
        self.assertIn("0.0001", clip_text)

        self.window.set_result_table_decimals(table, None)
        self.assertEqual(table.item(0, 1).text(), default_text)


if __name__ == "__main__":
    unittest.main()
