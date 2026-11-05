"""Per-column decoding dispatch.

See `docs/jmp_format.md` §6 for the dispatch on the six type bytes
(`t1..t6`) and §§7-10 for the encoding families. This module is the
single entry point that turns one column block into a `Column`.
"""

from __future__ import annotations

import gzip
import math
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from ._constants import GZIP_MARKER, JMP_EPOCH, ROWSTATE_COLORS, ROWSTATE_MARKERS
from ._io import Reader
from ._properties import parse_column_properties
from .table import Column, RowState

_INT_STRUCT_CHAR: Final[dict[int, str]] = {1: "b", 2: "h", 4: "i", 8: "q"}
_INT_SENTINEL: Final[dict[int, int]] = {
    1: -127,
    2: -32767,
    4: -2147483647,
    8: -9223372036854775807,
}

# Semantic-flavor dispatch on (t4, t5) for t1 == 0x01 columns. See
# `docs/jmp_format.md` §7. Order matters: a few codes appear in
# multiple sets, and the t4==t5 vs paired-tuple test disambiguates.

_NUMERIC_EQ: Final[frozenset[int]] = frozenset(
    {0x00, 0x03, 0x42, 0x43, 0x44, 0x59, 0x60, 0x63}
)
_NUMERIC_T5_ANY: Final[frozenset[int]] = frozenset({0x5E, 0x63})
_CURRENCY_EQ: Final[frozenset[int]] = frozenset({0x5F})
_LONGITUDE_EQ: Final[frozenset[int]] = frozenset({0x54, 0x55, 0x56})
_LATITUDE_EQ: Final[frozenset[int]] = frozenset({0x51, 0x52, 0x53})

_DATE_EQ: Final[frozenset[int]] = frozenset(
    {0x65, 0x66, 0x67, 0x6E, 0x6F, 0x70, 0x71, 0x72, 0x75, 0x76, 0x7A, 0x7F, 0x88, 0x8B}
)
_DATE_PAIRS: Final[frozenset[tuple[int, int]]] = frozenset(
    {
        (0x67, 0x65), (0x6F, 0x65), (0x72, 0x65), (0x72, 0x6F),
        (0x72, 0x7F), (0x72, 0x80), (0x7F, 0x72),
        (0x88, 0x65), (0x88, 0x7A),
    }
)

_DATETIME_T5: Final[frozenset[int]] = frozenset(
    {0x69, 0x6A, 0x73, 0x74, 0x77, 0x78, 0x7E, 0x81}
)
_DATETIME_T4: Final[frozenset[int]] = frozenset(
    {
        0x69, 0x6A, 0x6C, 0x6D, 0x73, 0x74, 0x77, 0x78, 0x79,
        0x7B, 0x7C, 0x7D, 0x7E, 0x80, 0x81, 0x82, 0x86, 0x87, 0x89, 0x8A,
    }
)
_DATETIME_EQ: Final[frozenset[int]] = frozenset({0x79, 0x7D})
_DATETIME_PAIRS: Final[frozenset[tuple[int, int]]] = frozenset(
    {(0x77, 0x80), (0x77, 0x7F), (0x89, 0x65)}
)

_TIME_EQ: Final[frozenset[int]] = frozenset({0x82})

_DURATION_EQ: Final[frozenset[int]] = frozenset(
    {0x0C, 0x6B, 0x6C, 0x6D, 0x83, 0x84, 0x85}
)
_DURATION_PAIRS: Final[frozenset[tuple[int, int]]] = frozenset({(0x84, 0x79)})


@dataclass(frozen=True)
class _TypeBytes:
    """The six type-discriminator bytes that follow a column's name."""

    t1: int
    t2: int
    t3: int
    t4: int
    t5: int
    t6: int


