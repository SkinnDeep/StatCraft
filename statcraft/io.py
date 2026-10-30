"""Original project/CSV IO and a deliberately limited read-only MWX importer.

MWX support is the observed ZIP/JSON version only. No MWX writer or claim of
application round-trip compatibility is provided. Archive members are never
extracted, interpreted as local paths, or executed.
"""
import copy
import csv
import hashlib
import io as _io
import json
from pathlib import Path
import re
import os
import tempfile
import zipfile
import struct
from .model import Column, Matrix, Worksheet, finite_number, datetime_to_serial
from datetime import datetime

MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 1000
MAX_CELLS = 1_000_000
PROJECT_SCHEMA = "statcraft-project"
PROJECT_VERSION = 1
MISSING_SENTINEL = 1.23456e30


class FormatError(ValueError):
    pass


class UnsupportedFormatError(FormatError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FormatError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _json(raw):
    def reject(value):
        raise FormatError("Nonfinite JSON number: " + value)
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=reject)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise FormatError("Invalid or excessively nested JSON.") from exc


def _count(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise FormatError(label + " must be an integer.")
    try:
        number = finite_number(value)
    except ValueError as exc:
        raise FormatError(label + " must be a finite integer.") from exc
    if number != int(number) or number < minimum or number > MAX_CELLS:
        raise FormatError(label + " is outside supported dimensions.")
    return int(number)


def _numeric(value):
    if value is None:
        return None
    try:
        return finite_number(value)
    except ValueError as exc:
        raise FormatError(str(exc)) from exc


def _write_atomic(path, raw):
    """Replace a completed save atomically, preserving existing files on errors."""
    path = Path(path)
    if len(raw.encode("utf-8")) > MAX_TOTAL_BYTES:
        raise FormatError("Saved file exceeds the size limit.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, prefix=".statcraft-", delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def _parse_cell(value, kind):
    if kind == "text":
        return value
    if value.strip() in ("", "*"):
        return None
    try:
        if kind == "date":
            try:
                return datetime_to_serial(datetime.fromisoformat(value.strip()))
            except ValueError:
                return finite_number(float(value))
        return finite_number(float(value))
    except (ValueError, OverflowError) as exc:
        raise FormatError("Invalid " + kind + " cell: " + repr(value)) from exc


def parse_delimited(text, delimiter=",", has_header=True, column_types=None, name="Worksheet"):
    if delimiter not in (",", "\t", ";"):
        raise FormatError("Choose comma, tab or semicolon as delimiter.")
    try:
        rows = list(csv.reader(_io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
    except csv.Error as exc:
        raise FormatError("Invalid delimited text: " + str(exc)) from exc
    if not rows:
        return Worksheet(name)
    width = len(rows[0])
    headers = rows.pop(0) if has_header else ["C" + str(i + 1) for i in range(width)]
    if not width:
        raise FormatError("The first row has no fields.")
    if any(len(row) != width for row in rows):
        raise FormatError("Rows must all have the same number of fields; no data was dropped.")
    if len(rows) * width > MAX_CELLS:
        raise FormatError("The table exceeds the cell limit.")
    if column_types is not None and len(column_types) != width:
        raise FormatError("Specify one type per column.")
    columns = []
    for index, header in enumerate(headers):
        raw = [row[index] for row in rows]
        kind = column_types[index] if column_types is not None else None
        if kind is None:
            nonmissing = [v for v in raw if v.strip() not in ("", "*")]
            try:
                for v in nonmissing:
                    finite_number(float(v))
                kind = "number" if nonmissing else "text"
            except ValueError:
                kind = "text"
        if kind not in ("number", "text", "date"):
            raise FormatError("Unsupported column type: " + str(kind))
        columns.append(Column(header or "C" + str(index + 1), kind,
                              [_parse_cell(v, kind) for v in raw]))
    return Worksheet(name, columns, metadata={"import": {"format": "delimited", "delimiter": delimiter,
                          "type_inference": column_types is None}})


def load_csv(path, delimiter=None, has_header=True, column_types=None):
    path = Path(path)
    if path.stat().st_size > MAX_TOTAL_BYTES:
        raise FormatError("Delimited file exceeds the size limit.")
    delimiter = delimiter or ("\t" if path.suffix.lower() in (".tsv", ".tab") else ",")
    return parse_delimited(path.read_text(encoding="utf-8-sig"), delimiter,
                           has_header, column_types, path.stem)


def save_csv(worksheet, path, delimiter=None):
    """Exports the column table only. Returns explicit information-loss notices."""
    worksheet.validate()
    delimiter = delimiter or ("\t" if Path(path).suffix.lower() in (".tsv", ".tab") else ",")
    if delimiter not in (",", "\t", ";"):
        raise FormatError("Unsupported delimiter.")
    stream = _io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerow(worksheet.headers)
    for row in range(worksheet.row_count):
        writer.writerow(["" if v is None else v for v in worksheet.row(row)])
    _write_atomic(path, stream.getvalue())
    warnings = ["Delimited text does not retain column types, metadata or unequal column lengths."]
    if worksheet.constants or worksheet.matrices:
        warnings.append("Constants and matrices are not included in delimited export; use project save.")
    if any(c.kind == "date" for c in worksheet.columns):
        warnings.append("Date cells are exported as serial numbers; select date types when importing.")
    return warnings


def save_project(worksheet, path):
    worksheet.validate()
    def column(c):
        return {"name": c.name, "kind": c.kind, "values": c.values, "metadata": c.metadata}
    payload = {"schema": PROJECT_SCHEMA, "version": PROJECT_VERSION,
               "worksheet": {"name": worksheet.name, "columns": [column(c) for c in worksheet.columns],
                "constants": [column(c) for c in worksheet.constants],
                "matrices": [{"name": m.name, "rows": m.rows, "columns": m.columns,
                              "values": m.values, "metadata": m.metadata} for m in worksheet.matrices],
                "metadata": worksheet.metadata}}
    try:
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2)
    except (TypeError, ValueError, RecursionError) as exc:
        raise FormatError("Project contains unsupported metadata or numbers.") from exc
    if len(raw.encode("utf-8")) > MAX_TOTAL_BYTES:
        raise FormatError("Project exceeds the size limit.")
    _write_atomic(path, raw)


def load_project(path):
    if Path(path).stat().st_size > MAX_TOTAL_BYTES:
        raise FormatError("Project exceeds the size limit.")
    payload = _json(Path(path).read_text(encoding="utf-8-sig"))
    if (not isinstance(payload, dict) or payload.get("schema") != PROJECT_SCHEMA or
            type(payload.get("version")) is not int or payload.get("version") != 1):
        raise UnsupportedFormatError("Unsupported StatCraft project schema/version.")
    try:
        body = payload["worksheet"]
        result = Worksheet(body["name"], [Column(**c) for c in body["columns"]],
                           [Column(**c) for c in body.get("constants", [])],
                           [Matrix(**m) for m in body.get("matrices", [])], body.get("metadata", {}))
        if sum(len(c.values) for c in result.columns + result.constants) + sum(len(m.values) for m in result.matrices) > MAX_CELLS:
            raise FormatError("Project exceeds the cell limit.")
        return result
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, FormatError):
            raise
        raise FormatError("Invalid typed project data: " + str(exc)) from exc


def _numeric_blob_reference(raw, count):
    match=re.fullmatch(r'(/blobs/blob[1-9][0-9]*)\?size=([0-9]+)',raw) if isinstance(raw,str) else None
    if match is None: raise UnsupportedFormatError("Unsupported numeric blob reference; only an internal /blobs/blobN?size=N member is supported.")
    size=_count(int(match.group(2)),"Numeric blob size")
    if size!=count: raise FormatError("Numeric blob size does not match CellCt.")
    return match.group(1)


def _mwx_variable(entry, expected_class, variable_type, members=None):
    try:
        if entry["ClassId"] != expected_class or entry.get("Compressed") or entry.get("WorksheetVar") is not None:
            raise UnsupportedFormatError("Unsupported variable class, compressed or shared-body schema.")
        wrapper = entry["WorksheetVarBody"]
        var = wrapper["VarData"]
        if wrapper["ClassId"] != 437 or var["ClassId"] != 439 or var["VariableType"] != variable_type:
            raise UnsupportedFormatError("Unsupported variable-body schema.")
        body = var["VarDataBody"]
        if body["ClassId"] != 447:
            raise UnsupportedFormatError("Unsupported cell-storage schema.")
        count = _count(body["CellCt"], "CellCt")
        columns = _count(body["ColCt"], "ColCt", 1)
        fmt = wrapper["Format"]
        numeric, text = body.get("HasNumericData"), body.get("HasTextData")
        if numeric is True and text is False and var["Data"] == 1 and fmt["Key"] in (1, 2):
            kind = "date" if fmt["Key"] == 2 else "number"
            raw = body["NumericData"]
            if isinstance(raw,str):
                member=_numeric_blob_reference(raw,count)
                if members is None or member not in members: raise FormatError("Referenced numeric blob is missing from the project archive.")
                payload=members[member]
                if len(payload)!=count*8: raise FormatError("Numeric blob byte length does not match its declared number of double values.")
                raw=list(struct.unpack('<'+str(count)+'d',payload))
            if not isinstance(raw, list):
                raise FormatError("NumericData must be an array.")
            if any(v is None for v in raw):
                raise UnsupportedFormatError("Null numeric MWX cells have not been observed.")
            if kind == "date" and any(v == MISSING_SENTINEL for v in raw):
                raise UnsupportedFormatError("Missing-date sentinel semantics have not been verified.")
            values = [None if _numeric(v) == MISSING_SENTINEL else _numeric(v) for v in raw]
        elif text is True and numeric is False and var["Data"] == 2 and fmt["Key"] == 3:
            kind = "text"
            values = body["TextData"]
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise FormatError("TextData must be an array of strings.")
        else:
            raise UnsupportedFormatError("Unsupported mixed, empty, binary or unknown cell storage.")
        if len(values) != count:
            raise FormatError("CellCt does not match the stored array length.")
        metadata = copy.deepcopy(entry)
        retained_body = metadata["WorksheetVarBody"]["VarData"]["VarDataBody"]
        retained_body.pop("NumericData", None)
        retained_body.pop("TextData", None)
        return Column(wrapper["Name"], kind, values, {"imported_variable_metadata": metadata}), columns
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, FormatError):
            raise
        raise FormatError("Malformed or unsupported worksheet variable: " + str(exc)) from exc


def load_mwx(path):
    """Reads observed version 20200604 only; unsupported content is never executed.

    Metadata for unimplemented models is preserved in the native project, with
    an explicit warning. Unknown ZIP members retain names, hashes and sizes,
    not bytes; consequently this importer does NOT provide lossless MWX roundtrip.
    """
    path = Path(path)
    if path.stat().st_size > MAX_TOTAL_BYTES:
        raise FormatError("Archive exceeds the size limit.")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS:
                raise FormatError("Archive exceeds the member limit.")
            names = set()
            total = 0
            raw = {}
            inventory = []
            for info in members:
                name = info.filename
                # Leading '/' is observed as a virtual package root, never a destination.
                if (name in names or "\\" in name or "\x00" in name or
                        ":" in name or any(p in (".", "..") for p in name.split("/"))):
                    raise FormatError("Duplicate or unsafe virtual archive member.")
                names.add(name)
                if info.flag_bits & 1:
                    raise UnsupportedFormatError("Encrypted archive members are unsupported.")
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise UnsupportedFormatError("Unsupported archive compression.")
                total += info.file_size
                if info.file_size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                    raise FormatError("Decoded archive exceeds the size limit.")
                content = archive.read(info)  # zipfile verifies the member CRC.
                raw[name] = content
                inventory.append({"name": name, "bytes": len(content),
                                  "sha256": hashlib.sha256(content).hexdigest()})
            if "/sheet_metadata_20.json" not in raw:
                raise UnsupportedFormatError("The observed worksheet metadata member is absent.")
            metadata = _json(raw["/sheet_metadata_20.json"])
            if not isinstance(metadata, dict) or metadata.get("Version") != 20200604:
                raise UnsupportedFormatError("Unverified worksheet metadata version.")
            if not isinstance(metadata.get("Worksheet"), dict):
                raise FormatError("Worksheet metadata must be an object.")
            uri = metadata["Worksheet"].get("Uri")
            if not isinstance(uri, str) or not re.fullmatch(r"/sheets/\d+/sheet", uri):
                raise UnsupportedFormatError("Unsupported worksheet member URI.")
            member = uri + ".json"
            if member not in raw:
                raise FormatError("Worksheet data member is absent.")
            sheet = _json(raw[member])
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, OSError) as exc:
        raise FormatError("Cannot read worksheet archive: " + str(exc)) from exc
    try:
        if not isinstance(sheet, dict) or sheet.get("Version") != 20200604:
            raise UnsupportedFormatError("Unverified worksheet data version.")
        data = sheet["Data"]
        parsed = {}
        cells = 0
        for key, cls, vt in (("Columns", 434, 3), ("Constants", 435, 2), ("Matrices", 436, 4)):
            entries = data.get(key, [])
            if not isinstance(entries, list):
                raise FormatError(key + " must be an array.")
            parsed[key] = []
            for index, entry in enumerate(entries):
                column, width = _mwx_variable(entry, cls, vt, raw)
                # An unnamed imported variable still needs a usable original UI label.
                # Its exact empty source Name remains in imported_variable_metadata.
                if not column.name:
                    column.name = {"Columns": "C", "Constants": "K", "Matrices": "M"}[key] + str(index + 1)
                cells += len(column.values)
                if cells > MAX_CELLS:
                    raise FormatError("Worksheet exceeds the cell limit.")
                if key == "Matrices":
                    if column.kind != "number" or len(column.values) % width:
                        raise UnsupportedFormatError("Only regular numeric column-major matrices are supported.")
                    parsed[key].append(Matrix(column.name, len(column.values) // width, width,
                                              column.values, column.metadata))
                else:
                    if width != 1 or (key == "Constants" and len(column.values) != 1):
                        raise UnsupportedFormatError("Unsupported column/constant dimensions.")
                    parsed[key].append(column)
        non_data = {key: value for key, value in sheet.items() if key != "Data"}
        unimplemented = {key: value for key, value in data.items() if key not in parsed}
        warnings = ["Read-only import of one observed MWX schema; application roundtrip and MWX writing are unverified.",
                    "Original model/format/view metadata is retained but its behavior is not implemented.",
                    "Unrecognized package member bytes are not retained; names, hashes and sizes are retained."]
        return Worksheet(metadata["Worksheet"].get("Name", path.stem), parsed["Columns"],
                         parsed["Constants"], parsed["Matrices"],
                         {"import": {"format": "MWX", "version": 20200604, "warnings": warnings,
                          "metadata_document": metadata, "sheet_metadata": non_data,
                          "unsupported_payload_metadata": unimplemented,
                          "member_inventory": inventory}})
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, FormatError):
            raise
        raise FormatError("Malformed worksheet document: " + str(exc)) from exc


def save_mwx(*args, **kwargs):
    raise UnsupportedFormatError("MWX writing and application roundtrip compatibility have not been verified. Save a StatCraft project instead.")
