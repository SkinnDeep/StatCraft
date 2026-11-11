"""Zero-dependency atomic Excel (.xlsx) worksheet reader for StatCraft."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zipfile import BadZipFile, ZipFile

from .io import FormatError, MAX_CELLS, MAX_TOTAL_BYTES
from .model import Column, Worksheet, finite_number

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_BUILTIN_DATE_FMTS = frozenset(range(14, 23)) | frozenset((27, 28, 29, 30, 36, 45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58))
_DATE_TOKEN_RE = re.compile(r"(?:y{2,4}|m{1,5}|d{1,4}|h{1,2}|s{1,2}|am/pm)", re.IGNORECASE)
_CELL_REF_RE = re.compile(r"^([A-Za-z]{1,3})([1-9][0-9]*)$")
_XESC_RE = re.compile(r"_x([0-9a-fA-F]{4})_")


def _unescape_x(text: str) -> str:
    return _XESC_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def _col_to_index(col_letters: str) -> int:
    idx = 0
    for ch in col_letters.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _parse_shared_strings(archive: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    raw = archive.read("xl/sharedStrings.xml")
    if len(raw) > MAX_TOTAL_BYTES:
        raise FormatError("Excel shared string table exceeds size limit.")
    root = ET.fromstring(raw)
    out: List[str] = []
    for si in root.findall(f"{{{_MAIN_NS}}}si"):
        t_el = si.find(f"{{{_MAIN_NS}}}t")
        if t_el is not None:
            out.append(_unescape_x(t_el.text or ""))
        else:
            parts = [(_unescape_x(r.text or "")) for r in si.findall(f".//{{{_MAIN_NS}}}t")]
            out.append("".join(parts))
    return out


def _parse_date_style_indices(archive: ZipFile) -> set[int]:
    """Identify cellXfs indices that format numbers as Excel serial dates."""
    if "xl/styles.xml" not in archive.namelist():
        return set()
    try:
        root = ET.fromstring(archive.read("xl/styles.xml"))
    except ET.ParseError:
        return set()
    custom_date_fmts: set[int] = set()
    num_fmts = root.find(f"{{{_MAIN_NS}}}numFmts")
    if num_fmts is not None:
        for nf in num_fmts.findall(f"{{{_MAIN_NS}}}numFmt"):
            try:
                fmt_id = int(nf.attrib.get("numFmtId", "-1"))
            except ValueError:
                continue
            code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", nf.attrib.get("formatCode", ""))
            if _DATE_TOKEN_RE.search(code):
                custom_date_fmts.add(fmt_id)
    date_styles: set[int] = set()
    xfs = root.find(f"{{{_MAIN_NS}}}cellXfs")
    if xfs is not None:
        for idx, xf in enumerate(xfs.findall(f"{{{_MAIN_NS}}}xf")):
            try:
                fid = int(xf.attrib.get("numFmtId", "0"))
            except ValueError:
                continue
            if fid in _BUILTIN_DATE_FMTS or fid in custom_date_fmts:
                date_styles.add(idx)
    return date_styles


def _resolve_sheet_targets(archive: ZipFile) -> List[Tuple[str, str]]:
    names = set(archive.namelist())
    if "xl/workbook.xml" not in names:
        raise FormatError("Invalid .xlsx file: missing xl/workbook.xml.")
    wb_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_map: Dict[str, str] = {}
    if "xl/_rels/workbook.xml.rels" in names:
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        for rel in rels_root:
            if rel.tag.endswith("Relationship"):
                rid = rel.attrib.get("Id", "")
                target = rel.attrib.get("Target", "").lstrip("/")
                if target and not target.startswith("xl/"):
                    target = f"xl/{target}"
                if rid and target:
                    rels_map[rid] = target

    sheets: List[Tuple[str, str]] = []
    for sheet_el in wb_root.findall(f".//{{{_MAIN_NS}}}sheet"):
        title = sheet_el.attrib.get("name", "Sheet")
        rid = sheet_el.attrib.get(f"{{{_REL_NS}}}id", "")
        target = rels_map.get(rid)
        if target and target in names:
            sheets.append((title, target))
    if not sheets:
        fallback = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        sheets = [(f"Sheet{i + 1}", path) for i, path in enumerate(fallback)]
    if not sheets:
        raise FormatError("Excel workbook contains no worksheets.")
    return sheets


def _parse_sheet_xml(
    raw_xml: bytes,
    sheet_name: str,
    shared_strings: List[str],
    date_styles: set[int],
    has_header: bool = True,
    column_types: Optional[List[str]] = None,
) -> Worksheet:
    if len(raw_xml) > MAX_TOTAL_BYTES:
        raise FormatError(f"Worksheet '{sheet_name}' exceeds XML size limit.")
    root = ET.fromstring(raw_xml)
    grid: Dict[int, Dict[int, Tuple[str, object]]] = {}
    max_row = -1
    max_col = -1
    seq_row = 0
    for row_el in root.findall(f".//{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row"):
        r_attr = row_el.attrib.get("r")
        r_idx = (int(r_attr) - 1) if (r_attr and r_attr.isdigit()) else seq_row
        seq_row = max(seq_row + 1, r_idx + 1)
        row_cells = grid.setdefault(r_idx, {})
        seq_col = 0
        for c_el in row_el.findall(f"{{{_MAIN_NS}}}c"):
            ref = c_el.attrib.get("r", "")
            m = _CELL_REF_RE.match(ref)
            if m:
                c_idx = _col_to_index(m.group(1))
                r_idx_cell = int(m.group(2)) - 1
                if r_idx_cell != r_idx:
                    r_idx = r_idx_cell
                    row_cells = grid.setdefault(r_idx, {})
            else:
                c_idx = seq_col
            seq_col = c_idx + 1
            if c_idx > max_col:
                max_col = c_idx
            if r_idx > max_row:
                max_row = r_idx

            ctype = c_el.attrib.get("t", "")
            style_idx = int(c_el.attrib["s"]) if c_el.attrib.get("s", "").isdigit() else 0
            v_el = c_el.find(f"{{{_MAIN_NS}}}v")
            is_el = c_el.find(f"{{{_MAIN_NS}}}is")
            if ctype == "s":
                if v_el is None or v_el.text is None:
                    continue
                idx = int(v_el.text)
                val = shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
                row_cells[c_idx] = ("text", val)
            elif ctype == "inlineStr":
                if is_el is None:
                    continue
                t_el = is_el.find(f"{{{_MAIN_NS}}}t")
                txt = _unescape_x(t_el.text or "") if t_el is not None else "".join(
                    _unescape_x(t.text or "") for t in is_el.findall(f".//{{{_MAIN_NS}}}t")
                )
                row_cells[c_idx] = ("text", txt)
            elif ctype in ("str", "e"):
                if v_el is not None and v_el.text is not None:
                    row_cells[c_idx] = ("text", _unescape_x(v_el.text))
            elif ctype == "b":
                if v_el is not None and v_el.text is not None:
                    row_cells[c_idx] = ("number", 1.0 if v_el.text.strip() in ("1", "true", "TRUE") else 0.0)
            else:
                if v_el is None or v_el.text is None or not v_el.text.strip():
                    continue
                num = finite_number(float(v_el.text))
                if style_idx in date_styles:
                    ole_num = num + 1.0 if 1.0 <= num < 61.0 else num
                    row_cells[c_idx] = ("date", ole_num)
                else:
                    row_cells[c_idx] = ("number", num)

    if max_row < 0 or max_col < 0:
        return Worksheet(sheet_name)

    n_cols = max_col + 1
    data_start = 1 if has_header else 0
    n_data_rows = max(0, max_row + 1 - data_start)
    if max(1, n_data_rows) * n_cols > MAX_CELLS:
        raise FormatError(f"Worksheet '{sheet_name}' exceeds the maximum cell budget.")
    if column_types is not None and len(column_types) != n_cols:
        raise FormatError("Specify one type per column.")

    header_cells = grid.get(0, {})
    columns: List[Column] = []
    for c_idx in range(n_cols):
        if has_header:
            hdr_pair = header_cells.get(c_idx)
            hdr = str(hdr_pair[1]).strip() if (hdr_pair and hdr_pair[1] is not None) else ""
        else:
            hdr = ""
        col_name = hdr or f"C{c_idx + 1}"

        raw_pairs = [grid.get(r_idx, {}).get(c_idx) for r_idx in range(data_start, max_row + 1)]
        while raw_pairs and raw_pairs[-1] is None:
            raw_pairs.pop()

        explicit_kind = column_types[c_idx] if column_types is not None else None
        if explicit_kind is not None:
            kind = explicit_kind
        else:
            observed_kinds = {p[0] for p in raw_pairs if p is not None and str(p[1]).strip() != ""}
            if not observed_kinds:
                kind = "text"
            elif "text" in observed_kinds:
                # Try numeric parse in case numeric column arrived stored as text strings
                try:
                    for p in raw_pairs:
                        if p is not None and p[0] == "text" and str(p[1]).strip() not in ("", "*"):
                            finite_number(float(str(p[1]).strip()))
                    kind = "date" if "date" in observed_kinds else "number"
                except ValueError:
                    kind = "text"
            elif observed_kinds == {"date"}:
                kind = "date"
            else:
                kind = "number"

        values = []
        for p in raw_pairs:
            if p is None:
                values.append(None)
            elif kind == "text":
                values.append(str(p[1]))
            elif kind == "date":
                values.append(float(p[1]))
            else:
                if p[0] == "text":
                    s = str(p[1]).strip()
                    values.append(None if s in ("", "*") else finite_number(float(s)))
                else:
                    values.append(finite_number(float(p[1])))
        columns.append(Column(col_name, kind, values))

    return Worksheet(sheet_name, columns, metadata={"import": {"format": "xlsx"}})


def load_xlsx(
    path: str | Path,
    sheet_name: Optional[str] = None,
    has_header: bool = True,
    column_types: Optional[List[str]] = None,
) -> List[Worksheet]:
    """Read one or all worksheets cleanly from an Excel .xlsx workbook."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Excel file not found: {p}")
    if p.stat().st_size > MAX_TOTAL_BYTES:
        raise FormatError("Excel workbook exceeds the maximum file size limit.")
    try:
        with ZipFile(p, "r") as archive:
            shared = _parse_shared_strings(archive)
            date_styles = _parse_date_style_indices(archive)
            targets = _resolve_sheet_targets(archive)
            if sheet_name is not None:
                targets = [(name, member) for name, member in targets if name == sheet_name]
                if not targets:
                    raise FormatError(f"Worksheet '{sheet_name}' not found in '{p.name}'.")
            worksheets: List[Worksheet] = []
            for name, member in targets:
                raw_xml = archive.read(member)
                worksheets.append(_parse_sheet_xml(raw_xml, name, shared, date_styles, has_header, column_types))
            return worksheets
    except BadZipFile as exc:
        raise FormatError(f"'{p.name}' is not a valid .xlsx workbook.") from exc
