"""Session window text report generator for Individuals-Moving Range (I-MR) Chart.

Matches StatCraft output formatting:
- Analysis title
- Test Results for I Chart of <Variable>
- Test Results for MR Chart of <Variable>
- Specific points that failed each Nelson test
- Omission notes and warning messages
"""
from __future__ import annotations

from typing import Any, Dict, List


TEST_DESCRIPTIONS = {
    1: "One point more than {k:.2f} standard deviations from center line.",
    2: "{k} points in a row on same side of center line.",
    3: "{k} points in a row, all increasing or all decreasing.",
    4: "{k} points in a row, alternating up and down.",
}


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_imr_report(result: Dict[str, Any]) -> str:
    """Format full session text report matching StatCraft."""
    var_name = result.get("variable_name", result.get("variable", "Data"))
    lines: List[str] = [
        f"\n\nI-MR Chart of {var_name}",
        "",
    ]

    opts = result.get("options", {})
    tests_cfg = opts.get("tests", {})

    # I Chart Test Results
    i_test_failures = result.get("test_failures", {})
    # Invert mapping from point -> [tests] to test -> [points]
    test_to_pts: Dict[int, List[int]] = {}
    for pt, test_list in i_test_failures.items():
        for t in test_list:
            test_to_pts.setdefault(t, []).append(pt)

    if test_to_pts:
        lines.append(f"Test Results for I Chart of {var_name}")
        for t_num in sorted(test_to_pts.keys()):
            pts_str = ", ".join(str(p) for p in sorted(test_to_pts[t_num]))
            k_val = 3.0
            if t_num == 1:
                k_val = float(tests_cfg.get("test1", {}).get("k", 3.0))
            elif t_num == 2:
                k_val = int(tests_cfg.get("test2", {}).get("k", 9))
            elif t_num == 3:
                k_val = int(tests_cfg.get("test3", {}).get("k", 6))
            elif t_num == 4:
                k_val = int(tests_cfg.get("test4", {}).get("k", 14))

            desc_template = TEST_DESCRIPTIONS.get(t_num, f"Test {t_num}")
            desc = desc_template.format(k=k_val)
            lines.append(f"TEST {t_num}. {desc}")
            lines.append(f"* WARNING * Test Failed at points: {pts_str}")
        lines.append("")

    # MR Chart Test Results
    mr_signals = result.get("mr_signals", [])
    if mr_signals:
        lines.append(f"Test Results for MR Chart of {var_name}")
        pts_str = ", ".join(str(p) for p in sorted(mr_signals))
        lines.append("TEST 1. One point more than 3.00 standard deviations from center line.")
        lines.append(f"* WARNING * Test Failed at points: {pts_str}")
        lines.append("")

    # Summary parameters if no test failures or detailed info requested
    if not test_to_pts and not mr_signals:
        lines.append("No test failures detected.")
        lines.append("")

    lines.append("Process Information")
    lines.append(f"  Count:                {result.get('count', 0)}")
    lines.append(f"  Missing:              {result.get('missing', 0)}")
    lines.append(f"  Mean (I Center):      {_fmt(result.get('i_center'))}")
    lines.append(f"  I LCL:                {_fmt(result.get('i_lcl'))}")
    lines.append(f"  I UCL:                {_fmt(result.get('i_ucl'))}")
    if result.get('i_lwl') is not None and result.get('i_uwl') is not None:
        lines.append(f"  I LWL:                {_fmt(result.get('i_lwl'))}")
        lines.append(f"  I UWL:                {_fmt(result.get('i_uwl'))}")
    lines.append(f"  Within Sigma:         {_fmt(result.get('within_stdev'))}")
    lines.append(f"  MR Center:            {_fmt(result.get('mr_center'))}")
    lines.append(f"  MR LCL:               {_fmt(result.get('mr_lcl'))}")
    lines.append(f"  MR UCL:               {_fmt(result.get('mr_ucl'))}")
    if result.get('mr_lwl') is not None and result.get('mr_uwl') is not None:
        lines.append(f"  MR LWL:               {_fmt(result.get('mr_lwl'))}")
        lines.append(f"  MR UWL:               {_fmt(result.get('mr_uwl'))}")
    lines.append(f"  Moving Range Span:    {result.get('span', 2)}")

    method = result.get("estimation_method", "amr")
    method_name = {
        "amr": "Average moving range",
        "mmr": "Median moving range",
        "srmssd": "Square root of MSSD",
    }.get(method, method)
    lines.append(f"  Estimation Method:    {method_name}")

    warnings = result.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"  * {w}")

    return "\n".join(lines) + "\n"
