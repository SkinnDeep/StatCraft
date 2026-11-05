"""jumpio — read JMP (.jmp) data files."""

import mmap
from collections.abc import Iterable
from os import PathLike
from pathlib import Path

from ._columns import decode_column
from ._io import Reader
from ._metadata import parse_metadata
from .table import Column, RowState, Table

__version__ = "0.1.0"

__all__ = ["__version__", "read_jmp", "Table", "Column", "RowState"]


def read_jmp(
    path: str | PathLike[str],
    *,
    select: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> Table:
    """Decode a `.jmp` file into a `Table`.

    The file is memory-mapped read-only; only pages we actually touch
    (header, column-offsets, plus each column block we decode) are
    paged into RSS. After decode all column values are materialized as
    plain Python lists, so the mmap is released before this call
    returns and the `Table` carries no file-handle dependency.

    `select` keeps only the named columns; `exclude` drops them. Pass
    one or the other, not both. Output is always in source order
    regardless of the order names appear in `select`. Unknown or
    duplicated names raise `ValueError`.
    """
    fpath = Path(path)
    if fpath.stat().st_size == 0:
        raise ValueError(f"{fpath}: file is empty")
    with open(fpath, "rb") as fh, mmap.mmap(  # noqa: SIM117
        fh.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        reader = Reader(data)
        meta = parse_metadata(reader)
        keep = _resolve_keep_set(meta.column_names, select, exclude)

        columns: list[Column] = []
        for i, off in enumerate(meta.column_offsets):
            if i not in keep:
                continue
            block_end = (
                meta.column_offsets[i + 1] if i + 1 < meta.ncols else len(data)
            )
            columns.append(decode_column(reader, meta.nrows, off, block_end))

    return Table(columns)


def _resolve_keep_set(
    column_names: list[str],
    select: Iterable[str] | None,
    exclude: Iterable[str] | None,
) -> set[int]:
    """Resolve `select`/`exclude` against the file's column names.

    Returns the set of column indices to decode. Validates that names
    exist and are not duplicated, so typos surface immediately rather
    than silently dropping or keeping the wrong column.
    """
    if select is not None and exclude is not None:
        raise ValueError("pass `select` or `exclude`, not both")

    name_to_index = {name: i for i, name in enumerate(column_names)}

    def _resolve(names: Iterable[str], kw: str) -> list[int]:
        seen: set[str] = set()
        indices: list[int] = []
        unknown: list[str] = []
        dups: list[str] = []
        for name in names:
            if name in seen:
                dups.append(name)
                continue
            seen.add(name)
            if name not in name_to_index:
                unknown.append(name)
            else:
                indices.append(name_to_index[name])
        if unknown:
            raise ValueError(
                f"{kw}: unknown column name(s) {unknown!r}; "
                f"file has {column_names!r}"
            )
        if dups:
            raise ValueError(f"{kw}: duplicate column name(s) {dups!r}")
        return indices

    if select is not None:
        return set(_resolve(select, "select"))
    if exclude is not None:
        drop = set(_resolve(exclude, "exclude"))
        return {i for i in range(len(column_names)) if i not in drop}
    return set(range(len(column_names)))
