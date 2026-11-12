"""Tests for StatCraft workflow micro-innovations."""
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit

from statcraft.micro_innovations import (
    BackgroundComputeManager,
    ColumnFilterPopover,
    CommandLineAssistant,
    ComputeProgressToast,
    ConditionalFormatCache,
    FormulaBarWidget,
    MRUColumnTracker,
    PasteToastBar,
    PinnedProceduresManager,
    SheetVersionTracker,
    StaleOutputBanner,
    build_chart_quick_bar,
    build_executive_pptx,
    format_selection_summary,
)
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.app import Presenter


def _app():
    return QApplication.instance() or QApplication([])


class MicroInnovationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _app()

    def test_conditional_format_cache_memoizes_and_invalidates(self):
        col = Column(
            name="Score",
            kind="number",
            values=[10.0, 95.0, 50.0],
            metadata={"conditional_rules": [{"type": "greater_than", "param1": 80, "color": "#fecaca"}]},
        )
        cache = ConditionalFormatCache()
        first = cache.get_highlights(col, 3)
        second = cache.get_highlights(col, 3)
        self.assertIs(first, second)
        self.assertIn("1", first)
        col.values[0] = 99.0
        third = cache.get_highlights(col, 3)
        self.assertIsNot(first, third)
        self.assertIn("0", third)

    def test_command_line_assistant_tokens_and_hints(self):
        ws = Worksheet(name="Sheet1", columns=[Column(name="Temp", kind="number", values=[1.0, 2.0])])
        ed = QPlainTextEdit()
        hint = QLabel()
        assistant = CommandLineAssistant(ed, hint, lambda: ws)
        tokens = assistant.refresh_tokens()
        self.assertIn("REGRESS", tokens)
        self.assertIn("C1", tokens)
        self.assertIn("'Temp'", tokens)
        ed.setPlainText("REGRESS C1")
        self.assertIn("Linear regression", hint.text())

    def test_mru_columns_and_pinned_procedures(self):
        mru = MRUColumnTracker(max_items=3)
        mru.record(["C1: \"A\"", "C2: \"B\"", "C1: \"A\""])
        self.assertEqual(mru.items(2), ["C1: \"A\"", "C2: \"B\""])

        pins = PinnedProceduresManager()
        called = []
        pins.pin("Regression", lambda: called.append("ok"))
        self.assertEqual(len(pins.list_items()), 1)
        pins.list_items()[0][1]()
        self.assertEqual(called, ["ok"])
        pins.unpin("Regression")
        self.assertEqual(pins.list_items(), [])

    def test_sheet_version_tracker_and_stale_banner(self):
        ws = Worksheet(name="S1", columns=[Column(name="X", kind="number", values=[1.0])])
        tracker = SheetVersionTracker()
        v0 = tracker.version(ws)
        v1 = tracker.bump(ws)
        self.assertGreater(v1, v0)
        banner = StaleOutputBanner()
        clicked = []
        banner.rerunRequested.connect(lambda: clicked.append(True))
        banner.rerun_btn.click()
        self.assertEqual(clicked, [True])

    def test_background_compute_manager(self):
        toast = ComputeProgressToast()
        mgr = BackgroundComputeManager(toast)
        out = []
        mgr.submit("Test Job", lambda: 42, lambda res: out.append(res))
        mgr.pool.waitForDone(3000)
        self.app.processEvents()
        self.assertEqual(out, [42])
        self.assertTrue(toast.isHidden())

    def test_formula_bar_and_selection_summary(self):
        bar = FormulaBarWidget()
        bar.sync(0, 2, "Yield", "88.5", formula=None)
        self.assertEqual(bar.addr_label.text(), "C1 [R3]")
        self.assertEqual(bar.input.text(), "88.5")
        bar.sync(1, 0, "TempF", "68", formula="C1 * 1.8 + 32")
        self.assertEqual(bar.input.text(), "= C1 * 1.8 + 32")

        summary = format_selection_summary([10.0, 20.0, 30.0], 3, missing_count=1)
        self.assertIn("Count: 3", summary)
        self.assertIn("Missing: 1", summary)
        self.assertIn("Mean: 20", summary)
        self.assertIn("SD: 10", summary)
        self.assertIn("Min: 10", summary)
        self.assertIn("Max: 30", summary)

    def test_paste_toast_bar(self):
        toast = PasteToastBar()
        toast.show_paste(5, 3, allow_header_promote=True)
        self.assertFalse(toast.isHidden())
        self.assertIn("5 rows", toast.info_label.text())
        self.assertIn("3 cols", toast.info_label.text())

    def test_column_filter_popover(self):
        col = Column(name="Group", kind="text", values=["A", "B", "A"])
        pop = ColumnFilterPopover(col, 0)
        self.assertEqual(pop.list_widget.count(), 2)
        pop._finish("sort_asc")
        self.assertEqual(pop.chosen_action, "sort_asc")

    def test_executive_slide_deck_export(self):
        entries = [
            {
                "title": "Descriptive Statistics: Yield",
                "result": {
                    "text": "Mean = 82.4\nSD = 5.1",
                    "tables": [{"headers": ["Variable", "Mean", "StDev"], "rows": [["Yield", "82.4", "5.1"]]}],
                    "graphs": [{"title": "Yield Trend", "series": [{"name": "Yield", "x": [1, 2, 3], "y": [80, 82, 85]}]}],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = build_executive_pptx(entries, os.path.join(tmp, "deck.pptx"))
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 5000)

    def test_main_window_wires_micro_innovations(self):
        presenter = Presenter()
        win = ModernWindow(presenter=presenter)
        try:
            self.assertIsNotNone(win.formula_bar)
            self.assertIsNotNone(win.paste_toast)
            self.assertIsNotNone(win.compute_manager)
            self.assertIsNotNone(win._cf_cache)
            self.assertIsNotNone(win._sheet_versions)
            self.assertIsNotNone(win._pinned_procedures)
            self.assertIsNotNone(win._cmd_assistant)
            self.assertIsNotNone(win.pinned_btn)
            self.assertIsNotNone(win.filter_shortcut)
            # Verify QTableWidgetItem reuse across refresh() calls (zero-churn fast path)
            win.refresh()
            item_before = win.table.item(0, 0)
            hdr_before = win.column_names.item(0, 0)
            win.refresh()
            self.assertIs(win.table.item(0, 0), item_before)
            self.assertIs(win.column_names.item(0, 0), hdr_before)
            # Test chart quick bar construction
            from PySide6.QtWidgets import QWidget
            class _DummyFrame(QWidget):
                def __init__(self):
                    super().__init__()
                    self.export_hidden = []
            class _DummyChart(QWidget):
                pass
            dummy_frame = _DummyFrame()
            dummy_chart = _DummyChart()
            qbar = build_chart_quick_bar(dummy_frame, dummy_chart, {"title": "Fitted Line Plot", "result": {"graphs": [{}]}}, win)
            self.assertEqual(qbar.objectName(), "chartQuickBar")
        finally:
            win.close()
            win.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
