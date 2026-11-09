"""Computational engine for Data Recoding (Data > Recode).

Matches Minitab recoding behavior:
- Recode to Numeric (from Text or Numeric)
- Recode to Text (from Numeric or Text)
- Exact value mapping (case-insensitive option, whitespace trimming)
- Numeric range mapping (low to high intervals)
- Missing value handling (* or None)
- In-place replacement or new column generation
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _parse_numeric(val: Any) -> Optional[float]:
    """Parse a value into float, returning None if missing or non-numeric."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if math.isfinite(val) else None
    s = str(val).strip()
    if not s or s == "*":
        return None
    try:
        f = float(s)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def recode_value(
    val: Any,
    rules: Sequence[Dict[str, Any]],
    target_kind: str = "number",
    default_action: str = "original",
    default_value: Any = None,
) -> Any:
    """Recode a single value according to ordered rules.
    
    Rule structures:
    - {'type': 'exact', 'current': 'A', 'recoded': 1}
    - {'type': 'range', 'low': 0.0, 'high': 10.0, 'recoded': 1, 'inc_low': True, 'inc_high': True}
    - {'type': 'missing', 'recoded': 0}
    """
    matched = False
    result_val: Any = None

    for rule in rules:
        rtype = rule.get("type", "exact")
        if rtype == "missing":
            if val is None or (isinstance(val, float) and math.isnan(val)) or str(val).strip() in ("", "*"):
                matched = True
                result_val = rule.get("recoded")
                break
        elif rtype == "exact":
            curr = rule.get("current")
            # Compare both as strings and as floats if numeric
            val_num = _parse_numeric(val)
            curr_num = _parse_numeric(curr)
            if val_num is not None and curr_num is not None:
                if math.isclose(val_num, curr_num, rel_tol=1e-9, abs_tol=1e-12):
                    matched = True
                    result_val = rule.get("recoded")
                    break
            else:
                s_val = "" if val is None else str(val).strip().lower()
                s_curr = "" if curr is None else str(curr).strip().lower()
                if s_val == s_curr:
                    matched = True
                    result_val = rule.get("recoded")
                    break
        elif rtype == "range":
            val_num = _parse_numeric(val)
            if val_num is not None:
                low = rule.get("low", float("-inf"))
                high = rule.get("high", float("inf"))
                inc_low = rule.get("inc_low", True)
                inc_high = rule.get("inc_high", True)

                cond_low = (val_num >= low) if inc_low else (val_num > low)
                cond_high = (val_num <= high) if inc_high else (val_num < high)

                if cond_low and cond_high:
                    matched = True
                    result_val = rule.get("recoded")
                    break

    if not matched:
        if default_action == "specified":
            result_val = default_value
        else:
            # Default action is 'original'
            result_val = val

    # Cast to target kind
    if target_kind == "number":
        return _parse_numeric(result_val)
    else:
        if result_val is None:
            return ""
        return str(result_val)


def recode_column(
    values: Sequence[Any],
    rules: Sequence[Dict[str, Any]],
    target_kind: str = "number",
    default_action: str = "original",
    default_value: Any = None,
) -> List[Any]:
    """Recode an entire column of values according to specified rules."""
    target_kind = "number" if target_kind.lower() in ("number", "numeric") else "text"
    recoded: List[Any] = []
    for v in values:
        recoded.append(
            recode_value(
                v,
                rules=rules,
                target_kind=target_kind,
                default_action=default_action,
                default_value=default_value,
            )
        )
    return recoded
