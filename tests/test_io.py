"""Independent fixtures for typed persistence and bounded archive import."""
import copy
import hashlib
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statcraft.model import Column, Matrix, Worksheet, serial_to_datetime, datetime_to_serial
from statcraft.io import (FormatError, UnsupportedFormatError, parse_delimited,
    load_csv, save_csv, load_project, save_project, load_mwx, save_mwx, MISSING_SENTINEL)


def variable(name, values, kind="number", class_id=434, width=1):
    vt = {434: 3, 435: 2, 436: 4}[class_id]
    numeric = kind != "text"
    data = {"ClassId": 447, "CellCt": len(values), "ColCt": width,
            "HasNumericData": numeric, "HasTextData": not numeric,
            "NumericData" if numeric else "TextData": values}
    return {"ClassId": class_id, "WorksheetVar": None, "Compressed": False,
            "WorksheetVarBody": {"ClassId": 437, "Name": name,
             "Format": {"Key": {"number": 1, "date": 2, "text": 3}[kind]},
             "VarData": {"ClassId": 439, "VariableType": vt, "Data": 1 if numeric else 2,
                         "VarDataBody": data}}}


def fixture():
    return {"Version": 20200604, "Data": {
        "Columns": [variable("numbers", [1, MISSING_SENTINEL, 3]),
                    variable("labels", ["", "*", "Ω\nquoted,\"value"], "text"),
                    variable("dates", [43831, 43832.520833333336], "date")],
        "Constants": [variable("pi", [3.141592653589793], class_id=435)],
        "Matrices": [variable("M", [1, 2, 3, 4, 5, 6], class_id=436, width=3)],
        "UnknownModel": {"opaque": ["preserve", 42]}}}


def archive(path, sheet=None, members=None, metadata=None):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("/", "")
        z.writestr("/sheet_metadata_20.json", json.dumps(metadata or {
            "Version": 20200604, "Worksheet": {"Name": "Synthetic", "Uri": "/sheets/0/sheet"}}))
        z.writestr("/sheets/0/sheet.json", json.dumps(sheet or fixture()))
        for name, data in members or []:
            z.writestr(name, data)


class TypedModelTests(unittest.TestCase):
    def test_missing_ragged_rows_and_complete_case_alignment(self):
        sheet = Worksheet("T", [Column("A", values=[1, None, 3]), Column("B", values=[10, 20])])
        self.assertEqual(sheet.row_count, 3)
        self.assertEqual(sheet.row(2), [3, None])
        self.assertEqual(sheet.complete_rows([0, 1]), [[1.0, 10.0]])
        self.assertEqual(sheet.numeric_column(0), [1.0, 3.0])
        self.assertEqual(sheet.numeric_column(0, True), [1.0, None, 3.0])

    def test_matrix_column_major_and_bounds(self):
        matrix = Matrix("M", 2, 3, [1, 2, 3, 4, 5, 6])
        self.assertEqual(matrix.as_rows(), [[1, 3, 5], [2, 4, 6]])
        with self.assertRaises(IndexError):
            matrix.cell(2, 0)
        with self.assertRaises(ValueError):
            Matrix("broken", 2, 3, [1])

    def test_invalid_nonfinite_and_text_values(self):
        for value in [float("nan"), float("inf"), True, "3"]:
            with self.assertRaises(ValueError):
                Column("A", values=[value])
        with self.assertRaises(ValueError):
            Column("S", "text", [1])

    def test_dates_do_not_invent_timezones_or_negative_ole_rules(self):
        self.assertEqual(serial_to_datetime(43831), datetime(2020, 1, 1))
        self.assertEqual(serial_to_datetime(43832.520833333336), datetime(2020, 1, 2, 12, 30))
        self.assertEqual(datetime_to_serial(datetime(2020, 1, 1)), 43831)
        with self.assertRaises(ValueError):
            serial_to_datetime(-0.25)