def decode_column(
    reader: Reader,
    nrows: int,
    column_offset: int,
    block_end: int,
) -> Column:
    """Decode the column block at `column_offset` into a `Column`.

    `block_end` is the file offset of the next column block (or EOF for
    the last column). For uncompressed columns, payloads sit in the
    column block directly; for compressed columns, the inflated buffer
    takes the place of the block for downstream decoding.
    """
    reader.seek(column_offset)
    name = reader.read_length_prefixed_string(2)
    types = _TypeBytes(*reader.read_array("B", 6))

    compressed = types.t1 in (0x09, 0x0A)
    raw_block = reader.buffer[column_offset:block_end]
    if compressed:
        data = _inflate_payload(reader, block_end, name)
    else:
        data = raw_block

    # Numeric / date / time / duration / currency / lat-long.
    # t1 == 0x01 (uncompressed) or 0x0a (compressed) — both share decoder.
    if types.t1 in (0x01, 0x0A):
        col = _decode_numeric_or_temporal(name, types, data, nrows)
        return _attach_properties(col, raw_block)

    # Byte integer — uncompressed only.
    if types.t1 in (0xFF, 0xFE, 0xFC):
        values = _read_trailing_ints(data, nrows, types.t5)
        col = Column(name=name, values=values, dtype=f"int{types.t5 * 8}")
        return _attach_properties(col, raw_block)

    # Character columns. t1 == 0x02 uncompressed, 0x09 compressed.
    if types.t1 in (0x02, 0x09) and types.t2 in (0x01, 0x02):
        col = _decode_character(reader, name, types, raw_block, data, nrows, compressed)
        return _attach_properties(col, raw_block)

    if types.t1 in (0x03, 0x09) and types.t2 == 0x03:
        col = _decode_rowstate(name, data, nrows, types.t5)
        return _attach_properties(col, raw_block)

    raise NotImplementedError(
        f"column type bytes "
        f"({types.t1:#04x},{types.t2:#04x},{types.t3:#04x},"
        f"{types.t4:#04x},{types.t5:#04x},{types.t6:#04x}) "
        f"not yet supported (column {name!r})"
    )


def _attach_properties(col: Column, raw_block: bytes) -> Column:
    """Scan the raw column block for named properties and fold them
    into `col.notes` and `col.extras`. Leaves `col` alone if nothing is
    found, so columns without properties stay dep-free.
    """
    notes, extras = parse_column_properties(raw_block)
    if notes is None and not extras:
        return col
    from dataclasses import replace

    return replace(col, notes=notes, extras=extras)


def _inflate_payload(reader: Reader, block_end: int, name: str) -> bytes:
    """Locate the gzip section in this column block and return inflated bytes.

    Format (docs §8): marker `ef be fe ca`, UInt64 gzlen, UInt64 unlen,
    then `gzlen` bytes of standard gzip stream.
    """
    buf = reader.buffer
    idx = buf.find(GZIP_MARKER, reader.tell(), block_end)
    if idx < 0:
        raise ValueError(
            f"gzip marker not found in compressed column {name!r}"
        )
    gzlen = struct.unpack_from("<Q", buf, idx + 4)[0]
    unlen = struct.unpack_from("<Q", buf, idx + 12)[0]
    stream_start = idx + 20
    stream_end = stream_start + gzlen
    if stream_end > len(buf):
        raise ValueError(
            f"gzip stream truncated in column {name!r}: "
            f"declared gzlen={gzlen} runs past file end "
            f"({stream_end - len(buf)} bytes short)"
        )
    try:
        inflated = gzip.decompress(buf[stream_start:stream_end])
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise ValueError(
            f"gzip decompress failed in column {name!r} "
            f"(gzlen={gzlen}, declared unlen={unlen}): {exc}"
        ) from exc
    if len(inflated) != unlen:
        raise ValueError(
            f"gzip length mismatch in column {name!r}: "
            f"declared unlen={unlen}, decompressed={len(inflated)}"
        )
    return inflated


def _decode_numeric_or_temporal(
    name: str, types: _TypeBytes, data: bytes, nrows: int
) -> Column:
    """`t1 == 0x01` family: width from `t6`, semantics from `(t4, t5)`."""
    if types.t6 in (1, 2, 4):
        values = _read_trailing_ints(data, nrows, types.t6)
        return Column(name=name, values=values, dtype=f"int{types.t6 * 8}")

    raw = _read_trailing_floats(data, nrows)
    flavor = _classify_temporal(types.t4, types.t5)

    if flavor == "numeric":
        return Column(name=name, values=raw, dtype="float64")
    if flavor in ("date", "datetime", "time"):
        return Column(name=name, values=_to_datetimes(raw), dtype=flavor)
    if flavor == "duration":
        return Column(name=name, values=_to_durations(raw), dtype="duration")
    raise AssertionError(f"unhandled flavor {flavor!r}")


