"""Read supported JMP binary tables and literal JSL table exports."""

import math
import mmap
import re
import struct
from datetime import timedelta
from pathlib import Path

from . import io
from ._vendor_jumpio import decode_column, parse_metadata, Reader
from ._vendor_jumpio._constants import MAGIC
from .model import Column, Worksheet, datetime_to_serial


class JmpParseError(ValueError):
    """A corrupt or unsupported JMP table."""


def is_jmp_file(filepath):
    path = Path(filepath)
    if path.suffix.lower() in (".jmp", ".jsl"):
        return True
    try:
        with path.open("rb") as source:
            return source.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def load_jmp(filepath):
    path = Path(filepath)
    try:
        size = path.stat().st_size
        if not 0 < size <= io.MAX_TOTAL_BYTES:
            raise ValueError("The file is empty or exceeds the import size limit.")
        with path.open("rb") as source:
            if path.suffix.lower() == ".jsl":
                return _parse_jsl_table(source.read().decode("utf-8-sig"), path.stem)
            with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as raw:
                return _parse_jmp_binary(raw, path.stem)
    except (OSError, ValueError, NotImplementedError, ArithmeticError, TypeError, IndexError, struct.error) as exc:
        raise JmpParseError(f"Could not open {path.name}. {exc}") from exc


def _parse_jmp_binary(raw, table_name):
    try:
        reader = Reader(raw)
        info = parse_metadata(reader)
        _check_size(info.nrows, info.ncols)
        offsets = info.column_offsets + [len(raw)]
        if any(start < 0 or start >= end for start, end in zip(offsets, offsets[1:])):
            raise ValueError("Invalid column offsets.")
        columns = []
        for index, name in enumerate(info.column_names):
            decoded = decode_column(reader, info.nrows, offsets[index], offsets[index + 1])
            if decoded.name != name or len(decoded.values) != info.nrows:
                raise ValueError(f"Invalid data for column {name}.")
            values = decoded.values
            kind = "number"
            if decoded.dtype in ("date", "datetime", "time"):
                kind = "date"
                values = [datetime_to_serial(value) if value is not None else None for value in values]
            elif decoded.dtype == "duration":
                values = [value.total_seconds() if isinstance(value, timedelta) else None for value in values]
            elif decoded.dtype == "rowstate":
                kind = "text"
                values = [value.marker if value is not None else None for value in values]
            elif decoded.dtype == "string":
                kind = "text"
            else:
                values = [value if value is None or math.isfinite(value) else None for value in values]
            metadata = {"source_format": "jmp", "jmp_storage": decoded.dtype}
            if decoded.notes:
                metadata["description"] = decoded.notes
            specs = decoded.extras.get("spec_limits", {})
            limits = {key.lower(): value for key, value in specs.items()
                      if key.lower() in ("lsl", "usl", "target")
                      and isinstance(value, (int, float)) and math.isfinite(value)}
            if limits:
                metadata["spec_limits"] = limits
            columns.append(Column(name, kind, values, metadata))
        sheet = Worksheet(table_name, columns, metadata={"source_format": "jmp"})
        sheet.validate()
        return sheet
    except (ValueError, NotImplementedError, ArithmeticError, TypeError, IndexError, struct.error) as exc:
        raise JmpParseError(str(exc)) from exc


_TOKEN = re.compile(r'''\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'|[A-Za-z_]\w*|[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?|[^\s]''')
_PAIRS = {"(": ")", "[": "]", "{": "}"}


def _check_size(rows, columns):
    if rows < 0 or not 1 <= columns <= 10_000 or rows * columns > io.MAX_CELLS:
        raise ValueError("The table dimensions exceed the import limits.")


