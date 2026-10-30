"""Unit tests for StatCraft JMP file reader."""
from __future__ import annotations

import tempfile
import struct
import unittest
from pathlib import Path

from statcraft.app import Presenter
from statcraft.jmp_reader import is_jmp_file, load_jmp, _parse_jsl_table, _parse_jmp_binary, JmpParseError


class TestJmpReader(unittest.TestCase):
    def test_is_jmp_file(self):
        self.assertTrue(is_jmp_file("sample.jmp"))
        self.assertTrue(is_jmp_file("sample.jsl"))
        self.assertFalse(is_jmp_file("sample.csv"))
        self.assertFalse(is_jmp_file("sample.mpx"))

    def test_parse_jsl_table(self):
        jsl_script = """
        // JMP Table Export Script
        New Table( "Semiconductor Yield",
            Add Rows( 4 ),
            New Column( "Wafer ID", Character, Set Values( ["W01", "W02", "W03", "W04"] ) ),
            New Column( "Thickness", Numeric, 
                Set Property( "Spec Limits", {LSL( 45.0 ), USL( 55.0 ), Target( 50.0 )} ),
                Set Values( [49.2, 50.8, ., 52.1] )
            ),
            New Column( "Status", Character, Set Values( ["Pass", "Pass", "Fail", "Pass"] ) )
        );
        """
        ws = _parse_jsl_table(jsl_script, "Default")
        self.assertEqual(ws.name, "Semiconductor Yield")
        self.assertEqual(len(ws.columns), 3)

        c1 = ws.columns[0]
        self.assertEqual(c1.name, "Wafer ID")
        self.assertEqual(c1.kind, "text")
        self.assertEqual(c1.values, ["W01", "W02", "W03", "W04"])

        c2 = ws.columns[1]
        self.assertEqual(c2.name, "Thickness")
        self.assertEqual(c2.kind, "number")
        self.assertEqual(c2.values[0], 49.2)
        self.assertEqual(c2.values[1], 50.8)
        self.assertIsNone(c2.values[2])
        self.assertEqual(c2.values[3], 52.1)
        self.assertIn("spec_limits", c2.metadata)
        self.assertEqual(c2.metadata["spec_limits"]["lsl"], 45.0)
        self.assertEqual(c2.metadata["spec_limits"]["usl"], 55.0)
        self.assertEqual(c2.metadata["spec_limits"]["target"], 50.0)

        c3 = ws.columns[2]
        self.assertEqual(c3.name, "Status")
        self.assertEqual(c3.kind, "text")
        self.assertEqual(c3.values, ["Pass", "Pass", "Fail", "Pass"])

    def test_parse_jmp_binary_heuristic(self):
        # Create a mock binary buffer with column names in header and 64-bit IEEE double floats
        header = b'LLLL' + b'\x00' * 32
        # Inject column names
        col_names = b'\x08Voltage\x00\x08Current\x00'
        padding = b'\x00' * (128 - len(header) - len(col_names))
        floats = struct.pack('<4d', 12.5, 12.8, 1.25, 1.45)
        raw_data = header + col_names + padding + floats

        ws = _parse_jmp_binary(raw_data, "TestBinary")
        self.assertEqual(ws.name, "TestBinary")
        self.assertTrue(len(ws.columns) >= 2)
        col_titles = [c.name for c in ws.columns]
        self.assertIn("Voltage", col_titles)
        self.assertIn("Current", col_titles)

    def test_load_jmp_via_presenter(self):
        jsl_script = """
        New Table( "Tensile Strength",
            Add Rows( 3 ),
            New Column( "Batch", Character, Set Values( ["B1", "B2", "B3"] ) ),
            New Column( "Strength", Numeric, Set Values( [105.4, 110.2, 98.7] ) )
        );
        """
        with tempfile.NamedTemporaryFile(suffix=".jsl", mode="w", delete=False, encoding="utf-8") as f:
            f.write(jsl_script)
            tmp_path = f.name

        try:
            p = Presenter()
            p.load(tmp_path)
            self.assertEqual(p.worksheet.name, "Tensile Strength")
            self.assertEqual([c.name for c in p.worksheet.columns], ["Batch", "Strength"])
            self.assertEqual(p.worksheet.columns[1].values, [105.4, 110.2, 98.7])
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
