"""Session output report generation for Process Screening."""
from __future__ import annotations

from typing import Any, Dict, List


def format_process_screening_report(result: Dict[str, Any]) -> str:
    """Format text report for Session Output."""
    lines: List[str] = []
    lines.append("Process Screening Dashboard")
    lines.append(f"Variables Screened: {result['total_screened']}")
    lines.append(
        f"Summary Health: {result['stable_count']}/{result['total_screened']} ({result['stable_percent']}%) Stable, "
        f"{result['capable_count']}/{result['total_screened']} ({result['capable_percent']}%) Capable (Ppk >= 1.33)"
    )
    lines.append(f"Processes with Special-Cause Alarms: {result['alarms_processes_count']}")
    lines.append(f"Worst Stability: {result['worst_stability_process']} (SI = {result['worst_stability_index']:.3f})")
    lines.append(f"Lowest Capability: {result['lowest_ppk_process']} (Ppk = {result['lowest_ppk']:.3f})")
    lines.append("")

    lines.append("Process Screening Details Table:")
    hdr = f"{'Process':<18} {'N':<6} {'Mean':<10} {'s(Overall)':<11} {'s(Within)':<10} {'Stability':<10} {'Alarms':<7} {'Ppk':<8} {'PPM':<8} {'Status'}"
    lines.append(hdr)
    lines.append("-" * len(hdr) + "----------------")
    for p in result["processes"]:
        ppk_str = f"{p['ppk']:.2f}" if p["ppk"] is not None else "N/A"
        lines.append(
            f"{p['process']:<18} {p['n']:<6} {p['mean']:<10.3f} {p['stdev_overall']:<11.3f} "
            f"{p['stdev_within']:<10.3f} {p['stability_index']:<10.3f} {p['alarms_count']:<7} "
            f"{ppk_str:<8} {p['ppm_defect']:<8.0f} {p['status_label']}"
        )

    return "\n".join(lines)


def get_process_screening_tables(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured tables for GUI rendering."""
    headers_scorecard = ["Metric", "Value"]
    rows_scorecard = [
        ["Total Processes Screened", result["total_screened"]],
        ["Processes in Control / Stable (SI < 1.25)", f"{result['stable_count']} ({result['stable_percent']}%)"],
        ["Capable Processes (Ppk >= 1.33)", f"{result['capable_count']} ({result['capable_percent']}%)"],
        ["Processes with Special-Cause Alarms", result["alarms_processes_count"]],
        ["Highest Stability Index (Most Drift)", f"{result['worst_stability_process']} ({result['worst_stability_index']:.3f})"],
        ["Lowest Ppk (Lowest Capability)", f"{result['lowest_ppk_process']} ({result['lowest_ppk']:.3f})"],
    ]

    headers_details = [
        "Status", "Process", "N", "Mean", "Overall SD", "Within SD",
        "Stability Index", "Alarms", "Cp", "Cpk", "Pp", "Ppk", "Defect PPM"
    ]
    rows_details = []
    for p in result["processes"]:
        rows_details.append([
            p["status_label"],
            p["process"],
            p["n"],
            round(p["mean"], 4),
            round(p["stdev_overall"], 4),
            round(p["stdev_within"], 4),
            round(p["stability_index"], 3),
            p["alarms_count"],
            p["cp"] if p["cp"] is not None else "—",
            p["cpk"] if p["cpk"] is not None else "—",
            p["pp"] if p["pp"] is not None else "—",
            p["ppk"] if p["ppk"] is not None else "—",
            round(p["ppm_defect"], 1),
        ])

    return [
        {"title": "Process Screening Summary Scorecard", "headers": headers_scorecard, "rows": rows_scorecard},
        {"title": "Process Screening Metrics Table", "headers": headers_details, "rows": rows_details},
    ]
