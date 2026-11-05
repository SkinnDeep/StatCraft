"""Core data types returned by `read_jmp`."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RowState:
    """A row's marker glyph and color, as set in JMP's row-state column."""

    marker: str
    color: tuple[float, float, float]


@dataclass(frozen=True)
class Column:
    """A single column from a JMP file: values plus per-column metadata.

    Known fields are first-class; everything else parsed from the file
    (spec limits, units, display format, role, etc.) goes into `extras`
    until it earns promotion. This keeps the public surface small while
    preserving information the parser recovers.
    """

    name: str
    values: list[Any]
    dtype: str | None = None
    notes: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)


class Table:
    """An ordered collection of named `Column`s. Returned by `read_jmp`.

    Dict-like value access: `table["col"]` -> the value list (matches
    most user expectations and pandas/polars indexing). To reach the
    metadata for a column use `table.column("col")`.

    `len(table)` returns the row count.
    """

    def __init__(self, columns: list[Column]) -> None:
        self._columns: list[Column] = list(columns)
        self._by_name: dict[str, Column] = {c.name: c for c in self._columns}
        if len(self._by_name) != len(self._columns):
            raise ValueError("duplicate column names in Table")

    @property
    def columns(self) -> list[str]:
        return [c.name for c in self._columns]

    def column(self, name: str) -> Column:
        return self._by_name[name]

    def __getitem__(self, name: str) -> list[Any]:
        return self._by_name[name].values

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def __iter__(self) -> Iterator[str]:
        return iter(self.columns)

    def __len__(self) -> int:
        if not self._columns:
            return 0
        return len(self._columns[0].values)

    def __repr__(self) -> str:
        return (
            f"Table({len(self)} rows x {len(self._columns)} cols: "
            f"{self.columns!r})"
        )

    def to_dict(self) -> dict[str, list[Any]]:
        return {c.name: list(c.values) for c in self._columns}

    def to_pandas(self):
        import pandas as pd

        return pd.DataFrame(self.to_dict())

    def to_polars(self):
        import polars as pl

        return pl.DataFrame(self.to_dict())

    def to_numpy(self) -> dict[str, "Any"]:
        import numpy as np

        return {c.name: np.array(c.values) for c in self._columns}

    def to_arrow(self):
        import pyarrow as pa

        return pa.table(self.to_dict())
