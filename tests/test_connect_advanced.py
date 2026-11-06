import unittest

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.connect import create_connected_analysis_from_entry


class TestConnectAdvanced(unittest.TestCase):
    def test_twoway_anova_connected_contract_and_r_script(self):
        ws = Worksheet("TwoWayStudy", [
            Column("Strength", "number", [19.8, 20.4, 22.1, 23.0, 18.5, 19.2, 21.0, 21.8]),
            Column("Operator", "text", ["Op1", "Op1", "Op2", "Op2", "Op1", "Op1", "Op2", "Op2"]),
            Column("Machine", "text", ["M1", "M2", "M1", "M2", "M1", "M2", "M1", "M2"]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.twoway_anova(0, 1, 2, fit_interaction=True)
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "twoway_anova")
        self.assertIn("aov(", conn.r_script)
        self.assertIn("Operator", conn.r_script)
        self.assertIn("Machine", conn.r_script)
        self.assertIn("interaction.plot", conn.r_script)

    def test_binary_logistic_connected_contract_and_r_script(self):
        ws = Worksheet("LogisticStudy", [
            Column("Pass", "text", ["Y", "N", "Y", "N", "Y", "Y", "N", "Y", "N", "N", "Y", "N"]),
            Column("Temp", "number", [10.0, 12.0, 14.0, 11.0, 15.0, 13.0, 10.0, 16.0, 12.0, 9.0, 14.0, 11.0]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.fit_binary_logistic(0, [1], [], event="Y")
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "binary_logistic")
        self.assertIn("glm(", conn.r_script)
        self.assertIn("family = binomial", conn.r_script)
        self.assertIn("exp(coef(fit))", conn.r_script)

    def test_normal_capability_connected_contract_and_r_script(self):
        ws = Worksheet("CapStudy", [
            Column("Diameter", "number", [10.1, 10.2, 9.9, 10.0, 10.3, 9.8, 10.2, 10.1, 9.9, 10.0]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.normal_capability(0, lsl=9.5, usl=10.5, target=10.0)
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "normal_capability")
        self.assertIn("Cp", conn.r_script)
        self.assertIn("Cpk", conn.r_script)
        self.assertIn("dnorm", conn.r_script)

    def test_imr_chart_connected_contract_and_r_script(self):
        ws = Worksheet("SPCStudy", [
            Column("Measurement", "number", [25.1, 24.8, 25.5, 25.0, 24.9, 25.3, 25.2, 24.7]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.individuals_moving_range(0)
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "individuals_moving_range")
        self.assertIn("Moving Range", conn.r_script)
        self.assertIn("UCL", conn.r_script)
        self.assertIn("LCL", conn.r_script)


if __name__ == "__main__":
    unittest.main()
