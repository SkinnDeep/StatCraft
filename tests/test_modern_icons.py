"""Unit tests for StatCraft modern multiresolution icons."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["STATCRAFT_TESTING"] = "1"

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from statcraft.modern_icons import ICON_KEYS, _ALIASES, tool_icon


class ModernIconsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_icon_keys_produce_valid_icons(self):
        for key in ICON_KEYS:
            icon = tool_icon(key)
            self.assertFalse(icon.isNull(), f"tool_icon('{key}') should not be null")
            pix = icon.pixmap(24, 24)
            self.assertFalse(pix.isNull(), f"tool_icon('{key}') pixmap should not be null")
            self.assertGreater(pix.width(), 0)
            self.assertGreater(pix.height(), 0)

    def test_new_action_icons_present(self):
        expected_icons = [
            "chart", "code_view", "connect", "covariance", "graphical_summary",
            "multivari", "outlier_test", "report", "run_chart", "select_all",
            "standardize", "subset", "table", "update", "workflow",
        ]
        for key in expected_icons:
            self.assertIn(key, ICON_KEYS, f"{key} must be in ICON_KEYS")
            icon = tool_icon(key)
            self.assertFalse(icon.isNull())
            pix = icon.pixmap(24, 24)
            self.assertFalse(pix.isNull())

    def test_aliases_resolve(self):
        aliases = ["distribution", "check_for_updates", "r_code", "r_script"]
        for a in aliases:
            self.assertIn(a, _ALIASES)
            icon = tool_icon(a)
            self.assertFalse(icon.isNull())


if __name__ == "__main__":
    unittest.main()
