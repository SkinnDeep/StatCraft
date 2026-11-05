"""Session output report generation for Control Chart Builder."""
from __future__ import annotations

from typing import Any, Dict, List


def format_control_chart_builder_report(result: Dict[str, Any]) -> str:
    """Format plain-text summary report for Session Output."""
    lines: List[str] = []
    lines.append("Control Chart Builder")
    lines.append(f"Response: {result['y_name']}")
    if result.get("subgroup_name"):
        lines.append(f"Subgroup: {result['subgroup_name']}")
    if result.get("phase_name"):
        lines.append(f"Phase: {result['phase_name']}")
    lines.append(f"Chart Type: {result['chart_type'].upper()} (Limits at ±{result['k_sigma']:g} Sigma)")
    lines.append("")

    # Phase summary table
    lines.append("Phase Summary & Control Limits:")
    lines.append(f"{'Phase':<16} {'Subgroups':<10} {'Centerline':<12} {'LCL':<10} {'UCL':<10} {'Within Sigma':<12} {'Alarms':<8}")
    lines.append("-" * 80)
    for p in result["phases"]:
        lines.append(
            f"{p['phase']:<16} {p['k_subgroups']:<10} {p['cl_x']:<12.4f} {p['lcl_x']:<10.4f} "
            f"{p['ucl_x']:<10.4f} {p['sigma_within']:<12.4f} {p['alarms_count']:<8}"
        )
    lines.append("")

    lines.append(f"Dispersion Limits ({result['disp_label']}):")
    lines.append(f"{'Phase':<16} {'Centerline':<12} {'LCL':<10} {'UCL':<10}")
    lines.append("-" * 52)
    for p in result["phases"]:
        lines.append(f"{p['phase']:<16} {p['cl_disp']:<12.4f} {p['lcl_disp']:<10.4f} {p['ucl_disp']:<10.4f}")
    lines.append("")

    # Out of control alarm details
    alarm_pts = [pt for pt in result["points"] if pt["alarm"]]
    if alarm_pts:
        lines.append(f"Test Results (Total Alarms: {len(alarm_pts)}):")
        for pt in alarm_pts:
            rules_str = ", ".join(f"Test {v}" for v in pt["violations"])
            lines.append(f"  * Subgroup {pt['label']} (Phase: {pt['phase']}): Value = {pt['value']:.4f} [Failed: {rules_str}]")
    else:
        lines.append("Test Results: Process is in statistical control. No Nelson rule tests failed.")

    return "\n".join(lines)


def get_control_chart_builder_tables(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured tables for GUI rendering."""
    headers_primary = ["Phase", "Subgroups", "Centerline", "LCL", "UCL", "Within Sigma", "Alarms"]
    rows_primary = []
    for p in result["phases"]:
        rows_primary.append([
            p["phase"],
            p["k_subgroups"],
            round(p["cl_x"], 4),
            round(p["lcl_x"], 4),
            round(p["ucl_x"], 4),
            round(p["sigma_within"], 4),
            p["alarms_count"],
        ])

    headers_disp = ["Phase", f"{result['disp_label']} Center", "Disp LCL", "Disp UCL"]
    rows_disp = []
    for p in result["phases"]:
        rows_disp.append([
            p["phase"],
            round(p["cl_disp"], 4),
            round(p["lcl_disp"], 4),
            round(p["ucl_disp"], 4),
        ])

    return [
        {"title": f"Primary Chart Limits ({result['primary_label']})", "headers": headers_primary, "rows": rows_primary},
        {"title": f"Dispersion Chart Limits ({result['disp_label']})", "headers": headers_disp, "rows": rows_disp},
    ]
