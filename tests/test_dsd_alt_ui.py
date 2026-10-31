"""UI and widget tests for Definitive Screening Design and Accelerated Life Testing in offscreen mode."""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from statcraft.alt_chart import ALTLifeVsStressWidget
from statcraft.alt_dialogs import AcceleratedLifeTestingDialog
from statcraft.alt_engine import fit_accelerated_life_test
from statcraft.alt_report import get_alt_structured_tables
from statcraft.app import Presenter
from statcraft.dsd import create_definitive_screening_design
from statcraft.dsd_analysis import analyze_definitive_screening_design
from statcraft.dsd_chart import DSDParetoEffectsWidget
from statcraft.dsd_dialogs import (
    AnalyzeDefinitiveScreeningDesignDialog,
    CreateDefinitiveScreeningDesignDialog,
)
from statcraft.model import Column, Worksheet

app = QApplication.instance() or QApplication([])


class TestDSDAltUI(unittest.TestCase):
    def setUp(self):
        self.presenter = Presenter()

    def test_create_dsd_dialog_instantiation(self):
        dlg = CreateDefinitiveScreeningDesignDialog()
        self.assertEqual(dlg.factor_count.value(), 6)
        dlg.factor_count.setValue(8)
        self.assertEqual(dlg.factor_table.rowCount(), 8)
        dlg._update_run_summary()
        self.assertIn("8 factors", dlg.summary_label.text())

    def test_analyze_dsd_dialog_instantiation(self):
        factors = [{"name": f"X{i}", "low": 0, "high": 10} for i in range(4)]
        ws = create_definitive_screening_design(factors, randomize=False)
        ws.columns.append(Column("Resp", "number", [float(i * 2) for i in range(ws.row_count)]))
        dlg = AnalyzeDefinitiveScreeningDesignDialog(ws)
        self.assertIsNotNone(dlg)

    def test_alt_dialog_instantiation(self):
        ws = Worksheet(name="ALT_Data", columns=[
            Column("Hours", "number", [100.0, 200.0, 300.0, 400.0, 500.0, 600.0]),
            Column("Temp", "number", [80.0, 80.0, 80.0, 100.0, 100.0, 100.0]),
            Column("Censor", "number", [1.0, 1.0, 0.0, 1.0, 1.0, 0.0]),
        ])
        dlg = AcceleratedLifeTestingDialog(ws)
        self.assertIsNotNone(dlg)

    def test_dsd_pareto_widget_render(self):
        factors = [{"name": f"X{i}", "low": 0, "high": 10} for i in range(4)]
        ws = create_definitive_screening_design(factors, randomize=False)
        y = [float(i + (i % 2) * 5) for i in range(ws.row_count)]
        ws.columns.append(Column("Resp", "number", y))
        res = analyze_definitive_screening_design(ws, response_index=len(ws.columns) - 1)
        entry = {"result": res, "title": "DSD Pareto"}
        widget = DSDParetoEffectsWidget(entry)
        widget.resize(700, 450)
        widget.show()
        from PySide6.QtGui import QPixmap
        pm = QPixmap(700, 450)
        widget.render(pm)
        self.assertTrue(len(widget._bar_rects) >= 1)

    def test_alt_chart_widget_render(self):
        times = [100.0, 150.0, 200.0, 80.0, 110.0, 130.0, 50.0, 70.0, 90.0]
        events = [1, 1, 0, 1, 1, 0, 1, 1, 1]
        stresses = [60.0, 60.0, 60.0, 80.0, 80.0, 80.0, 100.0, 100.0, 100.0]
        res = fit_accelerated_life_test(times, events, stresses, model="arrhenius", use_stress=25.0)
        res["time_name"] = "Hours"
        res["stress_name"] = "Temp"
        res["tables"] = get_alt_structured_tables(res)
        entry = {"result": res, "title": "ALT Life vs Stress"}
        widget = ALTLifeVsStressWidget(entry)
        widget.resize(850, 550)
        widget.show()
        from PySide6.QtGui import QPixmap
        pm = QPixmap(850, 550)
        widget.render(pm)
        self.assertEqual(len(widget._data_points_px), 9)


if __name__ == "__main__":
    unittest.main()
