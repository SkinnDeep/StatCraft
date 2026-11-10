"""Vectorized Formula Engine for StatCraft Worksheet Columns.

Evaluates safe, sandboxed mathematical expressions over worksheet columns with
NumPy speed, supporting Excel-like syntax (= C1 * 1.05) and instant live previews.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from .model import Column, Worksheet


SAFE_MATH_NAMES = {
    "abs": np.abs,
    "sqrt": np.sqrt,
    "log": np.log,
    "log10": np.log10,
    "exp": np.exp,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "round": np.round,
    "where": np.where,
    "if_else": np.where,
    "mean": np.nanmean,
    "std": np.nanstd,
    "min": np.nanmin,
    "max": np.nanmax,
    "pi": math.pi,
    "e": math.e,
}


def _clean_formula_string(formula: str) -> str:
    expr = formula.strip()
    if expr.startswith("="):
        expr = expr[1:].strip()
    return expr


def evaluate_formula(formula: str, worksheet: Worksheet) -> Tuple[Optional[List[Any]], Optional[str]]:
    """Safely evaluate expression over worksheet columns. Returns (results_list, error_msg)."""
    expr = _clean_formula_string(formula)
    if not expr:
        return None, "Empty formula."

    n_rows = worksheet.row_count
    if n_rows == 0:
        return [], None

    env: Dict[str, Any] = dict(SAFE_MATH_NAMES)

    # Populate column arrays into evaluation environment
    # Both by C1, C2 canonical labels and by exact column names
    for idx, col in enumerate(worksheet.columns, 1):
        c_label = f"C{idx}"
        c_label_lower = f"c{idx}"

        if col.kind == "number":
            arr = np.array([float(v) if v is not None and math.isfinite(v) else np.nan for v in col.values], dtype=float)
        else:
            arr = np.array([str(v) if v is not None else "" for v in col.values])

        env[c_label] = arr
        env[c_label_lower] = arr

        # Clean sanitized identifier for column name (e.g. Yield_Strength)
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", col.name)
        if clean_name and clean_name.isidentifier():
            env[clean_name] = arr

    # Support bracket syntax [Column Name]
    def _replace_brackets(match):
        col_name = match.group(1).strip()
        for idx, c in enumerate(worksheet.columns, 1):
            if c.name.strip().lower() == col_name.lower():
                return f"C{idx}"
        return match.group(0)

    clean_expr = re.sub(r"\[(.*?)\]", _replace_brackets, expr)

    # Security check: disallow dangerous builtins
    disallowed = ("__", "import", "exec", "eval", "compile", "open", "os", "sys", "globals", "locals")
    if any(term in clean_expr.lower() for term in disallowed):
        return None, "Formula contains unauthorized keywords."

    try:
        # Evaluate in restricted environment
        res = eval(clean_expr, {"__builtins__": {}}, env)

        # Convert numpy result to standard python list
        if isinstance(res, np.ndarray):
            out: List[Any] = []
            for item in res:
                if isinstance(item, (np.floating, float)):
                    out.append(None if (math.isnan(item) or not math.isfinite(item)) else float(item))
                elif isinstance(item, (np.integer, int)):
                    out.append(int(item))
                else:
                    out.append(str(item))
            # Ensure length matches n_rows
            if len(out) < n_rows:
                out.extend([None] * (n_rows - len(out)))
            return out[:n_rows], None

        elif isinstance(res, (int, float)):
            val = float(res) if math.isfinite(res) else None
            return [val] * n_rows, None

        else:
            return None, f"Unsupported formula result type: {type(res).__name__}"

    except Exception as exc:
        return None, f"Formula error: {exc}"


def preview_formula(formula: str, worksheet: Worksheet, n_preview: int = 5) -> Tuple[List[Any], Optional[str]]:
    """Instant live preview of first n_preview calculated rows."""
    res, err = evaluate_formula(formula, worksheet)
    if err or res is None:
        return [], err
    return res[:n_preview], None
