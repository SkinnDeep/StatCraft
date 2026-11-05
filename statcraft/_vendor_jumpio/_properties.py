"""Column-property decoding (notes, formulas, spec limits, ...).

JMP stores a few user-visible attributes per column inside the column
block as length-prefixed JSL function-call strings, e.g.::

    Notes("free-form text")
    Spec Limits({LSL(347.5), USL(352.5), Target(350), Show Limits(1)})
    Formula(Sqrt(:X))

Each property string is preceded by a UInt32 little-endian byte count.
We scan the raw column buffer for known property names and read each
as a length-prefixed slice. This is heuristic but robust against the
header-layout variation we have not fully reverse-engineered (see
``docs/jmp_format.md`` §6 open questions).
"""

from __future__ import annotations

import struct
from typing import Any

# JMP property names we recognize. Unknown ones go into
# ``extras["properties"]`` keyed by their JSL name. Order does not
# matter — each name is searched independently.
_KNOWN_PROPERTY_NAMES: tuple[str, ...] = (
    "Notes",
    "Localized Notes",
    "Spec Limits",
    "Response Limits",
    "Formula",
    "Long Name",
    "Units",
    "Range Check",
    "Value Labels",
    "Value Colors",
    "Value Order",
    "List Check",
    "Initialize Data",
    "Coding",
    "Aggregation",
    "Multiple Response Set",
    "Design Role",
    "Factor Changes",
    "ID Column",
)

# Sanity bound on a single property string. Real JMP files can carry
# lengthy formulas and value-label lists, but anything past 1 MB is
# almost certainly a misaligned read.
_MAX_PROPERTY_BYTES = 1 << 20


def parse_column_properties(buf: bytes) -> tuple[str | None, dict[str, Any]]:
    """Scan a raw column block for property strings.

    Returns ``(notes, extras)``:

    - ``notes`` is the unwrapped text of a ``Notes(...)`` property if
      present, else ``None``.
    - ``extras`` carries everything else:
        * ``"spec_limits"`` — dict like ``{"LSL": ..., "USL": ...}``
        * ``"formula"`` — raw JSL expression text inside ``Formula(...)``
        * ``"properties"`` — dict of remaining ``{name: text}`` pairs
    """
    notes: str | None = None
    extras: dict[str, Any] = {}
    seen: set[int] = set()

    for prop in _KNOWN_PROPERTY_NAMES:
        needle = (prop + "(").encode("utf-8")
        nlen = len(needle)
        pos = 0
        while True:
            i = buf.find(needle, pos)
            if i < 0:
                break
            pos = i + 1
            if i < 4 or i in seen:
                continue
            length = struct.unpack_from("<I", buf, i - 4)[0]
            if length < nlen + 1 or length > _MAX_PROPERTY_BYTES:
                continue
            end = i + length
            if end > len(buf):
                continue
            text = buf[i:end].decode("utf-8", errors="replace")
            # The slice must be a balanced JSL call. False positives
            # (where the Int32 just happens to look like a length)
            # nearly always fail one of these checks.
            if not text.startswith(prop + "(") or not text.endswith(")"):
                continue
            seen.add(i)
            content = text[nlen:-1]
            if prop == "Notes":
                notes = _unquote_jsl(content)
            elif prop == "Spec Limits":
                extras["spec_limits"] = _parse_spec_limits(content)
            elif prop == "Formula":
                extras["formula"] = content
            else:
                extras.setdefault("properties", {})[prop] = _unquote_jsl(content)

    return notes, extras


def _unquote_jsl(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _parse_spec_limits(content: str) -> dict[str, Any]:
    """Turn ``{LSL(347.5), USL(352.5), Target(350), Show Limits(1)}``
    into ``{"LSL": 347.5, "USL": 352.5, "Target": 350, "Show Limits": 1}``.
    """
    s = content.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out: dict[str, Any] = {}
    for raw in _split_top_level(s, ","):
        item = raw.strip()
        if "(" not in item or not item.endswith(")"):
            continue
        key = item[: item.index("(")].strip()
        val = item[item.index("(") + 1 : -1].strip()
        out[key] = _coerce_number(val)
    return out


def _split_top_level(s: str, sep: str) -> list[str]:
    depth = 0
    start = 0
    parts: list[str] = []
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(s[start:i])
            start = i + 1
    parts.append(s[start:])
    return parts


def _coerce_number(s: str) -> int | float | str:
    try:
        v = float(s)
    except ValueError:
        return s
    if v.is_integer() and "." not in s and "e" not in s.lower():
        return int(v)
    return v
