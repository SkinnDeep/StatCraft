"""Header and column-metadata parsing for .jmp files.

See docs/jmp_format.md §§2-4 for the format walkthrough; this module
ports `metadata.jl` and the relevant parts of `utils.jl`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ._constants import HEADER_ANCHOR, HEADER_REWIND_FROM_ANCHOR_END, JMP_EPOCH, MAGIC
from ._io import Reader

_SKIP_BLOCK_TAGS: frozenset[bytes] = frozenset(
    {b"\xfc\xff", b"\xfd\xff", b"\xfe\xff", b"\xff\xff"}
)

_MAX_HEADER_SCAN_ITERS: int = 100_000


@dataclass(frozen=True)
class FileMeta:
    nrows: int
    ncols: int
    charset: str
    savetime: datetime
    buildstring: str
    column_names: list[str]
    column_offsets: list[int]
    column_display_widths: list[int]


def check_magic(r: Reader) -> bool:
    r.seek(0)
    if r.remaining() < len(MAGIC):
        return False
    return r.read(len(MAGIC)) == MAGIC


def parse_metadata(r: Reader) -> FileMeta:
    if not check_magic(r):
        raise ValueError("not a .jmp file (magic mismatch)")

    r.seek(0)
    r.read_until(HEADER_ANCHOR)
    r.seek(r.tell() - HEADER_REWIND_FROM_ANCHOR_END)

    nrows = r.read_int64()
    ncols = r.read_int32()
    # StatCraft limits untrusted dimensions before allocating column arrays.
    from ..io import MAX_CELLS
    if nrows < 0 or not 1 <= ncols <= 10_000 or nrows * ncols > MAX_CELLS:
        raise ValueError("JMP table dimensions exceed import limits")
    r.read_array("h", 5)
    charset = r.read_length_prefixed_string(4).rstrip("\0")
    r.read_array("H", 3)
    savetime = JMP_EPOCH + timedelta(seconds=r.read_float64())
    r.read_uint16()
    buildstring = r.read_length_prefixed_string(4)

    n_visible, n_hidden = _find_column_offsets_section(r, ncols)
    r.read_array("I", n_visible)
    r.read_array("I", n_hidden)
    display_widths = r.read_array("H", ncols)
    r.read_array("I", 7)

    column_names, column_offsets = _parse_column_info(r, ncols)

    return FileMeta(
        nrows=nrows,
        ncols=ncols,
        charset=charset,
        savetime=savetime,
        buildstring=buildstring,
        column_names=column_names,
        column_offsets=column_offsets,
        column_display_widths=display_widths,
    )


def _find_column_offsets_section(r: Reader, ncols: int) -> tuple[int, int]:
    """Brute-force scan to align on the column-offsets section.

    Hacky by design — the upstream Julia code (`seek_to_column_data_offsets`)
    flags this as imperfect. False matches will likely surface on larger
    real-world files.
    """
    r.seek(2)
    for _ in range(_MAX_HEADER_SCAN_ITERS):
        try:
            r.read_until(b"\xff\xff")
        except ValueError:
            raise ValueError("could not find column-offsets section") from None
        while not r.at_eof() and r.peek(1) == b"\xff":
            r.skip(1)
        if r.remaining() < 26:
            raise ValueError("could not find column-offsets section")
        r.skip(10)
        n_visible = r.read_uint32()
        n_hidden = r.read_uint32()
        r.skip(8)
        if n_visible + n_hidden == ncols:
            return n_visible, n_hidden
        r.skip(-18)
    raise ValueError(
        f"column-offsets scan exceeded {_MAX_HEADER_SCAN_ITERS} candidate "
        f"positions; likely malformed file"
    )


def _parse_column_info(r: Reader, ncols: int) -> tuple[list[str], list[int]]:
    while True:
        tag = r.read(2)
        if tag in _SKIP_BLOCK_TAGS:
            n = r.read_int64()
            r.skip(n)
        else:
            r.skip(-2)
            break

    ncols2 = r.read_int32()
    if ncols2 != ncols:
        raise ValueError(
            f"column count mismatch: header says {ncols}, column_info says {ncols2}"
        )

    offsets = r.read_array("q", ncols)
    names: list[str] = []
    for off in offsets:
        r.seek(off)
        names.append(r.read_length_prefixed_string(2))
    return names, offsets