def _classify_temporal(t4: int, t5: int) -> str:
    """Map `(t4, t5)` to a semantic flavor.

    Returns one of `"numeric"`, `"date"`, `"datetime"`, `"time"`,
    `"duration"`. Unrecognized codes fall through as `"numeric"` so the
    raw Float64 values still reach the caller.
    """
    if t4 == t5 and t4 in _NUMERIC_EQ:
        return "numeric"
    if t5 in _NUMERIC_T5_ANY:
        return "numeric"
    if t4 == t5 and (
        t4 in _CURRENCY_EQ or t4 in _LONGITUDE_EQ or t4 in _LATITUDE_EQ
    ):
        return "numeric"

    if (t4 == t5 and t4 in _DATE_EQ) or (t4, t5) in _DATE_PAIRS:
        return "date"

    if (
        (t5 in _DATETIME_T5 and t4 in _DATETIME_T4)
        or (t4 == t5 and t4 in _DATETIME_EQ)
        or (t4, t5) in _DATETIME_PAIRS
    ):
        return "datetime"

    if t4 == t5 and t4 in _TIME_EQ:
        return "time"

    if (t4 == t5 and t4 in _DURATION_EQ) or (t4, t5) in _DURATION_PAIRS:
        return "duration"

    return "numeric"


def _to_datetimes(values: list[float | None]) -> list[datetime | None]:
    """All temporal flavors except duration share this lossless conversion.

    JMP stores date / datetime / time as Float64 seconds since 1904; the
    flavor tag controls *display* but not storage, so we keep the full
    precision and let the dtype label preserve display intent. Round to
    microseconds to align with `datetime`'s native precision.
    """
    return [
        None if v is None else JMP_EPOCH + timedelta(seconds=v) for v in values
    ]


def _to_durations(values: list[float | None]) -> list[timedelta | None]:
    return [None if v is None else timedelta(seconds=v) for v in values]


# ----------------------------------------------------------------------
# Character columns. See `docs/jmp_format.md` §9.
# ----------------------------------------------------------------------

_VAR_WIDTH_CHAR: Final[dict[int, str]] = {1: "b", 2: "h", 4: "i"}


def _decode_character(
    reader: Reader,
    name: str,
    types: _TypeBytes,
    raw_block: bytes,
    data: bytes,
    nrows: int,
    compressed: bool,
) -> Column:
    """Dispatch on (t3, t4, t5) within the character family.

    `raw_block` is always the original column block. `data` equals
    `raw_block` for uncompressed columns and the inflated buffer for
    compressed ones.
    """
    # Pooled-string variant (§9.4): pool layout always lives in the
    # uncompressed block body. For uncompressed columns the indices
    # follow the pool inside the same body. For compressed columns
    # (the §9.4 analog seen in Hurricanes.jmp / Auto Raw Data.jmp)
    # the indices are the entire inflated buffer. Without this
    # discriminator the constwidth branch below would silently emit
    # raw index bytes as 1-char strings.
    if types.t3 == 0 and types.t4 == 0 and types.t5 in _POOL_INDEX_FMT:
        body = _column_body(raw_block)
        if _looks_uncompressed_pooled(body):
            if compressed:
                return _decode_pooled_string_with_inflated_indices(
                    name, body, data, nrows, types.t5
                )
            return _decode_uncompressed_pooled_string(name, body, nrows, types.t5)

    constant_width = (
        (types.t3 == 0 and types.t4 == 0 and types.t5 > 0)
        or (1 <= types.t3 <= 7 and types.t4 == 0)
    )
    if constant_width:
        return _decode_constant_width_string(name, types.t5, data, nrows)

    if types.t3 == 0 and types.t4 == 0 and types.t5 == 0:
        if compressed:
            return _decode_variable_width_string_compressed(name, data, nrows)
        return _decode_variable_width_string_uncompressed(reader, name, data, nrows)

    raise NotImplementedError(
        f"unrecognized character (t3,t4,t5) = "
        f"({types.t3:#04x},{types.t4:#04x},{types.t5:#04x}) in column {name!r}"
    )


