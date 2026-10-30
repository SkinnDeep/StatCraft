"""Report generator for Time-Weighted Control Charts (EWMA, Moving Average, CUSUM).

Generates plain-text session window reports matching StatCraft output formatting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None:
        return "*"
    return f"{val:.{dec}f}"


def generate_time_weighted_report(result: Dict[str, Any]) -> str:
    """Generate session text report for EWMA, Moving Average, or CUSUM chart."""
    chart_type = str(result.get("chart_type", "EWMA")).upper()
    var_name = str(result.get("variable_name", "Data"))
    lines: List[str] = []

    if chart_type == "EWMA":
        title = f"EWMA Chart of {var_name}"
    elif chart_type in ("MA", "MOVING_AVERAGE"):
        title = f"Moving Average Chart of {var_name}"
    elif chart_type == "CUSUM":
        title = f"CUSUM Chart of {var_name}"
    else:
        title = f"{chart_type} Chart of {var_name}"

    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Process Information
    lines.append("Process Information")
    lines.append("-" * 30)
    lines.append(f"  Subgroups:           {result.get('k_subgroups', 0)}")
    
    sizes = result.get("subgroup_sizes", [])
    if sizes:
        if len(set(sizes)) == 1:
            lines.append(f"  Subgroup Size:       {sizes[0]}")
        else:
            lines.append(f"  Subgroup Size:       Varies (min={min(sizes)}, max={max(sizes)})")

    if chart_type == "EWMA":
        lines.append(f"  Weight of EWMA:      {_fmt(result.get('weight'), 4)}")
        lines.append(f"  Center Line (Mean):  {_fmt(result.get('center_line'), 4)}")
        lines.append(f"  Estimated Sigma:     {_fmt(result.get('sigma'), 4)}")
    elif chart_type in ("MA", "MOVING_AVERAGE"):
        lines.append(f"  Length of MA (Span): {result.get('span', 3)}")
        lines.append(f"  Center Line (Mean):  {_fmt(result.get('center_line'), 4)}")
        lines.append(f"  Estimated Sigma:     {_fmt(result.get('sigma'), 4)}")
    elif chart_type == "CUSUM":
        lines.append(f"  Target:              {_fmt(result.get('target'), 4)}")
        lines.append(f"  Estimated Sigma:     {_fmt(result.get('sigma'), 4)}")
        lines.append(f"  h (Decision Int):    {_fmt(result.get('h'), 4)}")
        lines.append(f"  k (Slack):           {_fmt(result.get('k'), 4)}")
        if result.get("use_fir"):
            lines.append(f"  FIR (Headstart):     {_fmt(result.get('fir'), 4)}")
        if result.get("reset"):
            lines.append("  Reset:               Yes (after out of control)")

    omits = result.get("omit_subgroups", [])
    if omits:
        lines.append(f"  Omitted Subgroups:   {omits}")

    lines.append("")

    # Test Results
    signals = result.get("signals", [])
    lines.append("Test Results for Out-of-Control Points")
    lines.append("-" * 45)
    if not signals:
        lines.append("  Test 1: One point beyond control limits.")
        lines.append("  * NOTE * No points were found to be out of control.")
    else:
        lines.append("  Test 1: One point beyond control limits.")
        lines.append("  Test Failed at Subgroup(s):")
        # Format signals in wrapped list
        sig_strs = [str(s) for s in sorted(signals)]
        lines.append("    " + ", ".join(sig_strs))

    lines.append("")
    return "\n".join(lines)
