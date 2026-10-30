"""Session window text report generator for Xbar-R and Xbar-S Subgroup Control Charts.

Matches StatCraft output format:
- Analysis title and variable name
- Parameter estimates and subgroup sizes
- Xbar and R / S control limits summary
- Nelson / Western Electric test results and warning messages
"""
from __future__ import annotations

from typing import Any


TEST_DESCRIPTIONS = {
    1: "One point more than {k:.2f} standard deviations from center line.",
    2: "{k} points in a row on same side of center line.",
    3: "{k} points in a row, all increasing or all decreasing.",
    4: "{k} points in a row, alternating up and down.",
    5: "{k} out of {k_plus_1} points > 2 standard deviations from center line (same side).",
    6: "{k} out of {k_plus_1} points > 1 standard deviations from center line (same side).",
    7: "{k} points in a row within 1 standard deviation of center line (either side).",
    8: "{k} points in a row > 1 standard deviation from center line (either side).",
}


def _fmt(val: float | None, precision: int = 4) -> str:
    if val is None:
        return "*"
    return f"{val:.{precision}f}"


def text_report(result: dict[str, Any]) -> str:
    """Generate fixed-width plain text report matching StatCraft."""
    chart_type = result.get('chart_type', 'xbar_r')
    chart_name = "Xbar-R Chart" if chart_type == 'xbar_r' else "Xbar-S Chart"
    var_name = result.get('variable_name', 'Data')
    opts = result.get('options', {})

    lines: list[str] = [
        f"{chart_name} of {var_name}",
        "",
    ]

    # Subgroup summary
    sizes = result.get('subgroup_sizes', [])
    k_sub = result.get('k_subgroups', 0)
    min_sz = min(sizes) if sizes else 0
    max_sz = max(sizes) if sizes else 0
    equal_sizes = (min_sz == max_sz)

    lines.append("Subgroup Information")
    lines.append(f"  Number of subgroups: {k_sub}")
    if equal_sizes:
        lines.append(f"  Subgroup size:       {min_sz}")
    else:
        lines.append(f"  Subgroup size:       Min: {min_sz}   Max: {max_sz}")
    lines.append("")

    # Parameters & Limits
    mean_cl = result.get('xbar_center', 0.0)
    sigma_hat = result.get('within_stdev', 0.0)
    disp_cl = result.get('disp_center')
    method_name = result.get('estimation_method', '')

    method_desc = {
        'rbar': "Average range (Rbar)",
        'sbar': "Average standard deviation (Sbar)",
        'pooled_stdev': "Pooled standard deviation",
    }.get(method_name, method_name)

    lines.append("Process Parameters and Limit Estimates")
    lines.append(f"  Estimated within-subgroup variation (sigma): {sigma_hat:.5f}")
    lines.append(f"  Estimation method:                          {method_desc}")
    if opts.get('historical_mean') is not None:
        lines.append(f"  Historical mean (mu):                       {opts['historical_mean']:.5f}")
    if opts.get('historical_sigma') is not None:
        lines.append(f"  Historical stdev (sigma):                   {opts['historical_sigma']:.5f}")
    lines.append("")

    lines.append(f"  Xbar Center Line: {mean_cl:.4f}")
    x_lcls = [v for v in result.get('xbar_lcl', []) if v is not None]
    x_ucls = [v for v in result.get('xbar_ucl', []) if v is not None]
    if x_lcls and x_ucls:
        if equal_sizes:
            lines.append(f"  Xbar Lower Control Limit (LCL): {x_lcls[0]:.4f}")
            lines.append(f"  Xbar Upper Control Limit (UCL): {x_ucls[0]:.4f}")
        else:
            lines.append(f"  Xbar Limits: Varying by subgroup size (e.g. LCL ~ {min(x_lcls):.4f}, UCL ~ {max(x_ucls):.4f})")

    disp_name = "R" if chart_type == 'xbar_r' else "S"
    if disp_cl is not None:
        lines.append(f"  {disp_name} Center Line:    {disp_cl:.4f}")
    d_lcls = [v for v in result.get('disp_lcl', []) if v is not None]
    d_ucls = [v for v in result.get('disp_ucl', []) if v is not None]
    if d_lcls and d_ucls:
        if equal_sizes:
            lines.append(f"  {disp_name} Lower Control Limit (LCL): {d_lcls[0]:.4f}")
            lines.append(f"  {disp_name} Upper Control Limit (UCL): {d_ucls[0]:.4f}")
        else:
            lines.append(f"  {disp_name} Limits: Varying by subgroup size")

    # StatCraft.6: Extended limits / Warning limits report
    x_lwls = [v for v in result.get('xbar_lwl', []) if v is not None]
    x_uwls = [v for v in result.get('xbar_uwl', []) if v is not None]
    if x_lwls and x_uwls:
        if equal_sizes:
            lines.append(f"  Xbar Lower Warning Limit (LWL): {x_lwls[0]:.4f}")
            lines.append(f"  Xbar Upper Warning Limit (UWL): {x_uwls[0]:.4f}")
        else:
            lines.append(f"  Xbar Warning Limits: Varying by subgroup size")

    d_lwls = [v for v in result.get('disp_lwl', []) if v is not None]
    d_uwls = [v for v in result.get('disp_uwl', []) if v is not None]
    if d_lwls and d_uwls:
        if equal_sizes:
            lines.append(f"  {disp_name} Lower Warning Limit (LWL): {d_lwls[0]:.4f}")
            lines.append(f"  {disp_name} Upper Warning Limit (UWL): {d_uwls[0]:.4f}")
    lines.append("")

    # Test Results section
    test_fails = result.get('test_failures', {})
    tests_cfg = opts.get('tests', {})

    # Invert mapping to test -> list of points
    failures_by_test: dict[int, list[int]] = {}
    for pt, test_list in sorted(test_fails.items()):
        for t in test_list:
            failures_by_test.setdefault(t, []).append(pt)

    if failures_by_test:
        lines.append(f"Test Results for Xbar Chart of {var_name}")
        for t_num in sorted(failures_by_test):
            pts = failures_by_test[t_num]
            t_cfg = tests_cfg.get(f"test{t_num}", {})
            k_val = t_cfg.get('k', 0)
            desc = TEST_DESCRIPTIONS.get(t_num, f"Test {t_num}").format(
                k=k_val,
                k_plus_1=k_val + 1 if isinstance(k_val, int) else k_val
            )
            lines.append(f"  TEST {t_num}. {desc}")
            pts_str = ", ".join(str(p) for p in pts)
            lines.append(f"    Test Failed at points: {pts_str}")
        lines.append("")
        lines.append("  * WARNING * If graph is updated with new data, the results above may no longer be correct.")
        lines.append("")
    else:
        lines.append(f"Test Results for Xbar Chart of {var_name}")
        lines.append("  No test failures found.")
        lines.append("")

    # Dispersion chart signals
    disp_signals = result.get('disp_signals', [])
    if disp_signals:
        lines.append(f"Test Results for {disp_name} Chart of {var_name}")
        lines.append("  TEST 1. One point beyond control limits.")
        pts_str = ", ".join(str(p) for p in disp_signals)
        lines.append(f"    Test Failed at points: {pts_str}")
        lines.append("")
        lines.append("  * WARNING * If graph is updated with new data, the results above may no longer be correct.")
        lines.append("")

    # Warnings
    warnings = result.get('warnings', [])
    if warnings:
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"  * {w}")
        lines.append("")

    # Stored columns
    stored = result.get('stored_columns', [])
    if stored:
        lines.append(f"Storage: Results stored in columns: {', '.join(stored)}")
        lines.append("")

    return "\n".join(lines)