def _arguments(tokens, opening):
    stack = [_PAIRS[tokens[opening]]]
    pieces = []
    start = opening + 1
    for i in range(start, len(tokens)):
        token = tokens[i]
        if token in _PAIRS:
            stack.append(_PAIRS[token])
        elif token in _PAIRS.values():
            if token != stack.pop():
                raise JmpParseError("Unbalanced delimiters in JSL table.")
            if not stack:
                if i > start or pieces:
                    pieces.append(tokens[start:i])
                return pieces, i
        elif token == "," and len(stack) == 1:
            pieces.append(tokens[start:i])
            start = i + 1
    raise JmpParseError("Incomplete JSL table expression.")


def _quoted(token):
    return len(token) >= 2 and token[0] in ('"', "'") and token[-1] == token[0]


def _text(token):
    if not _quoted(token):
        raise JmpParseError("A literal string is required.")
    return (token[1:-1].replace(r'\!"', '"').replace(r'\!n', '\n')
            .replace(r'\!t', '\t').replace(r'\"', '"').replace(r"\'", "'"))


def _call(tokens, *name):
    return (len(tokens) > len(name) and tokens[len(name)] == "("
            and [token.casefold() for token in tokens[:len(name)]] == list(name))


def _literal(tokens, kind):
    if not tokens or tokens == ["."]:
        return None
    if len(tokens) != 1:
        raise JmpParseError("Only literal JSL table values are supported.")
    if kind == "text":
        return _text(tokens[0])
    value = float(tokens[0])
    if not math.isfinite(value):
        raise JmpParseError("Nonfinite numeric JSL value.")
    return value


def _parse_jsl_table(text, default_name):
    tokens = [token for token in _TOKEN.findall(text)
              if not token.isspace() and not token.startswith(("//", "/*"))]
    starts = [i for i in range(len(tokens) - 2)
              if _call(tokens[i:i + 3], "new", "table")]
    if len(starts) != 1:
        raise JmpParseError("Expected one literal JSL New Table expression.")
    args, _ = _arguments(tokens, starts[0] + 2)
    if not args or len(args[0]) != 1:
        raise JmpParseError("Expected a literal JSL table name.")
    table_name = _text(args[0][0]) or default_name
    rows = 0
    columns = []
    for arg in args[1:]:
        if _call(arg, "add", "rows"):
            fields, _ = _arguments(arg, 2)
            if len(fields) != 1 or len(fields[0]) != 1:
                raise JmpParseError("Expected a literal row count.")
            rows += int(fields[0][0])
        if not _call(arg, "new", "column"):
            continue
        fields, _ = _arguments(arg, 2)
        if not fields or len(fields[0]) != 1:
            raise JmpParseError("Expected a literal column name.")
        name = _text(fields[0][0])
        kind = "text" if any([t.lower() for t in part] == ["character"] for part in fields) else "number"
        values = []
        metadata = {"source_format": "jmp_jsl"}
        for field in fields[1:]:
            if _call(field, "set", "values"):
                if len(field) < 5 or field[3] not in ("[", "{"):
                    raise JmpParseError("Expected a literal JSL value list.")
                items, end = _arguments(field, 3)
                if end != len(field) - 2:
                    raise JmpParseError("Only literal JSL value lists are supported.")
                values = [_literal(item, kind) for item in items]
            elif _call(field, "set", "property") and len(field) > 6 and field[3].lower() == '"spec limits"' and field[5] == "{":
                properties, _ = _arguments(field, 5)
                specs = {}
                for item in properties:
                    if len(item) == 4 and item[0].lower() in ("lsl", "usl", "target"):
                        value = _literal(item[2:3], "number")
                        if value is not None:
                            specs[item[0].lower()] = value
                if specs:
                    metadata["spec_limits"] = specs
        columns.append(Column(name, kind, values, metadata))
    if rows < 0:
        raise JmpParseError("The row count must be nonnegative.")
    rows = max(rows, max((len(column.values) for column in columns), default=0))
    _check_size(rows, len(columns))
    for column in columns:
        column.values.extend([None] * (rows - len(column.values)))
    sheet = Worksheet(table_name, columns, metadata={"source_format": "jmp_jsl"})
    sheet.validate()
    return sheet
