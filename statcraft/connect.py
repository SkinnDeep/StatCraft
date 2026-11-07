"""StatCraft Connect — Core Shared Data & Analysis Identity System.

Provides durable, traceable relationships between worksheets, columns,
observations (rows), statistical models, and external engines (R, JMP).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
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

    @property
    def fit_statistics(self) -> Dict[str, Any]:
        return self.statistics

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


def create_connected_fitted_line_plot(
    worksheet: Worksheet,
    response_index: int,
    predictor_index: int,
    result: Dict[str, Any],
    confidence: float = 0.95,
    model_type: str = "linear",
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a fitted_line_plot result."""
    ensure_worksheet_identities(worksheet)

    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-resp-{response_index}")
    pred_col = worksheet.columns[predictor_index]
    pred_id = pred_col.metadata.get("id", f"col-pred-{predictor_index}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = result.get("points", {}).get("row_indices", [])
    complete_set = set(complete_indices)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if 0 <= i < len(all_row_ids)]
    omitted_row_ids = [all_row_ids[i] for i in range(len(all_row_ids)) if i not in complete_set]

    stats = {
        "r_squared": result.get("r_squared", 0.0),
        "adjusted_r_squared": result.get("r_squared_adj", 0.0),
        "predicted_r_squared": result.get("r_squared_pred", 0.0),
        "s": result.get("s", 0.0),
        "equation": result.get("equation", ""),
        "model_type": model_type,
        "n": result.get("n", 0),
    }

    fingerprint = compute_data_fingerprint(worksheet, [response_index, predictor_index])

    connected = ConnectedAnalysis(
        analysis_id=f"conn-{uuid.uuid4().hex[:12]}",
        analysis_type="fitted_line_plot",
        title=f"Fitted Line Plot — {resp_col.name} versus {pred_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(timespec="seconds"),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=[pred_id],
        predictor_names=[pred_col.name],
        confidence=confidence,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=result.get("coefficients", []),
        statistics=stats,
        fitted_values=result.get("fits", []),
        residuals=result.get("residuals", []),
        metadata={
            "model_type": model_type,
            "degree": result.get("degree", 1),
            "equation": result.get("equation", ""),
            "options": result.get("options", {}),
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


def create_connected_response_surface(
    worksheet: Worksheet,
    response_index: int,
    factor_indices: List[int],
    result: Dict[str, Any],
    confidence: float = 0.95,
    coding: Optional[List[Dict[str, Any]]] = None,
    terms: Optional[List[List[int]]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a fitted analyze_response_surface result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-resp-{response_index}")
    factor_cols = [worksheet.columns[i] for i in factor_indices]
    factor_ids = [col.metadata.get("id", f"col-fact-{i}") for i, col in zip(factor_indices, factor_cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = result.get("row_indices")
    if complete_indices is None:
        def _valid_num(v: Any) -> bool:
            if v is None or isinstance(v, bool):
                return False
            try:
                import math
                return math.isfinite(float(v))
            except (ValueError, TypeError, OverflowError):
                return False

        complete_indices = []
        for i in range(len(all_row_ids)):
            r_val = resp_col.values[i] if i < len(resp_col.values) else None
            if not _valid_num(r_val):
                continue
            if all(i < len(p.values) and _valid_num(p.values[i]) for p in factor_cols):
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

    fingerprint = compute_data_fingerprint(worksheet, [response_index] + factor_indices)

    connected = ConnectedAnalysis(
        analysis_id=f"conn-{uuid.uuid4().hex[:12]}",
        analysis_type="analyze_response_surface",
        title=f"Response Surface — {resp_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(timespec="seconds"),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=factor_ids,
        predictor_names=[c.name for c in factor_cols],
        confidence=confidence,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=result.get("coefficients", []),
        statistics=stats,
        fitted_values=result.get("fitted", []),
        residuals=result.get("residuals", []),
        metadata={
            "coding": coding or result.get("coding_information", []),
            "terms": terms or result.get("terms", []),
            "options": options or result.get("options", {}),
            "lack_of_fit": result.get("lack_of_fit"),
            "anova_terms": result.get("anova_terms", []),
        }
    )

    from .connect_r import generate_r_rsm_script
    connected.r_script = generate_r_rsm_script(connected, worksheet)
    return connected


def create_connected_oneway_anova(
    worksheet: Worksheet,
    response_index: int,
    factor_index: int,
    result: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a fitted oneway_anova result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-resp-{response_index}")
    fact_col = worksheet.columns[factor_index]
    fact_id = fact_col.metadata.get("id", f"col-fact-{factor_index}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = []
    for i in range(worksheet.row_count):
        r_val = resp_col.values[i] if i < len(resp_col.values) else None
        f_val = fact_col.values[i] if i < len(fact_col.values) else None
        if r_val is not None and f_val is not None and not (isinstance(r_val, float) and math.isnan(r_val)):
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    fingerprint = compute_data_fingerprint(worksheet, [response_index, factor_index])

    anova_tab = result.get("anova_table", {})
    mod_sum = result.get("model_summary", {})
    r_sq = (mod_sum.get("r_sq", 0.0) / 100.0) if "r_sq" in mod_sum else result.get("r_squared", 0.0)
    adj_r_sq = (mod_sum.get("r_sq_adj", 0.0) / 100.0) if "r_sq_adj" in mod_sum else result.get("adjusted_r_squared", 0.0)
    s_val = mod_sum.get("s", result.get("residual_stdev", 0.0))

    stats = {
        "r_squared": r_sq,
        "adjusted_r_squared": adj_r_sq,
        "residual_stdev": s_val,
        "f_stat": anova_tab.get("f_value", result.get("f_stat", 0.0)),
        "p_value": anova_tab.get("p_value", result.get("p_value", 1.0)),
        "df_factor": anova_tab.get("df_factor", result.get("df_factor", 0)),
        "df_error": anova_tab.get("df_error", result.get("df_error", 0)),
    }

    fits = result.get("fits", result.get("fitted", []))
    resids = result.get("residuals", [])

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="oneway_anova",
        title=f"One-Way ANOVA: {resp_col.name} by {fact_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=[fact_id],
        predictor_names=[fact_col.name],
        confidence=float((options or {}).get("confidence", 0.95)),
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=fits,
        residuals=resids,
        metadata={
            "factor_name": fact_col.name,
            "response_name": resp_col.name,
            "options": options or {},
            "group_summary": result.get("means", result.get("group_summary", [])),
        }
    )
    from .connect_r import generate_r_oneway_anova_script
    connected.r_script = generate_r_oneway_anova_script(connected, worksheet)
    return connected


def create_connected_factorial(
    worksheet: Worksheet,
    response_index: int,
    factor_indices: List[int],
    result: Dict[str, Any],
    confidence: float = 0.95,
    selected_terms: Optional[List[Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a fitted analyze_factorial result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-resp-{response_index}")
    fact_cols = [worksheet.columns[i] for i in factor_indices]
    fact_ids = [col.metadata.get("id", f"col-fact-{i}") for i, col in zip(factor_indices, fact_cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = []
    for i in range(worksheet.row_count):
        r_val = resp_col.values[i] if i < len(resp_col.values) else None
        valid = r_val is not None and not (isinstance(r_val, float) and math.isnan(r_val))
        if valid:
            for fc in fact_cols:
                fv = fc.values[i] if i < len(fc.values) else None
                if fv is None or (isinstance(fv, float) and math.isnan(fv)):
                    valid = False
                    break
        if valid:
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    fingerprint = compute_data_fingerprint(worksheet, [response_index] + list(factor_indices))

    stats = {
        "r_squared": result.get("r_squared", 0.0),
        "adjusted_r_squared": result.get("adjusted_r_squared", 0.0),
        "residual_stdev": result.get("residual_stdev", 0.0),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="analyze_factorial",
        title=f"Factorial Fit: {resp_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=fact_ids,
        predictor_names=[c.name for c in fact_cols],
        confidence=confidence,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=result.get("coefficients", []),
        statistics=stats,
        fitted_values=result.get("fitted", []),
        residuals=result.get("residuals", []),
        metadata={
            "effects": result.get("effects", []),
            "selected_terms": selected_terms,
            "max_order": result.get("max_order", 2),
        }
    )
    from .connect_r import generate_r_factorial_script
    connected.r_script = generate_r_factorial_script(connected, worksheet)
    return connected


def create_connected_glm(
    worksheet: Worksheet,
    response_index: int,
    factor_indices: List[int],
    covariate_indices: List[int],
    result: Dict[str, Any],
    terms: Optional[List[Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a fitted general_linear_model result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-resp-{response_index}")
    all_pred_indices = list(factor_indices) + list(covariate_indices)
    pred_cols = [worksheet.columns[i] for i in all_pred_indices]
    pred_ids = [col.metadata.get("id", f"col-pred-{i}") for i, col in zip(all_pred_indices, pred_cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = []
    for i in range(worksheet.row_count):
        r_val = resp_col.values[i] if i < len(resp_col.values) else None
        valid = r_val is not None and not (isinstance(r_val, float) and math.isnan(r_val))
        if valid:
            for pc in pred_cols:
                pv = pc.values[i] if i < len(pc.values) else None
                if pv is None or (isinstance(pv, float) and math.isnan(pv)):
                    valid = False
                    break
        if valid:
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    fingerprint = compute_data_fingerprint(worksheet, [response_index] + all_pred_indices)

    stats = {
        "r_squared": result.get("r_squared", 0.0),
        "adjusted_r_squared": result.get("adjusted_r_squared", 0.0),
        "residual_stdev": result.get("residual_stdev", 0.0),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="general_linear_model",
        title=f"General Linear Model: {resp_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=pred_ids,
        predictor_names=[c.name for c in pred_cols],
        confidence=float((options or {}).get("confidence", 0.95)),
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=result.get("coefficients", []),
        statistics=stats,
        fitted_values=result.get("fitted", []),
        residuals=result.get("residuals", []),
        metadata={
            "factor_names": [worksheet.columns[i].name for i in factor_indices],
            "covariate_names": [worksheet.columns[i].name for i in covariate_indices],
            "terms": terms,
            "options": options or {},
        }
    )
    from .connect_r import generate_r_glm_script
    connected.r_script = generate_r_glm_script(connected, worksheet)
    return connected


def create_connected_two_sample_t(
    worksheet: Worksheet,
    settings: Dict[str, Any],
    result: Dict[str, Any],
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a 2-sample t-test result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    fmt = settings.get("data_format", 1)

    if fmt == 2:
        resp_idx = settings.get("samples_col")
        pred_idx = settings.get("sample_ids_col")
    else:
        resp_idx = settings.get("sample1_col")
        pred_idx = settings.get("sample2_col")

    resp_col = worksheet.columns[resp_idx] if resp_idx is not None and 0 <= resp_idx < len(worksheet.columns) else Column("Sample1", "number", [])
    pred_col = worksheet.columns[pred_idx] if pred_idx is not None and 0 <= pred_idx < len(worksheet.columns) else Column("Sample2", "number", [])

    resp_id = resp_col.metadata.get("id", f"col-{resp_idx}")
    pred_id = pred_col.metadata.get("id", f"col-{pred_idx}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    active_indices = [i for i in [resp_idx, pred_idx] if i is not None and 0 <= i < len(worksheet.columns)]
    fingerprint = compute_data_fingerprint(worksheet, active_indices)

    complete_indices = []
    for i in range(worksheet.row_count):
        valid = True
        for ci in active_indices:
            v = worksheet.columns[ci].values[i] if i < len(worksheet.columns[ci].values) else None
            if v is None or (isinstance(v, float) and math.isnan(v)):
                valid = False
                break
        if valid:
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    conf_pct = float(settings.get("confidence_level", result.get("confidence_level", 95.0)))
    conf = conf_pct / 100.0 if conf_pct > 1.0 else conf_pct

    stats = {
        "t_statistic": result.get("t_statistic", 0.0),
        "p_value": result.get("p_value", 1.0),
        "df": result.get("df", 0.0),
        "difference": result.get("difference", 0.0),
        "ci_lower": result.get("ci_lower", 0.0),
        "ci_upper": result.get("ci_upper", 0.0),
        "pooled_stdev": result.get("pooled_stdev"),
    }

    title = f"2-Sample t-Test: {resp_col.name} by {pred_col.name}" if fmt == 2 else f"2-Sample t-Test: {resp_col.name} vs {pred_col.name}"

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="two_sample_t",
        title=title,
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=[pred_id],
        predictor_names=[pred_col.name],
        confidence=conf,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "settings": settings,
            "data_format": fmt,
            "sample1": result.get("sample1", {}),
            "sample2": result.get("sample2", {}),
        }
    )
    from .connect_r import generate_r_two_sample_t_script
    connected.r_script = generate_r_two_sample_t_script(connected, worksheet)
    return connected


def create_connected_one_sample_t(
    worksheet: Worksheet,
    settings: Dict[str, Any],
    result: Dict[str, Any],
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a 1-sample t-test result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    sample_cols = settings.get("sample_cols", [])
    resp_idx = sample_cols[0] if sample_cols else 0
    resp_col = worksheet.columns[resp_idx] if 0 <= resp_idx < len(worksheet.columns) else Column("Sample", "number", [])
    resp_id = resp_col.metadata.get("id", f"col-{resp_idx}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    fingerprint = compute_data_fingerprint(worksheet, [resp_idx])

    complete_indices = [
        i for i in range(worksheet.row_count)
        if i < len(resp_col.values) and resp_col.values[i] is not None and not (isinstance(resp_col.values[i], float) and math.isnan(resp_col.values[i]))
    ]
    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    conf_pct = float(settings.get("confidence_level", result.get("confidence_level", 95.0)))
    conf = conf_pct / 100.0 if conf_pct > 1.0 else conf_pct

    s0 = result.get("samples", [{}])[0] if result.get("samples") else {}
    stats = {
        "mean": s0.get("mean", 0.0),
        "sd": s0.get("sd", 0.0),
        "t_statistic": s0.get("t_statistic", 0.0),
        "p_value": s0.get("p_value", 1.0),
        "df": s0.get("df", 0.0),
        "ci_lower": s0.get("ci_lower", 0.0),
        "ci_upper": s0.get("ci_upper", 0.0),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="one_sample_t",
        title=f"1-Sample t-Test: {resp_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=[],
        predictor_names=[],
        confidence=conf,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "settings": settings,
            "hypothesized_mean": settings.get("hypothesized_mean", 0.0),
            "samples": result.get("samples", []),
        }
    )
    from .connect_r import generate_r_one_sample_t_script
    connected.r_script = generate_r_one_sample_t_script(connected, worksheet)
    return connected


def create_connected_paired_t(
    worksheet: Worksheet,
    settings: Dict[str, Any],
    result: Dict[str, Any],
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a paired t-test result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    s1_idx = settings.get("sample1_col", 0)
    s2_idx = settings.get("sample2_col", 1)

    s1_col = worksheet.columns[s1_idx] if 0 <= s1_idx < len(worksheet.columns) else Column("Sample1", "number", [])
    s2_col = worksheet.columns[s2_idx] if 0 <= s2_idx < len(worksheet.columns) else Column("Sample2", "number", [])

    s1_id = s1_col.metadata.get("id", f"col-{s1_idx}")
    s2_id = s2_col.metadata.get("id", f"col-{s2_idx}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    fingerprint = compute_data_fingerprint(worksheet, [s1_idx, s2_idx])

    complete_indices = []
    for i in range(worksheet.row_count):
        v1 = s1_col.values[i] if i < len(s1_col.values) else None
        v2 = s2_col.values[i] if i < len(s2_col.values) else None
        if v1 is not None and v2 is not None and not (isinstance(v1, float) and math.isnan(v1)) and not (isinstance(v2, float) and math.isnan(v2)):
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    conf_pct = float(settings.get("confidence_level", result.get("confidence_level", 95.0)))
    conf = conf_pct / 100.0 if conf_pct > 1.0 else conf_pct

    diffs = result.get("differences", {})
    stats = {
        "t_statistic": result.get("t_statistic", 0.0),
        "p_value": result.get("p_value", 1.0),
        "df": result.get("df", 0.0),
        "mean_difference": diffs.get("mean", 0.0),
        "sd_difference": diffs.get("sd", 0.0),
        "ci_lower": diffs.get("ci_lower", 0.0),
        "ci_upper": diffs.get("ci_upper", 0.0),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="paired_t",
        title=f"Paired t-Test: {s1_col.name} vs {s2_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=s1_id,
        response_name=s1_col.name,
        predictor_col_ids=[s2_id],
        predictor_names=[s2_col.name],
        confidence=conf,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "settings": settings,
            "sample1": result.get("sample1", {}),
            "sample2": result.get("sample2", {}),
            "differences": diffs,
        }
    )
    from .connect_r import generate_r_paired_t_script
    connected.r_script = generate_r_paired_t_script(connected, worksheet)
    return connected


def create_connected_correlation(
    worksheet: Worksheet,
    indices: List[int],
    result: Dict[str, Any],
    method: str = "Pearson",
    missing: str = "Pairwise",
    confidence: float = 0.95,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a correlation analysis result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    valid_indices = [i for i in indices if 0 <= i < len(worksheet.columns)]
    if not valid_indices:
        valid_indices = list(range(min(2, len(worksheet.columns))))

    cols = [worksheet.columns[i] for i in valid_indices]
    col_ids = [c.metadata.get("id", f"col-{i}") for i, c in zip(valid_indices, cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    fingerprint = compute_data_fingerprint(worksheet, valid_indices)

    complete_indices = []
    for i in range(worksheet.row_count):
        valid = True
        for c in cols:
            v = c.values[i] if i < len(c.values) else None
            if v is None or (isinstance(v, float) and math.isnan(v)):
                valid = False
                break
        if valid:
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    names = [c.name for c in cols]
    resp_name = names[0] if names else "X1"
    pred_names = names[1:] if len(names) > 1 else []

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="correlation",
        title=f"Correlation Matrix: {', '.join(names)}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=col_ids[0] if col_ids else "",
        response_name=resp_name,
        predictor_col_ids=col_ids[1:] if len(col_ids) > 1 else [],
        predictor_names=pred_names,
        confidence=float(confidence),
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics={"correlations": result.get("correlations", {})},
        fitted_values=[],
        residuals=[],
        metadata={
            "method": method,
            "missing": missing,
            "all_column_names": names,
        }
    )
    from .connect_r import generate_r_correlation_script
    connected.r_script = generate_r_correlation_script(connected, worksheet)
    return connected


def create_connected_histogram(
    worksheet: Worksheet,
    indices: List[int],
    result: Dict[str, Any],
    variant: str = "simple",
    bins: Optional[int] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a Histogram procedure."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    valid_indices = [i for i in indices if 0 <= i < len(worksheet.columns)]
    if not valid_indices:
        valid_indices = list(range(min(1, len(worksheet.columns))))

    cols = [worksheet.columns[i] for i in valid_indices]
    col_ids = [c.metadata.get("id", f"col-{i}") for i, c in zip(valid_indices, cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    fingerprint = compute_data_fingerprint(worksheet, valid_indices)

    names = [c.name for c in cols]
    resp_name = names[0] if names else "Var1"
    pred_names = names[1:] if len(names) > 1 else []

    title_suffix = " with Fit" if variant in ("fit", "fit_groups") else ""
    title = f"Histogram: {', '.join(names)}{title_suffix}"

    from .connect_r import generate_r_histogram_script
    r_script = generate_r_histogram_script(names, variant=variant, bins=bins)

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="histogram",
        title=title,
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=col_ids[0] if col_ids else "",
        response_name=resp_name,
        predictor_col_ids=col_ids[1:] if len(col_ids) > 1 else [],
        predictor_names=pred_names,
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=all_row_ids,
        omitted_row_ids=[],
        coefficients=[],
        statistics={"variant": variant, "bins": bins},
        fitted_values=[],
        residuals=[],
        r_script=r_script,
        metadata={
            "indices": valid_indices,
            "column_names": names,
            "variant": variant,
            "bins": bins,
        },
    )
    return connected


def create_connected_descriptives(
    worksheet: Worksheet,
    indices: List[int],
    result: Dict[str, Any],
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from descriptive statistics."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    valid_indices = [i for i in indices if 0 <= i < len(worksheet.columns)]
    if not valid_indices:
        valid_indices = list(range(min(1, len(worksheet.columns))))

    cols = [worksheet.columns[i] for i in valid_indices]
    col_ids = [c.metadata.get("id", f"col-{i}") for i, c in zip(valid_indices, cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    fingerprint = compute_data_fingerprint(worksheet, valid_indices)

    names = [c.name for c in cols]
    resp_name = names[0] if names else "Var1"
    pred_names = names[1:] if len(names) > 1 else []

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="descriptive_statistics",
        title=f"Descriptive Statistics: {', '.join(names)}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=col_ids[0] if col_ids else "",
        response_name=resp_name,
        predictor_col_ids=col_ids[1:] if len(col_ids) > 1 else [],
        predictor_names=pred_names,
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=all_row_ids,
        omitted_row_ids=[],
        coefficients=[],
        statistics={"columns": result.get("columns", [])},
        fitted_values=[],
        residuals=[],
        metadata={
            "all_column_names": names,
            "columns": result.get("columns", []),
        }
    )
    from .connect_r import generate_r_descriptives_script
    connected.r_script = generate_r_descriptives_script(connected, worksheet)
    return connected


def create_connected_twoway_anova(
    worksheet: Worksheet,
    response_index: int,
    factor_a_index: int,
    factor_b_index: int,
    result: Dict[str, Any],
    fit_interaction: bool = True,
    confidence: float = 0.95,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a 2-way ANOVA result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    fa_col = worksheet.columns[factor_a_index]
    fb_col = worksheet.columns[factor_b_index]
    resp_id = resp_col.metadata.get("id", f"col-{response_index}")
    fa_id = fa_col.metadata.get("id", f"col-{factor_a_index}")
    fb_id = fb_col.metadata.get("id", f"col-{factor_b_index}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = []
    for i in range(worksheet.row_count):
        valid = True
        for ci in (response_index, factor_a_index, factor_b_index):
            v = worksheet.columns[ci].values[i] if i < len(worksheet.columns[ci].values) else None
            if v is None or (isinstance(v, float) and math.isnan(v)):
                valid = False
                break
        if valid:
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]
    fingerprint = compute_data_fingerprint(worksheet, [response_index, factor_a_index, factor_b_index])

    stats = {
        "r_squared": result.get("r_squared", 0.0),
        "adjusted_r_squared": result.get("adjusted_r_squared", 0.0),
        "f_a": result.get("f_a"),
        "p_a": result.get("p_a"),
        "f_b": result.get("f_b"),
        "p_b": result.get("p_b"),
        "f_ab": result.get("f_ab"),
        "p_ab": result.get("p_ab"),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="twoway_anova",
        title=f"Two-Way ANOVA: {resp_col.name} by {fa_col.name}, {fb_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=[fa_id, fb_id],
        predictor_names=[fa_col.name, fb_col.name],
        confidence=confidence,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "factor_a_name": fa_col.name,
            "factor_b_name": fb_col.name,
            "fit_interaction": fit_interaction,
            "cell_stats": result.get("cell_stats", {}),
        }
    )
    from .connect_r import generate_r_twoway_anova_script
    connected.r_script = generate_r_twoway_anova_script(connected, worksheet)
    return connected


def create_connected_binary_logistic(
    worksheet: Worksheet,
    response_index: int,
    continuous_indices: List[int],
    categorical_indices: List[int],
    result: Dict[str, Any],
    event: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from binary logistic regression."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    resp_col = worksheet.columns[response_index]
    resp_id = resp_col.metadata.get("id", f"col-{response_index}")

    pred_indices = list(continuous_indices) + list(categorical_indices)
    pred_cols = [worksheet.columns[i] for i in pred_indices if 0 <= i < len(worksheet.columns)]
    pred_ids = [c.metadata.get("id", f"col-{i}") for i, c in zip(pred_indices, pred_cols)]

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    active_indices = [response_index] + pred_indices
    fingerprint = compute_data_fingerprint(worksheet, active_indices)

    complete_indices = []
    for i in range(worksheet.row_count):
        valid = True
        for ci in active_indices:
            v = worksheet.columns[ci].values[i] if i < len(worksheet.columns[ci].values) else None
            if v is None or (isinstance(v, float) and math.isnan(v)):
                valid = False
                break
        if valid:
            complete_indices.append(i)

    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]

    event_val = event or result.get("event", "1")
    conf = float((options or {}).get("confidence", 0.95))

    stats = {
        "aic": result.get("aic"),
        "bic": result.get("bic"),
        "deviance": result.get("deviance"),
        "auc": result.get("auc"),
        "model_lr": result.get("model_lr"),
        "model_lr_p": result.get("model_lr_p"),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="binary_logistic",
        title=f"Binary Logistic Regression: {resp_col.name} (Event = '{event_val}')",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=resp_id,
        response_name=resp_col.name,
        predictor_col_ids=pred_ids,
        predictor_names=[c.name for c in pred_cols],
        confidence=conf,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=result.get("coefficients", []),
        statistics=stats,
        fitted_values=result.get("probabilities", []),
        residuals=result.get("residuals", []),
        metadata={
            "event": event_val,
            "continuous_indices": continuous_indices,
            "categorical_indices": categorical_indices,
            "options": options or {},
        }
    )
    from .connect_r import generate_r_logistic_script
    connected.r_script = generate_r_logistic_script(connected, worksheet)
    return connected


def create_connected_capability(
    worksheet: Worksheet,
    index: int,
    result: Dict[str, Any],
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from process capability analysis."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    col = worksheet.columns[index] if 0 <= index < len(worksheet.columns) else Column("Variable", "number", [])
    col_id = col.metadata.get("id", f"col-{index}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = [
        i for i in range(worksheet.row_count)
        if i < len(col.values) and col.values[i] is not None and not (isinstance(col.values[i], float) and math.isnan(col.values[i]))
    ]
    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]
    fingerprint = compute_data_fingerprint(worksheet, [index])

    stats = {
        "mean": result.get("mean"),
        "stdev_within": result.get("stdev_within"),
        "stdev_overall": result.get("stdev_overall"),
        "cp": result.get("cp"),
        "cpk": result.get("cpk"),
        "pp": result.get("pp"),
        "ppk": result.get("ppk"),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="normal_capability",
        title=f"Process Capability: {col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=col_id,
        response_name=col.name,
        predictor_col_ids=[],
        predictor_names=[],
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "lsl": lsl or result.get("lsl"),
            "usl": usl or result.get("usl"),
            "target": target or result.get("target"),
        }
    )
    from .connect_r import generate_r_capability_script
    connected.r_script = generate_r_capability_script(connected, worksheet)
    return connected


def create_connected_imr(
    worksheet: Worksheet,
    index: int,
    result: Dict[str, Any],
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from an I-MR chart result."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")
    col = worksheet.columns[index] if 0 <= index < len(worksheet.columns) else Column("Variable", "number", [])
    col_id = col.metadata.get("id", f"col-{index}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = [
        i for i in range(worksheet.row_count)
        if i < len(col.values) and col.values[i] is not None and not (isinstance(col.values[i], float) and math.isnan(col.values[i]))
    ]
    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]
    fingerprint = compute_data_fingerprint(worksheet, [index])

    stats = {
        "i_center": result.get("i_center"),
        "i_ucl": result.get("i_ucl"),
        "i_lcl": result.get("i_lcl"),
        "mr_center": result.get("mr_center"),
        "mr_ucl": result.get("mr_ucl"),
        "mr_lcl": result.get("mr_lcl"),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="individuals_moving_range",
        title=f"I-MR Chart: {col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=col_id,
        response_name=col.name,
        predictor_col_ids=[],
        predictor_names=[],
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "i_signals": result.get("i_signals", []),
            "mr_signals": result.get("mr_signals", []),
        }
    )
    from .connect_r import generate_r_imr_script
    connected.r_script = generate_r_imr_script(connected, worksheet)
    return connected


def create_connected_gage_rr(
    worksheet: Worksheet,
    measurement_index: int,
    part_index: int,
    operator_index: int,
    result: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a crossed Gage R&R study."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")

    meas_col = worksheet.columns[measurement_index] if 0 <= measurement_index < len(worksheet.columns) else Column("Measurement", "number", [])
    part_col = worksheet.columns[part_index] if 0 <= part_index < len(worksheet.columns) else Column("Part", "text", [])
    oper_col = worksheet.columns[operator_index] if 0 <= operator_index < len(worksheet.columns) else Column("Operator", "text", [])

    meas_id = meas_col.metadata.get("id", f"col-{measurement_index}")
    part_id = part_col.metadata.get("id", f"col-{part_index}")
    oper_id = oper_col.metadata.get("id", f"col-{operator_index}")

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = [
        i for i in range(worksheet.row_count)
        if (i < len(meas_col.values) and meas_col.values[i] is not None and not (isinstance(meas_col.values[i], float) and math.isnan(meas_col.values[i])))
        and (i < len(part_col.values) and part_col.values[i] is not None)
        and (i < len(oper_col.values) and oper_col.values[i] is not None)
    ]
    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]
    fingerprint = compute_data_fingerprint(worksheet, [measurement_index, part_index, operator_index])

    stats = {
        "variance_components": result.get("variance_components"),
        "study_variation": result.get("study_variation"),
        "ndc": result.get("ndc"),
    }

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type="gage_rr",
        title=f"Gage R&R Study (Crossed): {meas_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=meas_id,
        response_name=meas_col.name,
        predictor_col_ids=[part_id, oper_id],
        predictor_names=[part_col.name, oper_col.name],
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "part_index": part_index,
            "operator_index": operator_index,
            "measurement_index": measurement_index,
            "options": options or result.get("options", {}),
        },
    )

    from .connect_r import generate_r_gage_rr_script
    connected.r_script = generate_r_gage_rr_script(connected, worksheet)
    return connected


def create_connected_subgroup_spc(
    worksheet: Worksheet,
    response_index: int,
    factor_index: Optional[int] = None,
    subgroup_size: Optional[int] = None,
    chart_type: str = "xbar_r",
    result: Optional[Dict[str, Any]] = None,
    stacked: bool = True,
    options: Optional[Dict[str, Any]] = None,
) -> ConnectedAnalysis:
    """Create a ConnectedAnalysis record from a subgroup SPC chart (Xbar-R / Xbar-S)."""
    ensure_worksheet_identities(worksheet)
    ws_id = worksheet.metadata.get("id", "ws-default")

    res = result or {}
    meas_col = worksheet.columns[response_index] if 0 <= response_index < len(worksheet.columns) else Column("Measurement", "number", [])
    meas_id = meas_col.metadata.get("id", f"col-{response_index}")

    pred_ids = []
    pred_names = []
    if factor_index is not None and 0 <= factor_index < len(worksheet.columns):
        fac_col = worksheet.columns[factor_index]
        pred_ids.append(fac_col.metadata.get("id", f"col-{factor_index}"))
        pred_names.append(fac_col.name)

    all_row_ids = list(worksheet.metadata.get("row_ids", []))
    complete_indices = [
        i for i in range(worksheet.row_count)
        if i < len(meas_col.values) and meas_col.values[i] is not None and not (isinstance(meas_col.values[i], float) and math.isnan(meas_col.values[i]))
    ]
    fitted_row_ids = [all_row_ids[i] for i in complete_indices if i < len(all_row_ids)]
    omitted_row_ids = [rid for i, rid in enumerate(all_row_ids) if i not in complete_indices]
    cols_to_hash = [response_index] if factor_index is None else [response_index, factor_index]
    fingerprint = compute_data_fingerprint(worksheet, cols_to_hash)

    stats = {
        "xbar_center": res.get("xbar_center"),
        "xbar_ucl": res.get("xbar_ucl"),
        "xbar_lcl": res.get("xbar_lcl"),
        "disp_center": res.get("disp_center"),
        "disp_ucl": res.get("disp_ucl"),
        "disp_lcl": res.get("disp_lcl"),
        "within_stdev": res.get("within_stdev"),
        "k_subgroups": res.get("k_subgroups"),
    }

    c_type = res.get("chart_type") or chart_type or "xbar_r"
    chart_name = "Xbar-R Chart" if c_type == "xbar_r" else "Xbar-S Chart"

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type=c_type,
        title=f"{chart_name}: {meas_col.name}",
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=fingerprint,
        response_col_id=meas_id,
        response_name=meas_col.name,
        predictor_col_ids=pred_ids,
        predictor_names=pred_names,
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=fitted_row_ids,
        omitted_row_ids=omitted_row_ids,
        coefficients=[],
        statistics=stats,
        fitted_values=[],
        residuals=[],
        metadata={
            "response_index": response_index,
            "factor_index": factor_index,
            "subgroup_size": subgroup_size or res.get("subgroup_size"),
            "chart_type": c_type,
            "stacked": stacked,
            "options": options or res.get("options", {}),
        },
    )

    from .connect_r import generate_r_subgroup_spc_script
    connected.r_script = generate_r_subgroup_spc_script(connected, worksheet)
    return connected


def create_connected_generic(entry: Dict[str, Any], worksheet: Worksheet) -> ConnectedAnalysis:
    """Create a universal ConnectedAnalysis record with pure Base R script for any procedure."""
    meta = worksheet.metadata if isinstance(worksheet.metadata, dict) else {}
    ws_id = meta.get("id", "ws-default")
    recipe = entry.get("recipe", {})
    action = recipe.get("action", "analysis")
    title = entry.get("title") or f"StatCraft: {action.replace('_', ' ').title()}"

    all_row_ids = list(meta.get("row_ids", []))
    from .connect_r import generate_generic_r_script
    r_code = generate_generic_r_script(entry, worksheet)

    connected = ConnectedAnalysis(
        analysis_id=str(uuid.uuid4()),
        analysis_type=action,
        title=title,
        engine="statcraft",
        created_at=datetime.now().isoformat(),
        worksheet_id=ws_id,
        worksheet_name=worksheet.name,
        data_fingerprint=compute_data_fingerprint(worksheet, list(range(len(worksheet.columns)))),
        response_col_id="generic",
        response_name="Generic",
        predictor_col_ids=[],
        predictor_names=[],
        confidence=0.95,
        row_ids=all_row_ids,
        fitted_row_ids=all_row_ids,
        omitted_row_ids=[],
        coefficients=[],
        statistics={},
        fitted_values=[],
        residuals=[],
        metadata={"recipe": recipe, "entry_title": title},
        r_script=r_code,
    )
    return connected


def create_connected_analysis_from_entry(entry: Dict[str, Any], worksheet: Worksheet) -> Optional[ConnectedAnalysis]:
    """Universal factory to create or restore a ConnectedAnalysis contract from any history entry."""
    if not entry or entry.get("origin") == "native" or entry.get("result", {}).get("analysis") == "native_saved_output":
        return None
    conn_raw = entry.get("connected_analysis")
    if isinstance(conn_raw, dict):
        try:
            return ConnectedAnalysis.from_dict(conn_raw)
        except Exception:
            pass
    elif hasattr(conn_raw, "response_name"):
        return conn_raw

    recipe = entry.get("recipe", {})
    action = recipe.get("action")
    p = recipe.get("parameters", {})
    res = entry.get("result", {})

    conn: Optional[ConnectedAnalysis] = None
    if action == "multiple_regression" and "response_index" in p:
        conn = create_connected_regression(worksheet, p["response_index"], p["predictor_indices"], res, p.get("confidence", 0.95))
    elif action in ("analyze_response_surface", "response_surface") and "response_index" in p:
        conf = p.get("options", {}).get("confidence", 0.95) if isinstance(p.get("options"), dict) else 0.95
        conn = create_connected_response_surface(
            worksheet, p["response_index"], p["factor_indices"], res, conf,
            coding=p.get("coding"), terms=p.get("terms"), options=p.get("options")
        )
    elif action in ("oneway_anova", "one_way_anova") and "response_index" in p and "factor_index" in p:
        conn = create_connected_oneway_anova(
            worksheet, p["response_index"], p["factor_index"], res, p.get("options")
        )
    elif action in ("analyze_factorial", "analyze_factorial_terms", "factorial_regression") and "response_index" in p and "factor_indices" in p:
        conn = create_connected_factorial(
            worksheet, p["response_index"], p["factor_indices"], res,
            confidence=p.get("confidence", 0.95), selected_terms=p.get("selected_terms")
        )
    elif action in ("general_linear_model", "glm") and "response_index" in p and "factor_indices" in p:
        conn = create_connected_glm(
            worksheet, p["response_index"], p.get("factor_indices", []),
            p.get("covariate_indices", []), res, terms=p.get("terms"), options=p.get("options")
        )
    elif action == "two_sample_t":
        settings = p.get("settings", {})
        conn = create_connected_two_sample_t(worksheet, settings, res)
    elif action == "one_sample_t":
        settings = p.get("settings", {})
        conn = create_connected_one_sample_t(worksheet, settings, res)
    elif action == "paired_t":
        settings = p.get("settings", {})
        conn = create_connected_paired_t(worksheet, settings, res)
    elif action == "correlation":
        indices = p.get("indices", [])
        conn = create_connected_correlation(
            worksheet, indices, res,
            method=p.get("method", "Pearson"),
            missing=p.get("missing", "Pairwise"),
            confidence=p.get("confidence", 0.95),
        )
    elif action in ("histogram_graphs", "histogram") or (action == "graph" and p.get("method") == "histogram"):
        idx_list = p.get("response_indices") or p.get("indices")
        if idx_list is None and "index" in p:
            idx_list = [p["index"]]
        if not idx_list:
            idx_list = [0]
        variant = p.get("variant", "fit" if "fit" in str(entry.get("title", "")).lower() else "simple")
        conn = create_connected_histogram(worksheet, idx_list, res, variant=variant, bins=p.get("bins"))
    elif res.get("graph") in ("histogram", "histogram_graphs"):
        idx_list = p.get("response_indices") or p.get("indices") or [0]
        conn = create_connected_histogram(worksheet, idx_list, res, variant=p.get("variant", "simple"), bins=p.get("bins"))
    elif action in ("describe_columns", "descriptive_statistics", "describe_column"):
        indices = p.get("indices")
        if indices is None and "index" in p:
            indices = [p["index"]]
        conn = create_connected_descriptives(worksheet, indices or [], res)
    elif action in ("twoway_anova", "two_way_anova") and "response_index" in p and "factor_a_index" in p and "factor_b_index" in p:
        conn = create_connected_twoway_anova(
            worksheet, p["response_index"], p["factor_a_index"], p["factor_b_index"], res,
            fit_interaction=p.get("fit_interaction", True), confidence=p.get("confidence", 0.95)
        )
    elif action in ("fit_binary_logistic", "binary_logistic") and "response_index" in p:
        conn = create_connected_binary_logistic(
            worksheet, p["response_index"], p.get("continuous_indices", []),
            p.get("categorical_indices", []), res, event=p.get("event"), options=p.get("options")
        )
    elif action in ("normal_capability", "process_capability", "capability"):
        idx_c = p.get("index") or p.get("variable_index", 0)
        conn = create_connected_capability(
            worksheet, idx_c, res, lsl=p.get("lsl"), usl=p.get("usl"), target=p.get("target")
        )
    elif action in ("individuals_moving_range", "imr_chart", "imr"):
        idx_imr = p.get("index") or p.get("variable_index", 0)
        conn = create_connected_imr(worksheet, idx_imr, res)
    elif action in ("gage_rr", "gage_rr_crossed", "crossed_gage_rr") and "measurement_index" in p and "part_index" in p and "operator_index" in p:
        conn = create_connected_gage_rr(
            worksheet, p["measurement_index"], p["part_index"], p["operator_index"], res, options=p.get("options")
        )
    elif action in ("subgroup_control_chart", "xbar_r_chart", "xbar_s_chart", "xbar_r_stacked", "xbar_s_stacked", "xbar_r", "xbar_s"):
        c_type = p.get("chart_type") or ("xbar_s" if "xbar_s" in action else "xbar_r")
        resp_idx = p.get("response_index")
        if resp_idx is None and "index" in p:
            resp_idx = p["index"]
        if resp_idx is not None:
            conn = create_connected_subgroup_spc(
                worksheet,
                response_index=resp_idx,
                factor_index=p.get("factor_index"),
                subgroup_size=p.get("subgroup_size"),
                chart_type=c_type,
                result=res,
                stacked=p.get("stacked", True),
                options=p.get("options"),
            )

    if conn is None:
        conn = create_connected_generic(entry, worksheet)

    if conn is not None:
        entry["connected_analysis"] = conn.to_dict()
    return conn

