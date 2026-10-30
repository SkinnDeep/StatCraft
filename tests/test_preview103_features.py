"""Unit and integration tests for Preview 103: Setup Wizard, Auto-Updater, and Expanded Parity."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from statcraft.updater import (
    STATCRAFT_VERSION, parse_version, compare_versions,
    read_install_metadata, write_install_metadata,
    check_for_updates, get_default_install_dir
)
from statcraft.descriptive_report import format_descriptive_stats_report
from statcraft.app import Presenter, format_entry
from statcraft.model import Worksheet, Column
from installer_main import find_source_binary, perform_silent_install


class TestPreview103Features(unittest.TestCase):

    def test_version_parsing_and_comparison(self):
        self.assertEqual(parse_version("103.0.0"), (103, 0, 0))
        self.assertEqual(parse_version("v103.1.2"), (103, 1, 2))
        self.assertEqual(parse_version("V104"), (104, 0, 0))
        self.assertEqual(parse_version(""), (0, 0, 0))

        self.assertEqual(compare_versions("103.0.0", "103.0.0"), 0)
        self.assertEqual(compare_versions("102.0.0", "103.0.0"), -1)
        self.assertEqual(compare_versions("104.0.0", "103.0.0"), 1)
        self.assertEqual(compare_versions("v103.0.1", "103.0.0"), 1)
        self.assertEqual(compare_versions("103.0.0", "v103.0.1"), -1)

    def test_install_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            meta_file = write_install_metadata(target, "103.0.0", channel="preview", repo="statcraft/statcraft")
            self.assertTrue(meta_file.exists())

            loaded = read_install_metadata(target)
            self.assertEqual(loaded.get("version"), "103.0.0")
            self.assertEqual(loaded.get("channel"), "preview")
            self.assertEqual(loaded.get("repo"), "statcraft/statcraft")

    def test_check_for_updates_local_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            manifest_file = Path(td) / "release.json"
            manifest_data = {
                "tag_name": "v104.0.0",
                "name": "StatCraft 104 Release",
                "body": "Major performance improvements and new StatCraft workflows.",
                "download_url": "https://example.com/StatCraft-Setup.exe"
            }
            manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

            res = check_for_updates(current_ver="103.0.0", manifest_url=str(manifest_file))
            self.assertTrue(res["update_available"])
            self.assertEqual(res["latest_version"], "104.0.0")
            self.assertEqual(res["download_url"], "https://example.com/StatCraft-Setup.exe")
            self.assertIn("Major performance", res["release_notes"])

            # Test when already up-to-date
            res_current = check_for_updates(current_ver="104.0.0", manifest_url=str(manifest_file))
            self.assertFalse(res_current["update_available"])
            self.assertEqual(res_current["latest_version"], "104.0.0")

    def test_descriptive_stats_report_formatting(self):
        result = {
            "columns": [
                {
                    "name": "Length",
                    "count": 100,
                    "missing": 0,
                    "mean": 12.3456,
                    "standard_error": 0.1234,
                    "sample_stdev": 1.2345,
                    "minimum": 9.5,
                    "q1": 11.5,
                    "median": 12.3,
                    "q3": 13.1,
                    "maximum": 15.2,
                    "warnings": []
                }
            ]
        }
        report = format_descriptive_stats_report(result)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("Variable", report)
        self.assertIn("Length", report)
        self.assertIn("12.3456", report)
        self.assertIn("N* counts missing values", report)

        entry = {
            "title": "Descriptive Statistics: Length",
            "time": "Test Time",
            "result": result
        }
        entry_output = format_entry(entry)
        self.assertIn("Descriptive Statistics: Length", entry_output)
        self.assertIn("12.3456", entry_output)

    def test_source_binary_finding(self):
        found = find_source_binary()
        # Should locate either outputs/StatCraft.exe or work/statcraft-modern-next/StatCraft.exe
        self.assertIsNotNone(found)
        self.assertTrue(found.exists())

    def test_silent_installer(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "StatCraftInstall"
            code = perform_silent_install(target, desktop=False, start_menu=False)
            self.assertEqual(code, 0)
            self.assertTrue((target / "StatCraft.exe").exists())
            self.assertTrue((target / "version.json").exists())
            meta = read_install_metadata(target)
            self.assertEqual(meta.get("version"), STATCRAFT_VERSION)


if __name__ == "__main__":
    unittest.main()
