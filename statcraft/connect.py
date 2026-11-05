"""StatCraft Connect — Core Shared Data & Analysis Identity System.

Provides durable, traceable relationships between worksheets, columns,
observations (rows), statistical models, and external engines (R, JMP).
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .model import Column, Worksheet, finite_number


def ensure_worksheet_identities(worksheet: Worksheet) -> None:
    """Ensure worksheet, all columns, and all observations possess stable UUIDs.
    
    This operates idempotently: existing identities are preserved, and only
    missing identities are generated.
    """
    if not isinstance(worksheet.metadata, dict):
        worksheet.metadata = {}

    # 1. Stable Worksheet ID
    if "id" not in worksheet.metadata or not worksheet.metadata["id"]:
        worksheet.metadata["id"] = f"ws-{uuid.uuid4().hex[:12]}"

    # 2. Stable Column IDs
    for idx, col in enumerate(worksheet.columns):
        if not isinstance(col.metadata, dict):
            col.metadata = {}
        if "id" not in col.metadata or not col.metadata["id"]:
            col.metadata["id"] = f"col-{uuid.uuid4().hex[:12]}"

    # 3. Stable Observation (Row) IDs
    current_rows = worksheet.row_count
    row_ids: list[str] = worksheet.metadata.get("row_ids", [])
    if not isinstance(row_ids, list):
        row_ids = []

    if len(row_ids) < current_rows:
        # Extend with unique row IDs for newly added rows
        start = len(row_ids) + 1
        for i in range(start, current_rows + 1):
            row_ids.append(f"row-{i:05d}-{uuid.uuid4().hex[:6]}")
        worksheet.metadata["row_ids"] = row_ids
    elif len(row_ids) > current_rows:
        # Truncate to active row length
        worksheet.metadata["row_ids"] = row_ids[:current_rows]


def get_column_by_id(worksheet: Worksheet, col_id: str) -> Optional[Tuple[int, Column]]:
    """Locate a column by its durable unique ID."""
    for idx, col in enumerate(worksheet.columns):
        if col.metadata.get("id") == col_id:
            return idx, col
    return None


def get_column_by_name(worksheet: Worksheet, name: str) -> Optional[Tuple[int, Column]]:
    """Locate a column by display name (case-insensitive fallback)."""
    for idx, col in enumerate(worksheet.columns):
        if col.name == name:
            return idx, col
    for idx, col in enumerate(worksheet.columns):
        if col.name.casefold() == name.casefold():
            return idx, col
    return None


def permute_row_identities(worksheet: Worksheet, order: List[int]) -> None:
    """Reorder worksheet row identities matching a sort or filter permutation."""
    ensure_worksheet_identities(worksheet)
    current_ids = list(worksheet.metadata.get("row_ids", []))
    n = len(current_ids)
    if not order or len(order) > n:
        return

    permuted: list[str] = []
    seen = set()
    for idx in order:
        if 0 <= idx < n:
            permuted.append(current_ids[idx])
            seen.add(idx)

    # Append any remaining unpermuted indices in original sequence
    for idx in range(n):
        if idx not in seen:
            permuted.append(current_ids[idx])

    worksheet.metadata["row_ids"] = permuted


def compute_column_fingerprint(column: Column) -> str:
    """Compute cryptographic hash of a column's data values (preserving schema binding across renames)."""
    values = [None if v is None else float(v) for v in column.values] if column.kind == "number" else column.values
    state = [column.kind, values]
    if column.kind == "text" and "value_order" in column.metadata:
        state.append({"value_order": column.metadata["value_order"]})
    raw = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compute_data_fingerprint(worksheet: Worksheet, column_indices: List[int]) -> str:
    """Compute aggregate fingerprint for the selected columns and their row order."""
    parts = []
    ensure_worksheet_identities(worksheet)
    row_ids = worksheet.metadata.get("row_ids", [])
    parts.append(f"rows:{len(row_ids)}")
    for idx in column_indices:
        if 0 <= idx < len(worksheet.columns):
            col = worksheet.columns[idx]
            cid = col.metadata.get("id", f"idx-{idx}")
            parts.append(f"{cid}:{compute_column_fingerprint(col)}")
        else:
            parts.append(f"missing:{idx}")
    return hashlib.sha256(";".join(parts).encode("utf-8")).hexdigest()


