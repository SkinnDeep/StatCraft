"""Report generator for Rare Event Control Charts (G Chart & T Chart).

Generates plain-text session window reports matching StatCraft output formatting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None:
        return "*"
    return f"{val:.{dec}f}"


def generate_rare_event_report(result: Dict[str, Any]) -> str:
    """Generate session text report for G Chart or T Chart."""
    chart_type = str(result.get("chart_type", "G")).upper()
    var_name = str(result.get("variable_name", "Data"))
    lines: List[str] = []

    title = f"{chart_type} Chart of {var_name}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Process Information
    lines.append("Process Information")
    lines.append("-" * 30)
    lines.append(f"  Observations:        {result.get('k_subgroups', 0)}")

    if chart_type == "G":
        m_count = result.get("method_of_count", 0)
        method_str = "Between events (0, 1, 2, ...)" if m_count == 0 else "Until an event (1, 2, 3, ...)"
        lines.append(f"  Counting Method:     {method_str}")
        lines.append(f"  Proportion (p):      {_fmt(result.get('p'), 5)}")
        lines.append(f"  Center Line (Median):{_fmt(result.get('center_line'), 4)}")
        lines.append(f"  UCL:                 {_fmt(result.get('ucl_val'), 4)}")
        lines.append(f"  LCL:                 {_fmt(result.get('lcl_val'), 4)}")
    elif chart_type == "T":
        lines.append(f"  Distribution:        {result.get('distribution', 'Weibull')}")
        lines.append(f"  Shape (Beta):        {_fmt(result.get('shape'), 4)}")
        lines.append(f"  Scale (Eta):         {_fmt(result.get('scale'), 4)}")
        lines.append(f"  Units:               {result.get('units', 'Days')}")
        lines.append(f"  Center Line:         {_fmt(result.get('center_line'), 4)}")
        lines.append(f"  UCL:                 {_fmt(result.get('ucl_val'), 4)}")
        lines.append(f"  LCL:                 {_fmt(result.get('lcl_val'), 4)}")

    omits = result.get("omit_subgroups", [])
    if omits:
        lines.append(f"  Omitted:             {omits}")

    lines.append("")

    # Test Results
    test1 = result.get("test1_signals", [])
    benneyan = result.get("benneyan_signals", [])

    lines.append("Test Results for Special Causes")
    lines.append("-" * 45)
    if not test1 and not benneyan:
        lines.append("  Test 1: One point beyond control limits.")
        lines.append("  * NOTE * No points were found to be out of control.")
    else:
        if test1:
            lines.append("  Test 1: One point beyond control limits.")
            lines.append("    Failed at Observation(s): " + ", ".join(str(s) for s in sorted(test1)))
        if benneyan:
            lines.append("  Benneyan Test: Consecutive observations of short intervals/zeros.")
            lines.append("    Failed at Observation(s): " + ", ".join(str(s) for s in sorted(benneyan)))

    lines.append("")
    return "\n".join(lines)
