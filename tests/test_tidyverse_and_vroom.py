import unittest
import os
import sys

# Configure headless PySide6
os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
except ImportError:
    app = None

from statcraft.model import Worksheet, Column
from statcraft.connect import ConnectedAnalysis, create_connected_analysis_from_entry, create_connected_histogram
from statcraft.connect_r import (
    generate_vroom_data_import_code,
    generate_r_tidyverse_script,
    generate_dataframe_init_code,
    generate_r_histogram_script,
    build_self_contained_r_script,
)
from statcraft.connect_hub import ViewRCodeDialog, StatCraftAnalysisBar
from statcraft.modern_app import ModernWindow


class TestTidyverseAndVroom(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(name="QualityData")
        self.ws.columns.append(Column("Diameter", values=[10.1, 10.2, 9.9, 10.0, 10.3, 10.1, 9.8, 10.4]))
        self.ws.columns.append(Column("Pressure", values=[50.5, 51.0, 49.8, 50.2, 51.5, 50.8, 49.5, 52.0]))
        self.ws.columns.append(Column("Machine", values=["M1", "M1", "M1", "M1", "M2", "M2", "M2", "M2"], kind="text"))

    def test_vroom_ingestion_generator(self):
        code = generate_vroom_data_import_code(self.ws)
        self.assertIn("vroom::vroom", code)
        self.assertIn("readxl::read_excel", code)
        self.assertIn("tibble::tibble", code)
        self.assertIn('"Diameter" = c(10.1, 10.2', code)
        self.assertIn('"Machine" = c("M1", "M1"', code)

    def test_dataframe_definition_check_names(self):
        code = generate_dataframe_init_code(self.ws)
        self.assertIn("check.names = FALSE", code)
        self.assertIn('cat("Active worksheet loaded into R', code)
        self.assertIn("hist(x_clean", code)

    def test_histogram_connected_analysis(self):
        entry = {
            "title": "Histogram of Diameter with Fit",
            "recipe": {"action": "graph", "parameters": {"method": "histogram", "indices": [0], "bins": 10, "variant": "fit"}},
            "result": {"graph": "histogram"},
        }
        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "histogram")

        # Test Base R script
        base_script = build_self_contained_r_script(conn.r_script, self.ws, conn.title)
        self.assertIn("hist(x_clean", base_script)
        self.assertIn("dnorm", base_script)
        self.assertIn("check.names = FALSE", base_script)

        # Test Tidyverse / ggplot2 script
        tidy_script = generate_r_tidyverse_script(conn, self.ws)
        self.assertIn("geom_histogram", tidy_script)
        self.assertIn("stat_function(", tidy_script)
        self.assertIn("fun = dnorm", tidy_script)

    def test_tidyverse_descriptives(self):
        entry = {
            "title": "Descriptive Statistics",
            "recipe": {"action": "describe_columns", "columns": ["Diameter", "Pressure"]},
            "result": {"summary": {}},
        }
        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn)
        script = generate_r_tidyverse_script(conn, self.ws)

        # Check modern data science packages
        self.assertIn("library(tidyverse)", script)
        self.assertIn("library(ggplot2)", script)
        self.assertIn("library(dplyr)", script)
        self.assertIn("library(tidyr)", script)

        # Check dplyr wrangling
        self.assertIn("pivot_longer", script)
        self.assertIn("summarise(", script)
        self.assertIn("SE_Mean =", script)
        self.assertIn("CoeffVar =", script)
        self.assertIn("IQR =", script)

        # Check publication ggplot2 graphics
        self.assertIn("geom_histogram", script)
        self.assertIn("geom_density", script)
        self.assertIn("geom_boxplot", script)
        self.assertIn("geom_jitter", script)
        self.assertIn("stat_summary(fun = mean", script)

    def test_tidyverse_regression(self):
        entry = {
            "title": "Regression Analysis: Diameter vs Pressure",
            "recipe": {"action": "multiple_regression", "response": "Diameter", "predictors": ["Pressure"]},
            "result": {"r_squared": 0.85},
        }
        conn = create_connected_analysis_from_entry(entry, self.ws)
        script = generate_r_tidyverse_script(conn, self.ws)

        self.assertIn("lm(", script)
        self.assertIn("confint(fit)", script)
        self.assertIn("geom_smooth(method = 'lm'", script)
        self.assertIn("rstandard(fit)", script)

    def test_tidyverse_anova(self):
        entry = {
            "title": "One-Way ANOVA: Diameter by Machine",
            "recipe": {"action": "oneway_anova", "response": "Diameter", "factor": "Machine"},
            "result": {},
        }
        conn = create_connected_analysis_from_entry(entry, self.ws)
        script = generate_r_tidyverse_script(conn, self.ws)

        self.assertIn("aov(", script)
        self.assertIn("TukeyHSD(fit)", script)
        self.assertIn("geom_boxplot", script)

    def test_tidyverse_two_sample_t(self):
        entry = {
            "title": "Two-Sample T-Test: Diameter vs Pressure",
            "recipe": {"action": "two_sample_t", "sample1": "Diameter", "sample2": "Pressure"},
            "result": {},
        }
        conn = create_connected_analysis_from_entry(entry, self.ws)
        script = generate_r_tidyverse_script(conn, self.ws)

        self.assertIn("t.test(", script)
        self.assertIn("geom_boxplot", script)

    def test_view_r_code_dialog_multi_engine_modes(self):
        tidy = "# tidyverse script"
        base = "# base r script"
        vroom = "# vroom script"
        dlg = ViewRCodeDialog(None, r_script=base, title="Test Dialog", tidyverse_script=tidy, vroom_script=vroom)

        # Starts in tidyverse mode by default
        self.assertEqual(dlg.current_mode, "tidyverse")
        self.assertEqual(dlg.code_view.toPlainText(), tidy)

        # Switch to base_r
        dlg.set_mode("base_r")
        self.assertEqual(dlg.current_mode, "base_r")
        self.assertEqual(dlg.code_view.toPlainText(), base)

        # Switch to vroom
        dlg.set_mode("vroom")
        self.assertEqual(dlg.current_mode, "vroom")
        self.assertEqual(dlg.code_view.toPlainText(), vroom)

        dlg.close()
        dlg.deleteLater()

    def test_analysis_bar_r_translator_buttons(self):
        conn_dict = {
            "title": "Descriptive Statistics",
            "r_script": "summary(df)",
            "analysis_type": "descriptive_statistics",
        }
        entry = {"title": "Descriptive Statistics", "recipe": {"action": "describe_columns"}}
        bar = StatCraftAnalysisBar(None, entry, conn_dict)

        self.assertIsNotNone(bar.btn_copy_r)
        self.assertIsNotNone(bar.btn_copy_base)
        self.assertIsNotNone(bar.btn_view_r)
        self.assertIsNotNone(bar.btn_export_r)

        self.assertIn("Copy R Script", bar.btn_copy_r.text())
        self.assertIn("Pure Base R", bar.btn_copy_base.text())
        bar.deleteLater()

    def test_modern_window_export_menus_and_helpers(self):
        win = ModernWindow()
        try:
            # Check helper methods
            tidy_code, tidy_title = win._get_entry_tidyverse_script()
            self.assertTrue(len(tidy_code) > 0)
            self.assertIn("tibble", tidy_code)

            base_code, base_title = win._get_entry_r_script()
            self.assertTrue(len(base_code) > 0)
            self.assertIn("data.frame", base_code)

            vroom_code = win._get_entry_vroom_script()
            self.assertIn("vroom::vroom", vroom_code)
        finally:
            win.close()
            win.deleteLater()
            if app:
                app.processEvents()


if __name__ == "__main__":
    unittest.main()
