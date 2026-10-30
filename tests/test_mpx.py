"""Synthetic native-container contracts, no third-party dataset redistribution."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statcraft.mpx import Project, load_mpx, save_mpx
from statcraft.model import Column, Worksheet
from statcraft.io import FormatError, UnsupportedFormatError, MISSING_SENTINEL


def variable(name, values, kind="number", class_id=434, width=1):
    numeric = kind != "text"
    body = {"ClassId": 447, "CellCt": len(values), "ColCt": width, "CharCt": 4 if not numeric else 0,
            "HasNumericData": numeric, "HasTextData": not numeric,
            "NumericData" if numeric else "TextData": values}
    return {"ClassId": class_id, "Compressed": False, "WorksheetVar": None,
            "UnknownObjectField": {"preserve": [1, "Ω"]},
            "WorksheetVarBody": {"ClassId": 437, "Name": name,
             "Format": {"Key": {"number": 1, "date": 2, "text": 3}[kind]},
             "VarData": {"ClassId": 439, "VariableType": {434: 3, 435: 2, 436: 4}[class_id],
                         "Data": 1 if numeric else 2, "VarDataBody": body}}}


def documents():
    metadata = {"Version": 20200604, "Worksheets": {"Items": [
        {"Id": "a", "Name": "First synthetic worksheet", "Uri": "/sheets/0/sheet"},
        {"Id": "b", "Name": "Second synthetic worksheet", "Uri": "/sheets/1/sheet"}],
        "ExtraInformation": {"current_worksheet": "a", "worksheet_ordering": ["b", "a"]}},
        "History": ["Synthetic command"], "Commands": {"Items": [{"SyntheticUnknown": 42}]},
        "Models": {"Items": [{"UnknownTestModel": ["never execute"]}]}}
    first = {"Version": 20200604, "Data": {"Columns": [variable("", [1, MISSING_SENTINEL]), variable("Labels", ["a", "b"], "text")],
        "Constants": [variable("K", [3.5], class_id=435)],
        "Matrices": [variable("M", [1, 2, 3, 4], class_id=436, width=2)],
        "UnknownWorksheetPayload": {"retain": "unaltered"}}, "UnknownTop": [4, 5]}
    second = {"Version": 20200604, "Data": {"Columns": [variable("Values", [3, 4]), variable("Dates", [43831, 43832], "date")],
        "Constants": [], "Matrices": []}}
    return metadata, first, second


def fixture(path, metadata=None, first=None, extra=None):
    meta, a, b = documents()
    members = [("/", b""), ("/project_metadata_20.json", json.dumps(metadata or meta).encode("utf8")),
               ("/sheets/0/sheet.json", json.dumps(first or a, ensure_ascii=False).encode("utf8")),
               ("/sheets/1/sheet.json", json.dumps(b).encode("utf8")), ("/unknown/blob.bin", bytes(range(32)))]
    with zipfile.ZipFile(path, "w") as archive:
        archive.comment = b"original synthetic archive comment"
        for name, payload in members + (extra or []):
            info = zipfile.ZipInfo(name, (2025, 1, 2, 3, 4, 6)); info.compress_type = zipfile.ZIP_DEFLATED
            info.comment = b"test member"; info.external_attr = 0o600 << 16
            archive.writestr(info, payload)


def scratch():
    return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)


class MpxTests(unittest.TestCase):
    def test_all_worksheets_ui_order_active_history_constants_matrices(self):
        with scratch() as tmp:
            path = Path(tmp) / "original.mpx"; fixture(path)
            project = load_mpx(path)
            self.assertEqual(project.worksheet_ids, ["b", "a"])
            self.assertEqual(project.worksheet_uris, ["/sheets/1/sheet", "/sheets/0/sheet"])
            self.assertEqual(project.active_index, 1)
            self.assertEqual(project.active_worksheet.name, "First synthetic worksheet")
            self.assertEqual(project.active_worksheet.columns[0].values, [1, None])
            self.assertEqual(project.active_worksheet.constants[0].values, [3.5])
            self.assertEqual(project.active_worksheet.matrices[0].as_rows(), [[1, 3], [2, 4]])
            self.assertEqual(project.history, ["Synthetic command"])
            self.assertEqual(project.retained_members["/unknown/blob.bin"], bytes(range(32)))
            self.assertFalse((Path(tmp) / "unknown").exists())

    def test_untouched_native_save_copy_is_byte_exact_and_cannot_overwrite(self):
        with scratch() as tmp:
            path = Path(tmp) / "original.mpx"; fixture(path)
            original = path.read_bytes(); project = load_mpx(path)
            with self.assertRaises(UnsupportedFormatError): save_mpx(project, path)
            target = Path(tmp) / "copy.mpx"; notices = save_mpx(project, target)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(any("byte-for-byte" in n for n in notices))

    def test_existing_original_hardlink_is_blocked(self):
        with scratch() as tmp:
            path = Path(tmp) / "original.mpx"; fixture(path)
            alias = Path(tmp) / "alias.mpx"
            try: os.link(path, alias)
            except OSError as exc: self.skipTest("Hardlinks unavailable: " + str(exc))
            project = load_mpx(path)
            with self.assertRaises(UnsupportedFormatError): save_mpx(project, alias)
            self.assertEqual(path.read_bytes(), alias.read_bytes())

    def test_supported_fixed_size_column_edits_preserve_unknown_members_and_names(self):
        with scratch() as tmp:
            source = Path(tmp) / "original.mpx"; fixture(source)
            original = source.read_bytes(); project = load_mpx(source)
            sheet = project.active_worksheet
            sheet.columns[0].values = [99, None]
            sheet.columns[1].values = ["Ω", "bb"]
            sheet.columns[1].name = "New label"
            target = Path(tmp) / "edit.mpx"
            notices = save_mpx(project, target)
            self.assertTrue(any("stale" in n for n in notices))
            self.assertEqual(source.read_bytes(), original)
            loaded = load_mpx(target)
            self.assertEqual(loaded.active_worksheet.columns[0].values, [99, None])
            self.assertEqual(loaded.active_worksheet.columns[1].values, ["Ω", "bb"])
            self.assertEqual(loaded.active_worksheet.columns[1].name, "New label")
            with zipfile.ZipFile(source) as old, zipfile.ZipFile(target) as new:
                self.assertEqual(old.comment, new.comment)
                for info in old.infolist():
                    new_info = new.getinfo(info.filename)
                    self.assertEqual((info.date_time, info.comment, info.external_attr, info.compress_type),
                                     (new_info.date_time, new_info.comment, new_info.external_attr, new_info.compress_type))
                    if info.filename != "/sheets/0/sheet.json": self.assertEqual(old.read(info), new.read(info.filename))
                document = json.loads(new.read("/sheets/0/sheet.json"))
                self.assertEqual(document["Data"]["Columns"][0]["WorksheetVarBody"]["Name"], "")
                self.assertEqual(document["Data"]["UnknownWorksheetPayload"], {"retain": "unaltered"})

    def test_save_active_worksheet_known_metadata_id(self):
        with scratch() as tmp:
            path = Path(tmp) / "original.mpx"; fixture(path)
            project = load_mpx(path); project.active_index = 0
            target = Path(tmp) / "select.mpx"; save_mpx(project, target)
            self.assertEqual(load_mpx(target).active_index, 0)
            with zipfile.ZipFile(path) as a, zipfile.ZipFile(target) as b:
                for name in a.namelist():
                    if name != "/project_metadata_20.json": self.assertEqual(a.read(name), b.read(name))

    def test_reject_unverified_structure_type_length_dates_models_and_history_edits(self):
        with scratch() as tmp:
            path = Path(tmp) / "original.mpx"; fixture(path)
            changes = [lambda p: p.active_worksheet.columns.append(Column("New",'date')),
                       lambda p: p.active_worksheet.columns[1].values.append('a'),
                       lambda p: setattr(p.active_worksheet.columns[0], "kind", "date"),
                       lambda p: p.worksheets[0].columns[1].values.__setitem__(0, 43833),
                       lambda p: p.active_worksheet.constants[0].values.__setitem__(0, 10),
                       lambda p: p.history.append("new analysis"),
                       lambda p: p.metadata.__setitem__("Models", {}),
                       lambda p: p.active_worksheet.columns[1].values.__setitem__(0, "too long")]
            for index, change in enumerate(changes):
                project = load_mpx(path); change(project)
                target = Path(tmp) / ("invalid" + str(index) + ".mpx")
                with self.assertRaises(UnsupportedFormatError): save_mpx(project, target)
                self.assertFalse(target.exists())
            with self.assertRaises(UnsupportedFormatError): save_mpx(Project("new", [Worksheet()]), Path(tmp) / "new.mpx")

    def test_untyped_empty_column_preserved_but_native_initialization_rejected(self):
        with scratch() as tmp:
            meta, first, second = documents()
            empty = variable("", [], "number")
            var = empty["WorksheetVarBody"]["VarData"]; var["Data"] = 0
            empty["WorksheetVarBody"]["Format"]["Key"] = 0
            body = var["VarDataBody"]; body["ColCt"] = 0; body["HasNumericData"] = False; body.pop("NumericData")
            first["Data"]["Columns"].append(empty)
            path = Path(tmp) / "empty.mpx"; fixture(path, first=first)
            p = load_mpx(path)
            self.assertEqual(p.active_worksheet.columns[2].name, "C3")
            self.assertEqual(p.active_worksheet.columns[2].values, [])
            target = Path(tmp) / "copy.mpx"; save_mpx(p, target)
            self.assertEqual(target.read_bytes(), path.read_bytes())
            p.active_worksheet.columns[2].values = [1]
            with self.assertRaises(UnsupportedFormatError): save_mpx(p, Path(tmp) / "edit.mpx")

    def test_reject_unsafe_duplicate_unknown_schema_reference_and_size(self):
        with scratch() as tmp:
            path = Path(tmp) / "bad.mpx"
            metadata, first, second = documents()
            metadata["Worksheets"]["Items"][0]["Uri"] = "../../escape"
            fixture(path, metadata=metadata)
            with self.assertRaises(FormatError): load_mpx(path)
            fixture(path, extra=[("/../escape", b"x")])
            with self.assertRaises(FormatError): load_mpx(path)
            metadata, first, second = documents(); metadata["Version"] = 20200605
            fixture(path, metadata=metadata)
            with self.assertRaises(UnsupportedFormatError): load_mpx(path)
            fixture(path)
            with patch("statcraft.mpx.io.MAX_MEMBER_BYTES", 8):
                with self.assertRaises(FormatError): load_mpx(path)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fixture(path, extra=[("/project_metadata_20.json", b"{}")])
            with self.assertRaises(FormatError): load_mpx(path)

    def test_atomic_save_failure_preserves_existing_copy(self):
        with scratch() as tmp:
            source = Path(tmp) / "source.mpx"; fixture(source)
            p = load_mpx(source); target = Path(tmp) / "destination.mpx"; target.write_bytes(b"old copy")
            with patch("statcraft.mpx.os.replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError): save_mpx(p, target)
            self.assertEqual(target.read_bytes(), b"old copy")
            self.assertEqual(list(Path(tmp).glob(".statcraft-mpx-*")), [])


if __name__ == "__main__": unittest.main()