def _column_body(data: bytes) -> bytes:
    """Slice past the column header (Int16 name length + name + 6 type bytes)
    so callers see the post-header body directly.
    """
    name_len = struct.unpack_from("<h", data)[0]
    return data[2 + name_len + 6 :]


def _looks_uncompressed_pooled(body: bytes) -> bool:
    """Structural fingerprint of the uncompressed pooled-string layout
    (§9.4):

      - bytes 0..3   = 0x00000000
      - bytes 4..5   = tag1 (UInt16 LE), non-zero — observed values 1, 3, 4
      - bytes 14..15 = 0x0004 (pool record marker)

    The non-zero tag1 check rejects look-alike constwidth columns whose
    body happens to lead with many zeros and incidentally has 0x0004 at
    offset 14.
    """
    return (
        len(body) >= 26
        and body[:4] == b"\x00\x00\x00\x00"
        and body[4:6] != b"\x00\x00"
        and body[14:16] == b"\x04\x00"
    )


def _decode_constant_width_string(
    name: str, width: int, data: bytes, nrows: int
) -> Column:
    """Each row is exactly `width` bytes, trailing nulls stripped.

    Raises NotImplementedError if the decoded text is dominated by C0
    control bytes — a strong signal that the dispatcher picked constwidth
    for what is actually some other character variant. Pre-fix, columns
    using the §9.4 uncompressed-pooled layout were silently decoded here
    as 1-char strings of raw pool indices; the check makes that visible.
    """
    raw = data[-nrows * width :]
    values = [
        raw[i * width : (i + 1) * width].rstrip(b"\x00").decode("utf-8")
        for i in range(nrows)
    ]
    if not _looks_like_text(values):
        raise NotImplementedError(
            f"column {name!r}: constwidth (width={width}) decoded as "
            f"non-text bytes — likely an unrecognized character variant "
            f"misdispatched as constwidth"
        )
    return Column(name=name, values=values, dtype="string")


def _looks_like_text(values: list[str], threshold: float = 0.80) -> bool:
    """Return True if non-empty cell content is mostly printable.

    Counts C0 control characters (codepoints < 0x20) other than tab,
    newline, and carriage return — those three appear in legitimate
    cell text. An all-empty column (every cell stripped to "") carries
    no signal and passes.
    """
    total = 0
    bad = 0
    for v in values:
        for ch in v:
            total += 1
            if ch < " " and ch not in "\t\n\r":
                bad += 1
    if total == 0:
        return True
    return bad / total <= threshold


def _decode_variable_width_string_uncompressed(
    reader: Reader, name: str, block: bytes, nrows: int
) -> Column:
    """Per-row lengths follow a small preamble in the column block;
    payload is the trailing `sum(widths)` bytes of the block.
    """
    reader.skip(6)
    n1 = reader.read_int64()
    reader.skip(n1)
    reader.skip(2)
    n2 = reader.read_uint32()
    reader.skip(n2 + 8)

    width_bytes = reader.read_uint8()
    if width_bytes not in _VAR_WIDTH_CHAR:
        raise ValueError(
            f"unexpected variable-width string width_bytes={width_bytes!r} "
            f"in column {name!r}"
        )
    reader.read_uint32()  # max_width — informational, not needed
    widths = reader.read_array(_VAR_WIDTH_CHAR[width_bytes], nrows)

    return _materialize_variable_strings(name, block, widths)


def _decode_variable_width_string_compressed(
    name: str, data: bytes, nrows: int
) -> Column:
    """Compressed variable-width strings live entirely in the inflated
    buffer. Pooled encoding (§9.3) is signaled by the first 8 bytes
    equaling the buffer length — split out for a separate decoder.
    """
    if len(data) >= 8 and struct.unpack_from("<q", data)[0] == len(data):
        return _decode_pooled_string(name, data, nrows)

    width_bytes = data[8]
    if width_bytes not in _VAR_WIDTH_CHAR:
        raise ValueError(
            f"unexpected compressed-string width_bytes={width_bytes!r} "
            f"in column {name!r}"
        )
    fmt = _VAR_WIDTH_CHAR[width_bytes]
    size = struct.calcsize("<" + fmt)
    widths_end = 13 + nrows * size
    widths = struct.unpack(f"<{nrows}{fmt}", data[13:widths_end])
    payload = data[widths_end:]
    return _materialize_variable_strings(name, payload, widths)


