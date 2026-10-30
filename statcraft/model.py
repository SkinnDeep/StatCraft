"""Original typed worksheet structures. Dates retain timezone-free day serials."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from typing import Any, Optional

KINDS = {"number", "text", "date"}
DATE_EPOCH = datetime(1899, 12, 30)


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("A numeric cell must contain a number or None.")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("The number is outside finite floating-point range.") from exc
    if not math.isfinite(value):
        raise ValueError("Nonfinite cells are unsupported; use None for missing data.")
    return value


def serial_to_datetime(value):
    """Nonnegative serial conversion only; negative OLE date rules are unverified."""
    value = finite_number(value)
    if value < 0:
        raise ValueError("Negative date serial display has not been verified.")
    try:
        return DATE_EPOCH + timedelta(days=value)
    except OverflowError as exc:
        raise ValueError("Date serial is outside the supported calendar range.") from exc


def display_date(value):
    """Original ISO display; preserve unsupported imported serials visibly."""
    try:
        date = serial_to_datetime(value)
    except ValueError:
        return str(value)
    if date.hour == date.minute == date.second == date.microsecond == 0:
        return date.date().isoformat()
    return date.isoformat(sep=' ', timespec='microseconds' if date.microsecond else 'seconds')


def datetime_to_serial(value):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError("Use a timezone-free datetime for date cells.")
    delta = value - DATE_EPOCH
    serial = delta.total_seconds() / 86400.0
    if serial < 0:
        raise ValueError("Dates before the serial epoch are unsupported for conversion.")
    return serial


@dataclass
class Column:
    name: str
    kind: str = "number"
    values: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or self.kind not in KINDS:
            raise ValueError("Invalid column name or type.")
        if not isinstance(self.values, list) or not isinstance(self.metadata, dict):
            raise ValueError("Column values and metadata must be a list and object.")
        self.validate()

    def validate(self):
        if self.kind not in KINDS:
            raise ValueError("Unsupported column type.")
        for value in self.values:
            if value is None:
                continue
            if self.kind == "text":
                if not isinstance(value, str):
                    raise ValueError("Text cells must contain strings or None.")
            else:
                finite_number(value)

    def numeric_values(self, include_missing=False):
        if self.kind != "number":
            raise ValueError("Select a numeric column for this analysis.")
        self.validate()
        return [None if v is None else float(v) for v in self.values
                if include_missing or v is not None]


@dataclass
class Matrix:
    name: str
    rows: int
    columns: int
    values: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not isinstance(self.metadata, dict):
            raise ValueError("Invalid matrix name or metadata.")
        if (type(self.rows) is not int or type(self.columns) is not int or
                self.rows < 0 or self.columns < 1 or
                not isinstance(self.values, list) or
                len(self.values) != self.rows * self.columns):
            raise ValueError("Matrix dimensions do not match its column-major values.")
        for value in self.values:
            if value is not None:
                finite_number(value)

    def cell(self, row, column):
        """Zero-based public coordinates; storage is explicitly column-major."""
        if not (0 <= row < self.rows and 0 <= column < self.columns):
            raise IndexError("Matrix coordinate is outside its dimensions.")
        return self.values[column * self.rows + row]

    def as_rows(self):
        return [[self.cell(r, c) for c in range(self.columns)] for r in range(self.rows)]


@dataclass
class Worksheet:
    name: str = "Worksheet"
    columns: list = field(default_factory=list)
    constants: list = field(default_factory=list)
    matrices: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    @property
    def row_count(self):
        return max((len(c.values) for c in self.columns), default=0)

    @property
    def headers(self):
        return [c.name for c in self.columns]

    def validate(self):
        if not isinstance(self.name, str) or not isinstance(self.metadata, dict):
            raise ValueError("Invalid worksheet name or metadata.")
        for entries in (self.columns, self.constants, self.matrices):
            if not isinstance(entries, list):
                raise ValueError("Worksheet collections must be lists.")
        if not all(isinstance(c, Column) for c in self.columns + self.constants):
            raise ValueError("Worksheet columns/constants must be Column objects.")
        if not all(isinstance(m, Matrix) for m in self.matrices):
            raise ValueError("Worksheet matrices must be Matrix objects.")
        for c in self.columns + self.constants:
            c.validate()
        if any(len(c.values) != 1 for c in self.constants):
            raise ValueError("A scalar constant must contain exactly one cell.")
        for matrix in self.matrices:
            matrix.__post_init__()

    def numeric_column(self, index, include_missing=False):
        return self.columns[index].numeric_values(include_missing)

    def row(self, index):
        if not 0 <= index < self.row_count:
            raise IndexError("Worksheet row is outside its dimensions.")
        return [c.values[index] if index < len(c.values) else None for c in self.columns]

    def complete_rows(self, indices):
        selected = [self.columns[i] for i in indices]
        if any(c.kind != "number" for c in selected):
            raise ValueError("Complete numeric rows require numeric columns.")
        result = []
        for row in range(self.row_count):
            cells = [c.values[row] if row < len(c.values) else None for c in selected]
            if all(v is not None for v in cells):
                result.append([finite_number(v) for v in cells])
        return result
