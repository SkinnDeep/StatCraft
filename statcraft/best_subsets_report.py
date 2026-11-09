"""Session report formatter for Best Subsets Regression.

Generates authentic Minitab output table:
- Response and Predictors header
- Table columns: Vars, R-Sq, R-Sq(adj), C-p, s, followed by vertical/tabular predictor headers and 'X' indicators
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 1) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "*"
    return f"{val:.{dec}f}"


def generate_best_subsets_report(result: Dict[str, Any]) -> str:
    """Format Best Subsets Regression output matching Minitab session window."""
    lines: List[str] = []
    resp_name = result.get("response_name", "Y")
    free_names = result.get("free_names", [])
    forced_names = result.get("forced_names", [])
    models = result.get("models", [])

    all_names_str = ", ".join(forced_names + free_names)
    title = f"Best Subsets Regression: {resp_name} versus {all_names_str}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Response is {resp_name}")
    if forced_names:
        lines.append(f"Predictors in all models: {', '.join(forced_names)}")
    lines.append("")

    p_free = len(free_names)
    if not models or p_free == 0:
        lines.append("No models evaluated.")
        return "\n" + "\n".join(lines)

    # Determine vertical header depth for predictor names
    max_name_len = max(len(name) for name in free_names)
    header_chars: List[List[str]] = []
    for r in range(max_name_len):
        row_chars = []
        for name in free_names:
            if r < len(name):
                row_chars.append(name[r])
            else:
                row_chars.append(" ")
        header_chars.append(row_chars)

    # Left table header metrics
    # Vars   R-Sq  R-Sq(adj)      C-p          s
    prefix_len = 42

    for row_chars in header_chars:
        pred_header_str = "  ".join(f"{c:>2}" for c in row_chars)
        lines.append(" " * prefix_len + pred_header_str)

    lines.append(f"{'Vars':>5} {'R-Sq':>7} {'R-Sq(adj)':>10} {'C-p':>8} {'s':>10}")
    lines.append("-" * prefix_len + "-" * (p_free * 4))

    for m in models:
        v_count = m.get("vars", 0)
        r2 = _fmt(m.get("r2"), 1)
        r2_adj = _fmt(m.get("r2_adj"), 1)
        cp = _fmt(m.get("cp"), 1)
        s_val = _fmt(m.get("s"), 4)

        included = m.get("included_free", [])
        flags_str = "  ".join(f"{'X' if inc else ' ':>2}" for inc in included)

        lines.append(f"{v_count:>5} {r2:>7} {r2_adj:>10} {cp:>8} {s_val:>10}   {flags_str}")

    lines.append("")
    return "\n" + "\n".join(lines)
