"""Tests for JMP Auto-Conversion into Minitab Projects and Universal R Translation."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.r_universal_translator import translate_entry_to_r, generate_dataframe_r_code


class TestJmpConversionAndUniversalR(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_jmp_file_auto_conversion_to_minitab_project(self):
        """Verify loading a JMP (.jsl/.jmp) table auto-converts into a native Minitab project."""
        jsl_content = """
        New Table( "JMP Silicon Batch",
            Add Rows( 4 ),
            New Column( "Batch", Character, Set Values( ["B1", "B2", "B3", "B4"] ) ),
            New Column( "Yield", Numeric, Set Values( [88.5, 92.1, 95.0, 89.4] ) ),
            New Column( "Temp", Numeric, Set Values( [350.0, 360.0, 355.0, 358.0] ) )
        );
        """
        jsl_path = Path(self.tmp_dir.name) / "silicon_batch.jsl"
        jsl_path.write_text(jsl_content, encoding="utf-8")

        p = Presenter()
        notices = p.load(jsl_path)

        # 1. Worksheet and Project status
        self.assertIsNotNone(p.worksheet)
        self.assertEqual(p.worksheet.name, "JMP Silicon Batch")
        self.assertEqual(len(p.worksheet.columns), 3)

        # 2. Native Project is instantiated with StatCraft ownership
        self.assertIsNotNone(p.native_project)
        self.assertTrue(getattr(p.native_project, "statcraft_owned", False))
        self.assertEqual(len(p.worksheets), 1)

        # 3. Notice is clear and explicit
        self.assertTrue(any("JMP data table auto-converted to Minitab project" in n for n in notices))

        # 4. Multi-worksheet operations work on the converted project
        ws2 = p.add_worksheet("Second Worksheet")
        self.assertEqual(len(p.worksheets), 2)

        # 5. Native MPX saving works directly on auto-converted project
        mpx_out = Path(self.tmp_dir.name) / "converted_jmp.mpx"
        p.save(mpx_out)
        self.assertTrue(mpx_out.exists())
        self.assertGreater(mpx_out.stat().st_size, 0)

        # 6. Re-opening saved MPX restores all worksheets cleanly
        p2 = Presenter()
        p2.load(mpx_out)
        self.assertEqual(len(p2.worksheets), 2)
        self.assertEqual(p2.worksheets[0].name, "JMP Silicon Batch")
        self.assertEqual(p2.worksheets[1].name, "Second Worksheet")

    def test_universal_r_translator_deming_orthogonal(self):
        ws = Worksheet("DemingData", [
            Column("RefMethod", "number", [10.2, 12.5, 14.8, 18.0, 21.2]),
            Column("NewMethod", "number", [10.5, 12.8, 14.9, 18.2, 21.0]),
        ])
        entry = {
            "title": "Orthogonal Regression (Deming)",
            "recipe": {
                "action": "orthogonal_regression",
                "parameters": {"response_index": 1, "predictor_index": 0, "error_variance_ratio": 1.0}
            },
            "result": {
                "analysis": "orthogonal_regression",
                "response_name": "NewMethod",
                "predictor_name": "RefMethod",
                "intercept": 0.25,
                "slope": 0.99
            }
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("Deming Fit", base_r)
        self.assertIn("s_xx <- var(x)", base_r)
        self.assertIn("ggplot", tidy_r)
        self.assertIn("geom_abline", tidy_r)
        self.assertEqual(title, "Orthogonal Regression (Deming)")

    def test_universal_r_translator_probit(self):
        ws = Worksheet("Bioassay", [
            Column("Dose", "number", [1.0, 2.0, 3.0, 4.0]),
            Column("Responded", "number", [2, 8, 15, 19]),
            Column("Total", "number", [20, 20, 20, 20]),
        ])
        entry = {
            "title": "Probit Analysis",
            "recipe": {
                "action": "probit_analysis",
                "parameters": {"response_index": 1, "trials_index": 2, "dose_index": 0, "distribution": "probit"}
            },
            "result": {"analysis": "probit_analysis"}
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("glm(cbind(", base_r)
        self.assertIn("family = binomial(link = 'probit')", base_r)
        self.assertIn("ggplot(df, aes", tidy_r)
        self.assertIn("stat_smooth", tidy_r)

    def test_universal_r_translator_factor_analysis(self):
        ws = Worksheet("Survey", [
            Column("Q1", "number", [4, 5, 2, 1, 5]),
            Column("Q2", "number", [5, 4, 1, 2, 4]),
            Column("Q3", "number", [2, 1, 5, 4, 1]),
        ])
        entry = {
            "title": "Factor Analysis",
            "recipe": {
                "action": "factor_analysis",
                "parameters": {"variable_indices": [0, 1, 2], "n_factors": 2}
            },
            "result": {"analysis": "factor_analysis", "n_factors": 2}
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("factanal(", base_r)
        self.assertIn("rotation = 'varimax'", base_r)
        self.assertIn("ggplot(loads_df", tidy_r)

    def test_universal_r_translator_mca(self):
        ws = Worksheet("Demographics", [
            Column("Age", "text", ["Young", "Old", "Young", "Old"]),
            Column("Car", "text", ["Sedan", "SUV", "Sedan", "Truck"]),
        ])
        entry = {
            "title": "Multiple Correspondence Analysis",
            "recipe": {
                "action": "multiple_correspondence",
                "parameters": {"variable_indices": [0, 1]}
            },
            "result": {"analysis": "multiple_correspondence"}
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("MASS::mca", base_r)
        self.assertIn("FactoMineR::MCA", tidy_r)

    def test_universal_r_translator_prob_dist_plot(self):
        ws = Worksheet("Empty", [Column("Empty", "number", [])])
        entry = {
            "title": "Probability Distribution Plot",
            "recipe": {
                "action": "probability_distribution_plot",
                "parameters": {"distribution": "Normal", "parameters": {"mean": 100, "stdev": 15}}
            },
            "result": {
                "analysis": "probability_distribution",
                "distribution": "Normal",
                "c1": 85,
                "c2": 115,
                "total_shaded_prob": 0.6826
            }
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("curve(dnorm", base_r)
        self.assertIn("polygon(", base_r)
        self.assertIn("stat_function(fun = dnorm", tidy_r)

    def test_universal_r_translator_marginal_plot(self):
        ws = Worksheet("MarginalData", [
            Column("Height", "number", [65, 70, 72, 68, 62]),
            Column("Weight", "number", [140, 175, 190, 160, 125]),
        ])
        entry = {
            "title": "Marginal Plot",
            "recipe": {
                "action": "marginal_plot",
                "parameters": {"y_index": 1, "x_index": 0}
            },
            "result": {"analysis": "marginal_plot", "y_name": "Weight", "x_name": "Height"}
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("layout(matrix", base_r)
        self.assertIn("hist(x", base_r)
        self.assertIn("ggExtra::ggMarginal", tidy_r)

    def test_universal_r_translator_ecdf_plot(self):
        ws = Worksheet("ECDFData", [
            Column("Lifespan", "number", [120, 150, 160, 180, 210]),
        ])
        entry = {
            "title": "Empirical CDF Plot",
            "recipe": {
                "action": "ecdf_plot",
                "parameters": {"variable_index": 0}
            },
            "result": {"analysis": "ecdf_plot", "variable_name": "Lifespan"}
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("plot(ecdf(x)", base_r)
        self.assertNotIn(" + ", base_r)  # ensures paste0 was used
        self.assertIn("stat_ecdf", tidy_r)

    def test_universal_r_translator_fallback_on_any_output(self):
        """Universal fallback works seamlessly for ANY unrecognized analysis without error."""
        ws = Worksheet("CustomData", [
            Column("FeatureA", "number", [1.2, 2.3, 3.4, 4.5]),
            Column("FeatureB", "number", [10, 20, 30, 40]),
        ])
        entry = {
            "title": "Custom Neural Architecture Output",
            "recipe": {
                "action": "custom_black_box_model",
                "parameters": {"param_foo": 42}
            },
            "result": {"analysis": "custom_black_box_model"}
        }
        base_r, tidy_r, title = translate_entry_to_r(entry, ws)
        self.assertIn("StatCraft Procedure: Custom Neural Architecture Output", base_r)
        self.assertIn("summary(sub_df)", base_r)
        self.assertIn("cor(sub_df", base_r)
        self.assertIn("ggplot", tidy_r)
        self.assertEqual(title, "Custom Neural Architecture Output")

    def test_universal_r_translator_one_sample_and_paired_t(self):
        ws = Worksheet("TestData", [
            Column("Before", "number", [10, 12, 14, 15]),
            Column("After", "number", [12, 13, 16, 17]),
        ])
        entry_1t = {
            "title": "1-Sample T",
            "recipe": {"action": "one_sample_t", "parameters": {"index": 0, "mu": 12.0}},
            "result": {"analysis": "one_sample_t"}
        }
        base_r, tidy_r, _ = translate_entry_to_r(entry_1t, ws)
        self.assertIn("t.test(df[[\"Before\"]], mu = 12.0)", base_r)
        self.assertIn("geom_hline(yintercept = 12.0", tidy_r)

        entry_pt = {
            "title": "Paired T",
            "recipe": {"action": "paired_t", "parameters": {"first_index": 0, "second_index": 1}},
            "result": {"analysis": "paired_t"}
        }
        base_r2, tidy_r2, _ = translate_entry_to_r(entry_pt, ws)
        self.assertIn("t.test(df[[\"Before\"]], df[[\"After\"]], paired = TRUE)", base_r2)
        self.assertIn("Diff", tidy_r2)

    def test_universal_r_translator_twoway_anova_and_logistic(self):
        ws = Worksheet("DOEData", [
            Column("Response", "number", [50, 60, 55, 65, 70, 75]),
            Column("FactorA", "text", ["Lo", "Lo", "Hi", "Hi", "Lo", "Hi"]),
            Column("FactorB", "text", ["M1", "M2", "M1", "M2", "M1", "M2"]),
        ])
        entry_aov = {
            "title": "Two-Way ANOVA",
            "recipe": {"action": "twoway_anova", "parameters": {"response_index": 0, "row_factor_index": 1, "col_factor_index": 2}},
            "result": {"analysis": "twoway_anova"}
        }
        base_r, tidy_r, _ = translate_entry_to_r(entry_aov, ws)
        self.assertIn("aov(", base_r)
        self.assertIn("interaction.plot", base_r)
        self.assertIn("stat_summary", tidy_r)

        entry_logit = {
            "title": "Binary Logistic",
            "recipe": {"action": "binary_logistic_regression", "parameters": {"response_index": 1, "predictor_indices": [0]}},
            "result": {"analysis": "binary_logistic_regression"}
        }
        base_r2, tidy_r2, _ = translate_entry_to_r(entry_logit, ws)
        self.assertIn("family = binomial", base_r2)
        self.assertIn("stat_smooth", tidy_r2)

    def test_modern_app_r_script_methods(self):
        """Test ModernWindow R script retrieval and copy methods."""
        from statcraft.modern_app import ModernWindow
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])

        app = ModernWindow()
        ws = Worksheet("TestWS", [Column("Metric", "number", [1.0, 2.0, 3.0, 4.0])])
        app.presenter.worksheet = ws

        entry = {
            "title": "Descriptive Statistics",
            "recipe": {"action": "descriptive_statistics", "parameters": {"indices": [0]}},
            "result": {"analysis": "descriptive_statistics"}
        }
        app.presenter.history = [entry]

        # 1. Base R retrieval
        base_r, title = app._get_entry_r_script(entry)
        self.assertIn("Descriptive Statistics", base_r)
        self.assertIn("df <- data.frame", base_r)

        # 2. Tidyverse retrieval
        tidy_r, title2 = app._get_entry_tidyverse_script(entry)
        self.assertIn("pivot_longer", tidy_r)
        self.assertIn("library(tidyverse)", tidy_r)

        # 3. Clipboard copy methods run without exception
        app.copy_connected_r_script(entry)
        app.copy_entry_r_script(entry)
        app.copy_active_r_script()
        app.copy_active_base_r_script()


if __name__ == "__main__":
    unittest.main()