# Pool index width (UInt8/16/32) and string-length width (Int8/16) per §9.3.
_POOL_INDEX_FMT: Final[dict[int, str]] = {1: "B", 2: "H", 4: "I"}
_POOL_LENGTH_FMT: Final[dict[int, str]] = {1: "b", 2: "h"}


def _decode_pooled_string(name: str, data: bytes, nrows: int) -> Column:
    """Pooled string decoding per docs §9.3.

    Layout: Int64 rec_length, 9 ignored bytes, Int64 (pool size hint —
    we use `max(indices)` instead since it's unambiguous), Int8
    `index_bytes`, `nrows` indices, Int8 `length_bytes`, then
    `max(indices)` pool entries each prefixed by its length. Index 0 is
    the empty string; index N>0 selects pool entry N-1.
    """
    index_bytes = data[25]
    if index_bytes not in _POOL_INDEX_FMT:
        raise ValueError(
            f"unexpected pooled-string index_bytes={index_bytes!r} in column {name!r}"
        )
    ifmt = _POOL_INDEX_FMT[index_bytes]
    isize = struct.calcsize("<" + ifmt)
    indices_end = 26 + nrows * isize
    indices = struct.unpack(f"<{nrows}{ifmt}", data[26:indices_end])

    length_bytes = data[indices_end]
    if length_bytes not in _POOL_LENGTH_FMT:
        raise ValueError(
            f"unexpected pooled-string length_bytes={length_bytes!r} in column {name!r}"
        )
    lfmt = _POOL_LENGTH_FMT[length_bytes]
    lsize = struct.calcsize("<" + lfmt)

    pool: list[str] = []
    pos = indices_end + 1
    for _ in range(max(indices, default=0)):
        (slen,) = struct.unpack_from("<" + lfmt, data, pos)
        pos += lsize
        pool.append(data[pos : pos + slen].decode("utf-8"))
        pos += slen

    values = ["" if idx == 0 else pool[idx - 1] for idx in indices]
    return Column(name=name, values=values, dtype="string")


def _parse_pool_from_body(body: bytes, name: str) -> list[str]:
    """Extract the §9.4 string pool from the column block body.

    Pool layout (offsets within body):
      bytes 0-3   : zeros
      bytes 4-5   : tag1 (UInt16, observed values 1, 3, 4 — semantics unknown)
      bytes 6-13  : len1 (UInt64 — section size, not used here)
      bytes 14-15 : tag2 = 0x0004 (pool record marker)
      bytes 16-23 : pool_size (UInt64) — bytes covering pool_count + entries
      bytes 24-25 : pool_count (UInt16)
      pool_size-2 bytes of null-terminated entries

    Used by both uncompressed §9.4 (indices follow the pool in the body)
    and the compressed §9.4 analog (indices live in the inflated buffer).
    """
    pool_size = struct.unpack_from("<Q", body, 16)[0]
    pool_count = struct.unpack_from("<H", body, 24)[0]
    pool_data = body[26 : 26 + pool_size - 2]
    entries = pool_data.split(b"\x00")
    if len(entries) < pool_count:
        raise ValueError(
            f"pooled-string pool truncated in column {name!r}: "
            f"expected {pool_count} entries, found {len(entries)}"
        )
    return [e.decode("utf-8") for e in entries[:pool_count]]


def _apply_pool_indices(
    pool: list[str], buf: bytes, nrows: int, index_bytes: int
) -> list[str | None]:
    """Read `nrows` indices from the trailing bytes of `buf` and resolve
    them through `pool`. Sentinel = all-ones of `index_bytes` width.
    """
    if nrows == 0:
        return []
    fmt = _POOL_INDEX_FMT[index_bytes]
    idx_total = nrows * index_bytes
    indices = struct.unpack(f"<{nrows}{fmt}", buf[len(buf) - idx_total :])
    sentinel = (1 << (index_bytes * 8)) - 1
    return [None if i == sentinel else pool[i] for i in indices]