@dataclass
class ConnectedAnalysis:
    """Provenance and reproduction contract for a StatCraft Connect analysis."""
    analysis_id: str
    analysis_type: str  # "multiple_regression", "analyze_response_surface", etc.
    title: str
    engine: str  # "statcraft" | "r"
    created_at: str

    # Source worksheet bindings
    worksheet_id: str
    worksheet_name: str
    data_fingerprint: str
    response_col_id: str
    response_name: str
    predictor_col_ids: List[str]
    predictor_names: List[str]
    confidence: float

    # Observation alignment
    row_ids: List[str]
    fitted_row_ids: List[str]
    omitted_row_ids: List[str]

    # Model definition & parameters
    coefficients: List[Dict[str, Any]]
    statistics: Dict[str, Any]  # r_squared, adjusted_r_squared, f, p_value, residual_stdev
    fitted_values: List[float]
    residuals: List[float]

    # Generated executable R translation
    r_script: str = ""

    # Extra options and settings
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def model_type(self) -> str:
        return self.analysis_type

    @property
    def response_column_name(self) -> str:
        return self.response_name

    @property
    def predictor_column_names(self) -> List[str]:
        return self.predictor_names

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectedAnalysis":
        return cls(
            analysis_id=data.get("analysis_id", str(uuid.uuid4())),
            analysis_type=data.get("analysis_type", "multiple_regression"),
            title=data.get("title", "Connected Analysis"),
            engine=data.get("engine", "statcraft"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            worksheet_id=data.get("worksheet_id", ""),
            worksheet_name=data.get("worksheet_name", ""),
            data_fingerprint=data.get("data_fingerprint", ""),
            response_col_id=data.get("response_col_id", ""),
            response_name=data.get("response_name", ""),
            predictor_col_ids=data.get("predictor_col_ids", []),
            predictor_names=data.get("predictor_names", []),
            confidence=float(data.get("confidence", 0.95)),
            row_ids=data.get("row_ids", []),
            fitted_row_ids=data.get("fitted_row_ids", []),
            omitted_row_ids=data.get("omitted_row_ids", []),
            coefficients=data.get("coefficients", []),
            statistics=data.get("statistics", {}),
            fitted_values=data.get("fitted_values", []),
            residuals=data.get("residuals", []),
            r_script=data.get("r_script", ""),
            metadata=data.get("metadata", {}),
        )


def create_connected_regression(
    worksheet: Worksheet,
    response_index: int,
    predictor_indices: List[int],
    result: Dict[str, Any],
    confidence: float = 0.95
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a fitted multiple_regression result."""
    ensure_worksheet_identities(worksheet)

    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-resp-{response_index}")
    pred_cols = [worksheet.columns[i] for i in predictor_indices]
    pred_ids = [col.metadata.get("id", f"col-pred-{i}") for i, col in zip(predictor_indices, pred_cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = result.get("row_indices")
    if complete_indices is None:
        def _valid_num(v: Any) -> bool:
            if v is None or isinstance(v, bool):
                return False
            try:
                f = float(v)
                import math
                return math.isfinite(f)
            except (ValueError, TypeError, OverflowError):
                return False

        complete_indices = []
        for i in range(len(all_row_ids)):
            r_val = resp_col.values[i] if i < len(resp_col.values) else None
            if not _valid_num(r_val):
                continue
            if all(i < len(p.values) and _valid_num(p.values[i]) for p in pred_cols):
                complete_indices.append(i)
    complete_set = set(complete_indices)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if 0 <= i < len(all_row_ids)]
    omitted_row_ids = [all_row_ids[i] for i in range(len(all_row_ids)) if i not in complete_set]

    stats = {
        "r_squared": result.get("r_squared", 0.0),
        "adjusted_r_squared": result.get("adjusted_r_squared", 0.0),
        "f_statistic": result.get("f"),
        "p_value": result.get("p_value"),
        "residual_stdev": result.get("residual_stdev", 0.0),
        "df_regression": result.get("df_regression"),
        "df_error": result.get("df_error"),
        "count": result.get("count", 0),
        "missing": result.get("missing", 0),
    }

    fingerprint = compute_data_fingerprint(worksheet, [response_index] + predictor_indices)

    connected = ConnectedAnalysis(
        analysis_id=f"conn-{uuid.uuid4().hex[:12]}",
        analysis_type="multiple_regression",
        title=f"Multiple Regression — {resp_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(timespec="seconds"),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=pred_ids,
        predictor_names=[c.name for c in pred_cols],
        confidence=confidence,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=result.get("coefficients", []),
        statistics=stats,
        fitted_values=result.get("fitted", []),
        residuals=result.get("residuals", []),
        metadata={
            "method": result.get("method"),
            "assumptions": result.get("assumptions"),
            "warnings": result.get("warnings", []),
        }
    )

    from .connect_r import generate_r_regression_script
    connected.r_script = generate_r_regression_script(connected, worksheet)
    return connected


def check_analysis_freshness(connected: ConnectedAnalysis, worksheet: Worksheet) -> Tuple[str, str]:
    """Evaluate whether connected analysis is current, stale, or requires repair.
    
    Returns:
        (status, message)
        status in ('current', 'stale', 'repair_needed')
    """
    ensure_worksheet_identities(worksheet)

    # 1. Check if response column exists by ID or name
    resp_match = get_column_by_id(worksheet, connected.response_col_id)
    if resp_match is None:
        resp_match = get_column_by_name(worksheet, connected.response_name)
    if resp_match is None:
        return (
            "repair_needed",
            f"Response column '{connected.response_name}' was deleted. Please restore it or rebind the analysis."
        )

    # 2. Check if all predictor columns exist
    pred_indices = []
    for cid, cname in zip(connected.predictor_col_ids, connected.predictor_names):
        pmatch = get_column_by_id(worksheet, cid)
        if pmatch is None:
            pmatch = get_column_by_name(worksheet, cname)
        if pmatch is None:
            return (
                "repair_needed",
                f"Predictor column '{cname}' was deleted. Please restore it or rebind the analysis."
            )
        pred_indices.append(pmatch[0])

    all_indices = [resp_match[0]] + pred_indices
    current_fingerprint = compute_data_fingerprint(worksheet, all_indices)

    if current_fingerprint != connected.data_fingerprint:
        return (
            "stale",
            "Source worksheet data has changed since this model was fitted. Rerun or refit to update."
        )

    return ("current", "Model is fully synchronized with current worksheet data.")
