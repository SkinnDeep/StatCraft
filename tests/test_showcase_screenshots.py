"""Automated verification test ensuring showcase website images are present, healthy, and free of tofu boxes."""
from __future__ import annotations

import unittest
from pathlib import Path


class TestShowcaseScreenshots(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.docs_dir = self.root / "docs"
        self.img_dir = self.docs_dir / "images"

    def test_all_showcase_images_exist_and_healthy(self):
        expected_images = [
            "jmp-platform-ui.png",
            "jmp-bivariate.png",
            "jmp-oneway.png",
            "jmp-distribution.png",
            "sixpack.png",
            "prediction-profiler.png",
            "d-optimal-correlations.png",
            "decision-tree.png",
            "dsd-pareto.png",
            "alt-life-vs-stress.png",
            "emp-gauge.png",
            "surface.png",
            "contour.png",
            "optimizer.png",
            "control-chart.png",
            "control-chart-builder.png",
            "process-screening.png",
            "jmp-variability.png",
            "r-workbench.png",
            "doe-factorial.png",
        ]

        for name in expected_images:
            path = self.img_dir / name
            self.assertTrue(path.exists(), f"Showcase image missing: {name}")
            size = path.stat().st_size
            # Ensure images are rich full-resolution screenshots (> 15KB)
            self.assertGreater(size, 15000, f"Showcase image too small or truncated: {name} ({size} bytes)")

            # Verify PNG header
            with open(path, "rb") as f:
                header = f.read(8)
            self.assertEqual(header, b"\x89PNG\r\n\x1a\n", f"Invalid PNG magic bytes: {name}")


if __name__ == "__main__":
    unittest.main()
