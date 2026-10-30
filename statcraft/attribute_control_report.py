"""Session window text report generator for Attributes Control Charts (P, NP, C, U).

Matches StatCraft output formatting:
- Analysis title (e.g. P Chart of <Variable>)
- Summary of process parameter (Center, Subgroup sizes)
- Test Results for <Chart> Chart of <Variable>
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


def format_attribute_control_report(result: Dict[str, Any]) -> str:
    """Format full session text report matching StatCraft."""
    chart_raw = str(result.get("chart_type", result.get("chart", "P"))).upper().strip().replace("′", "'")
    if chart_raw in ("P'", "P_PRIME", "LANEY_P"):
        chart_title = "Laney P' Chart"
    elif chart_raw in ("U'", "U_PRIME", "LANEY_U"):
        chart_title = "Laney U' Chart"
    else:
        chart_title = f"{chart_raw} Chart"

    var_name = result.get("variable_name", "Data")
    full_title = f"{chart_title} of {var_name}"

    lines: List[str] = [
        f"\n\n{full_title}",
        "",
    ]

    opts = result.get("options", {})
    tests_cfg = opts.get("tests", {})

    # Test Results
    test_failures = result.get("test_failures", {})
    test_to_pts: Dict[int, List[int]] = {}
    for pt, test_list in test_failures.items():
        for t in test_list:
            test_to_pts.setdefault(t, []).append(pt)

    if test_to_pts:
        lines.append(f"Test Results for {chart_title} of {var_name}")
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

            desc_tmpl = TEST_DESCRIPTIONS.get(t_num, "Test {k}")
            if t_num == 1:
                desc = desc_tmpl.format(k=k_val)
            else:
                desc = desc_tmpl.format(k=int(k_val))
            lines.append(f"TEST {t_num}. {desc}")
            lines.append(f"   Test Failed at points: {pts_str}")
        lines.append("")
        lines.append("* WARNING * If graph is updated with new data, the results above may no")
        lines.append("            longer be correct.")
        lines.append("")

    # Summary Information
    lines.append("Process Information")
    lines.append(f"  Variable:               {var_name}")
    is_const = result.get("is_constant_size", False)
    if is_const:
        c_size = result.get("constant_size", 1.0)
        lines.append(f"  Subgroup size:          {_fmt(c_size, 2 if c_size % 1 else 0)}")
    else:
        avg_sz = result.get("average_subgroup_size", 0.0)
        lines.append(f"  Average subgroup size:  {_fmt(avg_sz, 2)}")

    param_label = "p" if chart_raw in ("P", "P'", "NP") else "Mean (mu)"
    center_val = result.get("center")
    lines.append(f"  Center ({param_label}):         {_fmt(center_val, 4)}")
    if chart_raw in ("P'", "U'"):
        lines.append(f"  Sigma Z:                {_fmt(result.get('sigma_z', 1.0), 4)}")

    omitted = result.get("omitted_subgroups", [])
    if omitted:
        omit_str = ", ".join(str(x) for x in omitted)
        lines.append(f"  Subgroups omitted:      {omit_str}")

    if result.get("is_historical"):
        lines.append("  Note: Parameters were specified historically.")

    if not is_const:
        lines.append("  Note: Control limits vary with subgroup size.")
    else:
        ucl_list = [v for v in result.get("ucl", []) if v is not None]
        lcl_list = [v for v in result.get("lcl", []) if v is not None]
        if ucl_list:
            lines.append(f"  UCL:                    {_fmt(ucl_list[0], 4)}")
        if lcl_list:
            lines.append(f"  LCL:                    {_fmt(lcl_list[0], 4)}")

    lines.append("")
    return "\n".join(lines)