def _decode_uncompressed_pooled_string(
    name: str, body: bytes, nrows: int, index_bytes: int
) -> Column:
    """Uncompressed pooled-string variant (§9.4).

    Pool and per-row indices both live in `body`: pool at the start
    (per `_parse_pool_from_body`), trailing nrows*index_bytes bytes are
    the 0-based indices. Indexing is 0-based; all-ones is the missing
    sentinel. Distinct from §9.3 which is 1-based with 0 == "".
    """
    pool = _parse_pool_from_body(body, name)
    values = _apply_pool_indices(pool, body, nrows, index_bytes)
    return Column(name=name, values=values, dtype="string")


def _decode_pooled_string_with_inflated_indices(
    name: str, body: bytes, inflated: bytes, nrows: int, index_bytes: int
) -> Column:
    """Compressed analog of §9.4: pool layout in the uncompressed block
    body, indices in the inflated gzip buffer.

    Observed in Hurricanes.jmp `Time` (4-entry pool of synoptic times)
    and Auto Raw Data.jmp `Claim(Y/N)` (2-entry Y/N pool). The inflated
    buffer for these is exactly nrows*index_bytes — no preamble or
    padding — so the trailing-slice in `_apply_pool_indices` returns
    the whole thing.
    """
    pool = _parse_pool_from_body(body, name)
    values = _apply_pool_indices(pool, inflated, nrows, index_bytes)
    return Column(name=name, values=values, dtype="string")


def _materialize_variable_strings(
    name: str, payload: bytes, widths
) -> Column:
    """Slice `payload` into per-row strings using `widths` as a length cursor.

    For uncompressed columns `payload` is the full column block and we
    take `sum(widths)` bytes from its tail. For compressed columns the
    payload buffer already starts at the first byte of string data.
    """
    total = sum(widths)
    if total < len(payload):
        payload = payload[-total:]
    values: list[str] = []
    pos = 0
    for w in widths:
        values.append(payload[pos : pos + w].decode("utf-8"))
        pos += w
    return Column(name=name, values=values, dtype="string")


# ----------------------------------------------------------------------
# Row state. See `docs/jmp_format.md` §10.
# ----------------------------------------------------------------------


def _decode_rowstate(name: str, data: bytes, nrows: int, width: int) -> Column:
    """Each row is `width` bytes. Marker index = bytes (5,6) little-endian;
    palette markers if ≤ 0x1f, otherwise raw Unicode codepoint. Color
    flag at byte 3: 0xff → custom RGB in bytes (2,1,0); else palette
    color indexed by byte 0.
    """
    raw = data[-nrows * width :]
    values: list[RowState] = []
    for i in range(nrows):
        row = raw[i * width : (i + 1) * width]
        marker_idx = (row[6] << 8) | row[5]
        marker = (
            ROWSTATE_MARKERS[marker_idx] if marker_idx <= 0x1F else chr(marker_idx)
        )
        if row[3] == 0xFF:
            color = (row[2] / 255.0, row[1] / 255.0, row[0] / 255.0)
        else:
            color = _hex_to_rgb(ROWSTATE_COLORS[row[0]])
        values.append(RowState(marker=marker, color=color))
    return Column(name=name, values=values, dtype="rowstate")


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    s = hex_color.lstrip("#")
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)


def _read_trailing_ints(data: bytes, nrows: int, width: int) -> list[int | None]:
    if nrows == 0:
        return []
    fmt_char = _INT_STRUCT_CHAR[width]
    sentinel = _INT_SENTINEL[width]
    raw = data[-nrows * width :]
    values = struct.unpack(f"<{nrows}{fmt_char}", raw)
    return [None if v == sentinel else v for v in values]


def _read_trailing_floats(data: bytes, nrows: int) -> list[float | None]:
    if nrows == 0:
        return []
    raw = data[-nrows * 8 :]
    values = struct.unpack(f"<{nrows}d", raw)
    return [None if math.isnan(v) else v for v in values]
