"""Cursor-based reader over an in-memory bytes buffer.

Mirrors the seek/tell/read shape of Julia's `IO` so JMPReader.jl
translations stay mechanical. Backed by either `bytes` (test buffers)
or `mmap.mmap` (production read path) — both expose the buffer
protocol and `find()`, so callers don't need to care.
"""

from __future__ import annotations

import math
import mmap
import struct
from typing import Any, Final, Union

_Buffer = Union[bytes, mmap.mmap]


class Reader:
    __slots__ = ("_data", "_pos")

    def __init__(self, data: _Buffer) -> None:
        self._data: _Buffer = data
        self._pos: int = 0

    @property
    def buffer(self) -> _Buffer:
        return self._data

    def __len__(self) -> int:
        return len(self._data)

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int) -> None:
        self._pos = pos

    def skip(self, n: int) -> None:
        self._pos += n

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def at_eof(self) -> bool:
        return self._pos >= len(self._data)

    def peek(self, n: int = 1) -> bytes:
        return self._data[self._pos : self._pos + n]

    def read(self, n: int) -> bytes:
        end = self._pos + n
        out = self._data[self._pos : end]
        if len(out) != n:
            raise EOFError(
                f"requested {n} bytes at offset {self._pos}, "
                f"only {len(out)} available (file size {len(self._data)})"
            )
        self._pos = end
        return out

    def _unpack(self, fmt: str, n: int) -> Any:
        (val,) = struct.unpack(fmt, self.read(n))
        return val

    def read_int8(self) -> int: return self._unpack("<b", 1)
    def read_int16(self) -> int: return self._unpack("<h", 2)
    def read_int32(self) -> int: return self._unpack("<i", 4)
    def read_int64(self) -> int: return self._unpack("<q", 8)
    def read_uint8(self) -> int: return self._unpack("<B", 1)
    def read_uint16(self) -> int: return self._unpack("<H", 2)
    def read_uint32(self) -> int: return self._unpack("<I", 4)
    def read_uint64(self) -> int: return self._unpack("<Q", 8)
    def read_float64(self) -> float: return self._unpack("<d", 8)

    def read_array(self, fmt: str, n: int) -> list[Any]:
        """Read `n` values of single-char struct format `fmt` (little-endian)."""
        size = struct.calcsize("<" + fmt)
        raw = self.read(n * size)
        return list(struct.unpack(f"<{n}{fmt}", raw))

    def read_until(self, sep: bytes) -> bytes:
        """Read bytes through `sep` (cursor lands just after the match).

        Returns the bytes that preceded `sep` (not including `sep`).
        """
        idx = self._data.find(sep, self._pos)
        if idx < 0:
            raise ValueError(
                f"separator {sep.hex()!r} not found from offset {self._pos}"
            )
        out = self._data[self._pos : idx]
        self._pos = idx + len(sep)
        return out

    def read_length_prefixed_string(self, width: int) -> str:
        """Read a UTF-8 string prefixed by a signed length of `width` bytes (1, 2, or 4)."""
        if width == 1:
            n = self.read_int8()
        elif width == 2:
            n = self.read_int16()
        elif width == 4:
            n = self.read_int32()
        else:
            raise ValueError(f"invalid string-length width {width!r}")
        return self.read(n).decode("utf-8")


_INT_SENTINELS: Final[dict[int, int]] = {
    1: -127,
    2: -32767,
    4: -2147483647,
    8: -9223372036854775807,
}


def replace_int_sentinel(values: list[int], width: int) -> list[int | None]:
    s = _INT_SENTINELS[width]
    return [None if v == s else v for v in values]


def replace_float_nan(values: list[float]) -> list[float | None]:
    return [None if isinstance(v, float) and math.isnan(v) else v for v in values]
