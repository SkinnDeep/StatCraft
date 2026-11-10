"""Dynamic conditional colors, independent of manually assigned cell colors.

Rules are original StatCraft metadata. Rank ties are all included; outliers use
the existing StatCraft indexed quartiles and 1.5 IQR fences. Native equivalence
of those statistical details has not been established.

Old versions baked rule colors into cell_highlights without recording their
source. Preserve that mapping during migration: even a matching color may have
been assigned manually. legacy_conditional_candidates is a diagnostic only;
it must not be used to silently delete colors. New writes should store rules
alone and render this module's overlay above the independent manual mapping.
"""
import math
import re


RULE_TYPES = frozenset((
    "missing", "greater_than", "less_than", "equal_to",
    "between", "contains", "highest", "lowest", "outlier",
    "above_mean", "below_mean", "outside_3sigma", "outside_specs",
    "top_percent", "bottom_percent",
))
_FIELDS = frozenset(("type", "param1", "param2", "color"))


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{label} must be a finite number.")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number.")
    return result


def validate_rule(rule):
    """Return a detached, normalized rule; reject malformed parameters."""
    if not isinstance(rule, dict) or set(rule) - _FIELDS:
        raise ValueError("Conditional formatting requires a valid rule object.")
    kind = rule.get("type")
    if not isinstance(kind, str) or kind not in RULE_TYPES:
        raise ValueError("Unsupported conditional formatting rule.")
    color = rule.get("color", "#f8d7da")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Conditional formatting color must be #RRGGBB.")
    first, second = rule.get("param1"), rule.get("param2")
    if kind in ("greater_than", "less_than", "between"):
        first = _number(first, "Value")
        if kind == "between":
            second = _number(second, "Maximum")
            first, second = min(first, second), max(first, second)
        else:
            second = None
    elif kind in ("highest", "lowest"):
        first = _number(3 if first is None else first, "Count")
        if first < 1 or not first.is_integer():
            raise ValueError("Count must be a positive whole number.")
        first, second = int(first), None
    elif kind in ("top_percent", "bottom_percent"):
        first = _number(10 if first is None else first, "Percent")
        if not 0 < first <= 100:
            raise ValueError("Percent must be between 0 (exclusive) and 100.")
        second = None
    elif kind == "outside_specs":
        has_lsl = first is not None and str(first).strip() != ""
        has_usl = second is not None and str(second).strip() != ""
        if not has_lsl and not has_usl:
            raise ValueError("Specify at least one specification limit (LSL or USL).")
        first = _number(first, "LSL") if has_lsl else None
        second = _number(second, "USL") if has_usl else None
        if first is not None and second is not None and first > second:
            first, second = second, first
    elif kind in ("equal_to", "contains"):
        if isinstance(first, bool) or not isinstance(first, (str, int, float)):
            raise ValueError("Enter a text or numeric comparison value.")
        if isinstance(first, (int, float)):
            first = _number(first, "Value")
        if kind == "contains":
            first = str(first)
            if not first:
                raise ValueError("Enter text to search for.")
        second = None
    else:
        first = second = None
    return {"type": kind, "param1": first, "param2": second, "color": color.lower()}


def validate_rules(rules):
    """Validate the complete collection before anything can be applied."""
    if not isinstance(rules, (list, tuple)):
        raise ValueError("Conditional formatting rules must be a list.")
    return [validate_rule(rule) for rule in rules]


def effective_highlights(column, row_count=None, rules=None):
    """Compute fresh conditional colors with zero-based string row keys.

    Include missing rows up to worksheet row_count, but never invent rows past
    that extent for display padding. Last matching rule wins. No state changes.
    Invalid persisted rules raise ValueError so callers can show a diagnostic
    rather than partially applying a broken rule collection.
    """
    column.validate()
    if row_count is None:
        row_count = len(column.values)
    if type(row_count) is not int or row_count < 0:
        raise ValueError("Worksheet row count must be a nonnegative integer.")
    count = max(row_count, len(column.values))
    checked = validate_rules(column.metadata.get("conditional_rules", []) if rules is None else rules)
    ordered = sorted(float(value) for value in column.values
                     if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))
    col_mean = sum(ordered) / len(ordered) if ordered else None
    sigma_fences = None
    if len(ordered) >= 2 and col_mean is not None:
        s = math.sqrt(sum((v - col_mean) ** 2 for v in ordered) / (len(ordered) - 1))
        if s > 0:
            sigma_fences = (col_mean - 3.0 * s, col_mean + 3.0 * s)

    result = {}
    for rule in checked:
        kind, first, second = rule["type"], rule["param1"], rule["param2"]
        cutoff = None
        if kind in ("highest", "lowest") and ordered:
            position = min(first, len(ordered))
            cutoff = ordered[-position] if kind == "highest" else ordered[position - 1]
        elif kind in ("top_percent", "bottom_percent") and ordered:
            position = max(1, int((first / 100.0) * len(ordered)))
            cutoff = ordered[-position] if kind == "top_percent" else ordered[position - 1]
        fences = None
        if kind == "outlier" and len(ordered) >= 4:
            q1, q3 = ordered[len(ordered) // 4], ordered[(3 * len(ordered)) // 4]
            spread = q3 - q1
            fences = q1 - 1.5 * spread, q3 + 1.5 * spread
        for row in range(count):
            value = column.values[row] if row < len(column.values) else None
            missing = value is None or (column.kind == "text" and value == "")
            number = isinstance(value, (int, float)) and not isinstance(value, bool)
            match = kind == "missing" and missing
            if not missing:
                if kind == "greater_than" and number:
                    match = value > first
                elif kind == "less_than" and number:
                    match = value < first
                elif kind == "between" and number:
                    match = first <= value <= second
                elif kind == "equal_to":
                    try:
                        match = value == _number(first, "Value") if number else str(value).casefold() == str(first).casefold()
                    except ValueError:
                        match = False
                elif kind == "contains":
                    match = str(first).casefold() in str(value).casefold()
                elif kind in ("highest", "top_percent") and number and cutoff is not None:
                    match = value >= cutoff
                elif kind in ("lowest", "bottom_percent") and number and cutoff is not None:
                    match = value <= cutoff
                elif kind == "outlier" and number and fences:
                    match = value < fences[0] or value > fences[1]
                elif kind == "above_mean" and number and col_mean is not None:
                    match = value > col_mean
                elif kind == "below_mean" and number and col_mean is not None:
                    match = value < col_mean
                elif kind == "outside_3sigma" and number and sigma_fences is not None:
                    match = value < sigma_fences[0] or value > sigma_fences[1]
                elif kind == "outside_specs" and number:
                    match = (first is not None and value < first) or (second is not None and value > second)
            if match:
                result[str(row)] = rule["color"]
    return result


def legacy_conditional_candidates(column, row_count=None):
    """Report currently matching baked colors; provenance remains ambiguous."""
    overlay = effective_highlights(column, row_count)
    manual = column.metadata.get("cell_highlights", {})
    return {row: color for row, color in overlay.items()
            if isinstance(manual, dict) and isinstance(manual.get(row), str)
            and manual[row].casefold() == color.casefold()}
