"""Unit tests for What-If Spec & Tolerance Simulation in Capability Analysis."""
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.capability_chart import CapabilityPlotWidget, CapabilityWhatIfStrip, CapabilityContainerWidget

_app = QApplication.instance() or QApplication([])


class TestWhatIfCapability(unittest.TestCase):
    def setUp(self):
        self.entry = {
            "title": "Process Capability Analysis for Piston Diameter",
            "recipe": {"action": "capability_analysis"},
            "result": {
                "analysis": "capability",
                "variable_name": "Diameter",
                "lsl": 74.0,
                "usl": 76.0,
                "target": 75.0,
                "mean": 75.0,
                "stdev_within": 0.5,
                "stdev_overall": 0.5,
                "observations": [74.5, 75.0, 75.2, 74.8, 75.5, 74.9],
                "cp": 0.667,
                "cpk": 0.667
            }
        }

    def test_plot_simulation_updates(self):
        plot = CapabilityPlotWidget(self.entry)
        self.assertFalse(plot.is_simulation_active)

        # 1. Update LSL and USL
        plot.set_simulation(override_lsl=73.0, override_usl=77.0, drift_pct=0.0)
        self.assertTrue(plot.is_simulation_active)
        self.assertEqual(plot.override_lsl, 73.0)
        self.assertEqual(plot.override_usl, 77.0)

        # 2. Reset simulation
        plot.reset_simulation()
        self.assertFalse(plot.is_simulation_active)
        self.assertIsNone(plot.override_lsl)

    def test_container_and_strip_integration(self):
        container = CapabilityContainerWidget(self.entry)
        self.assertIsNotNone(container.plot)
        self.assertIsNotNone(container.strip)

        # Adjust spinboxes in strip
        container.strip.lsl_spin.setValue(72.0)
        container.strip.usl_spin.setValue(78.0)
        container.strip.drift_spin.setValue(10.0)

        # Triggers simulation update in plot
        self.assertTrue(container.plot.is_simulation_active)
        self.assertEqual(container.plot.override_lsl, 72.0)
        self.assertEqual(container.plot.override_usl, 78.0)
        self.assertEqual(container.plot.drift_pct, 10.0)


if __name__ == "__main__":
    unittest.main()