class DelimitedTests(unittest.TestCase):
    def test_quoting_unicode_newlines_missing_and_tsv(self):
        sheet = parse_delimited('N,S\n1,"Ω, \'quoted\'"\n*,"line1\nline2"\n3,*\n')
        self.assertEqual(sheet.columns[0].values, [1.0, None, 3.0])
        self.assertEqual(sheet.columns[1].values, ["Ω, 'quoted'", "line1\nline2", "*"])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            target = Path(tmp) / "test.tsv"
            save_csv(sheet, target)
            loaded = load_csv(target)
            self.assertEqual([c.values for c in loaded.columns], [c.values for c in sheet.columns])

    def test_explicit_text_retains_empty_and_numeric_looking_labels(self):
        sheet = parse_delimited("code,date\n001,2020-01-01\n*,2020-01-02T12:30:00\n", column_types=["text", "date"])
        self.assertEqual(sheet.columns[0].values, ["001", "*"])
        self.assertEqual(sheet.columns[1].values, [43831, 43832.520833333336])

    def test_reject_malformed_dimensions_numeric_and_quotes(self):
        for text in ["A,B\n1\n", 'A\n"unterminated']:
            with self.assertRaises(FormatError):
                parse_delimited(text)
        with self.assertRaises(FormatError):
            parse_delimited("A\nNaN\n", column_types=["number"])


