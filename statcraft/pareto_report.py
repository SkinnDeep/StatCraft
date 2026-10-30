"""Report generator for Pareto Chart (Stat > Quality Tools > Pareto Chart).

Generates plain-text session window reports matching StatCraft output formatting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 1) -> str:
    if val is None:
        return "*"
    return f"{val:.{dec}f}"


def generate_pareto_report(result: Dict[str, Any]) -> str:
    """Generate session window report for Pareto Chart."""
    var_name = str(result.get("variable_name", "Defects"))
    title = f"Pareto Chart of {var_name}"
    lines: List[str] = [title, "=" * len(title), ""]

    categories = result.get("categories", [])
    counts = result.get("counts", [])
    percents = result.get("percents", [])
    cum_percents = result.get("cum_percents", [])
    total_count = result.get("total_count", 0.0)

    # Table Header
    col_width = max(18, max((len(str(c)) for c in categories), default=18))
    header = f"  {('Defect Category').ljust(col_width)}  {'Count':>8}  {'Percent':>8}  {'Cum %':>8}"
    lines.append(header)
    lines.append("  " + "-" * (col_width + 30))

    # Table Rows
    for cat, cnt, pct, cum_pct in zip(categories, counts, percents, cum_percents):
        cnt_str = f"{int(cnt)}" if cnt == int(cnt) else f"{cnt:.1f}"
        row_str = f"  {str(cat).ljust(col_width)}  {cnt_str:>8}  {_fmt(pct, 1):>8}  {_fmt(cum_pct, 1):>8}"
        lines.append(row_str)

    lines.append("  " + "-" * (col_width + 30))
    total_cnt_str = f"{int(total_count)}" if total_count == int(total_count) else f"{total_count:.1f}"
    lines.append(f"  {('Total').ljust(col_width)}  {total_cnt_str:>8}  {'100.0':>8}")
    lines.append("")

    other_cnt = result.get("other_count", 0.0)
    other_subs = result.get("other_subcategories", 0)
    if other_cnt > 0:
        lines.append(f"  * NOTE * 'Other' includes {other_subs} categories with cumulative counts beyond threshold.")
        lines.append("")

    return "\n".join(lines)