class PersistenceTests(unittest.TestCase):
    def test_failed_atomic_save_preserves_existing_project(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            path = Path(tmp) / "existing.statcraft"
            path.write_text("existing content", encoding="utf8")
            with patch("statcraft.io.os.replace", side_effect=OSError("simulated locked destination")):
                with self.assertRaises(OSError):
                    save_project(Worksheet("new", [Column("A", values=[1])]), path)
            self.assertEqual(path.read_text(encoding="utf8"), "existing content")
            self.assertEqual(list(Path(tmp).glob(".statcraft-*")), [])

    def test_original_project_full_typed_roundtrip(self):
        original = Worksheet("Unicode Ω", [Column("A", values=[1, None]),
            Column("S", "text", ["", "*"]), Column("D", "date", [43831])],
            [Column("K", values=[3.14])], [Matrix("M", 2, 2, [1, None, 3, 4])],
            {"unsupported": {"retain": "yes"}})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            path = Path(tmp) / "p.statcraft"
            save_project(original, path)
            self.assertEqual(load_project(path), original)
            content = json.loads(path.read_text(encoding="utf8"))
            content["version"] = 2
            path.write_text(json.dumps(content), encoding="utf8")
            with self.assertRaises(UnsupportedFormatError):
                load_project(path)

    def test_project_rejects_duplicate_json_and_nonfinite(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p = Path(tmp) / "bad.json"
            for text in ['{"schema":"statcraft-project","schema":"other"}', '{"x": NaN}']:
                p.write_text(text, encoding="utf8")
                with self.assertRaises(FormatError):
                    load_project(p)


class MwxImportTests(unittest.TestCase):
    def test_durable_normal_ui_wsave_numeric_fixture(self):
        directory = Path(__file__).resolve().parent / "fixtures"
        provenance = json.loads((directory / "reference-wsave-numeric.provenance.json").read_text(encoding="utf8"))
        path = directory / provenance["fixture"]
        raw = path.read_bytes()
        self.assertEqual(len(raw), provenance["bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), provenance["sha256"])
        sheet = load_mwx(path)
        self.assertEqual(sheet.headers, ["C1", "C2", "C3", "C4", "C5"])
        self.assertEqual([c.values for c in sheet.columns], provenance["expected_numeric_columns"])
        for col in sheet.columns:
            original = col.metadata["imported_variable_metadata"]
            self.assertEqual(original["WorksheetVarBody"]["Name"], "")
        with zipfile.ZipFile(path) as source:
            body = json.loads(source.read("/sheets/0/sheet.json"))
        saved_c3 = body["Data"]["Columns"][2]["WorksheetVarBody"]["VarData"]["VarDataBody"]["NumericData"]
        self.assertEqual(saved_c3, [7, MISSING_SENTINEL, MISSING_SENTINEL, MISSING_SENTINEL, MISSING_SENTINEL])

    def test_unverified_null_numeric_missing_date_and_malformed_objects(self):
        cases = []
        nulls = fixture(); nulls["Data"]["Columns"][0]["WorksheetVarBody"]["VarData"]["VarDataBody"]["NumericData"][0] = None; cases.append(nulls)
        dates = fixture(); dates["Data"]["Columns"][2]["WorksheetVarBody"]["VarData"]["VarDataBody"]["NumericData"][0] = MISSING_SENTINEL; cases.append(dates)
        malformed = fixture(); malformed["Data"] = []; cases.append(malformed)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            path = Path(tmp) / "unsupported.mwx"
            for data in cases:
                archive(path, data)
                with self.assertRaises(FormatError):
                    load_mwx(path)
            archive(path, metadata={"Version": 20200604, "Worksheet": []})
            with self.assertRaises(FormatError):
                load_mwx(path)

    def test_observed_contract_types_constants_matrix_metadata(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p = Path(tmp) / "sheet.mwx"
            archive(p, members=[("/unknown.bin", b"uninterpreted")])
            sheet = load_mwx(p)
            self.assertEqual(sheet.columns[0].values, [1.0, None, 3.0])
            self.assertEqual(sheet.columns[1].values, ["", "*", 'Ω\nquoted,"value'])
            self.assertEqual(sheet.columns[2].kind, "date")
            self.assertEqual(sheet.constants[0].values, [3.141592653589793])
            self.assertEqual(sheet.matrices[0].as_rows(), [[1, 3, 5], [2, 4, 6]])
            self.assertEqual(sheet.metadata["import"]["unsupported_payload_metadata"]["UnknownModel"],
                             {"opaque": ["preserve", 42]})
            self.assertEqual(len(sheet.metadata["import"]["warnings"]), 3)
            self.assertFalse((Path(tmp) / "unknown.bin").exists())
            out = Path(tmp) / "read.statcraft"
            save_project(sheet, out)
            self.assertEqual(load_project(out), sheet)
            with self.assertRaises(UnsupportedFormatError):
                save_mwx(sheet, Path(tmp) / "out.mwx")

    def test_reject_unverified_versions_counts_mixed_and_path_traversal(self):
        cases = []
        version = fixture(); version["Version"] = 20200605; cases.append(version)
        wrong = fixture(); wrong["Data"]["Columns"][0]["WorksheetVarBody"]["VarData"]["VarDataBody"]["CellCt"] = 4; cases.append(wrong)
        mixed = fixture(); mixed["Data"]["Columns"][0]["WorksheetVarBody"]["VarData"]["VarDataBody"]["HasTextData"] = True; cases.append(mixed)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p = Path(tmp) / "bad.mwx"
            for data in cases:
                archive(p, data)
                with self.assertRaises(FormatError):
                    load_mwx(p)
            archive(p, members=[("/../escaped.txt", b"no")])
            with self.assertRaises(FormatError):
                load_mwx(p)
            self.assertFalse((Path(tmp).parent / "escaped.txt").exists())

    def test_reject_duplicate_members_uri_and_bounded_decompression(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p = Path(tmp) / "bad.mwx"
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive(p, members=[("/sheets/0/sheet.json", b"{}")])
            with self.assertRaises(FormatError):
                load_mwx(p)
            archive(p, metadata={"Version": 20200604, "Worksheet": {"Uri": "../../other"}})
            with self.assertRaises(UnsupportedFormatError):
                load_mwx(p)
            from unittest.mock import patch
            archive(p)
            with patch("statcraft.io.MAX_MEMBER_BYTES", 8):
                with self.assertRaises(FormatError):
                    load_mwx(p)

    def test_saved_research_samples_if_present(self):
        # Optional research correlation: no product dependency on fixtures.
        outputs = Path(__file__).resolve().parents[3] / "outputs"
        checked = 0
        for name in ("statcraft-runtime-worksheet-decoded.json",
                     "statcraft-runtime-typed-worksheet-decoded.json",
                     "statcraft-runtime-numeric-edge-decoded.json"):
            source = outputs / name
            if not source.exists():
                continue
            decoded = json.loads(source.read_text(encoding="utf8"))
            p = Path(decoded["artifact"]["path"])
            if not p.exists():
                continue
            result = load_mwx(p)
            sheet_json = next(m["json"] for m in decoded["members"] if m["name"].endswith("/sheet.json"))
            expected = sheet_json["Data"]
            self.assertEqual(len(result.columns), len(expected["Columns"]))
            for col, original in zip(result.columns, expected["Columns"]):
                body = original["WorksheetVarBody"]["VarData"]["VarDataBody"]
                values = body.get("TextData", body.get("NumericData"))
                self.assertEqual(col.values, [None if v == MISSING_SENTINEL else v for v in values])
            checked += 1
        if not checked:
            self.skipTest("Research fixtures are optional and absent.")


if __name__ == "__main__":
    unittest.main()
