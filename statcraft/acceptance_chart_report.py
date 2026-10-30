"""Session text report generator for Acceptance Control Charts."""

from typing import Any, Dict


def format_acceptance_chart_report(res: Dict[str, Any]) -> str:
    """Format structured text report for Acceptance Control Chart."""
    lines = []
    var_name = res.get("variable_name", "Data")
    title = f"Acceptance Control Chart for {var_name}"
    lines.append(title)
    lines.append("")

    lines.append("Process Parameters")
    lines.append(f"{'Sample N':28} {res.get('sample_n', 0)}")
    lines.append(f"{'Subgroups':28} {res.get('subgroup_count', 0)}")
    lines.append(f"{'Subgroup Size':28} {res.get('avg_subgroup_size', 0):.4g}")
    lines.append(f"{'Process Mean':28} {res.get('grand_mean', 0.0):.5g}")
    lines.append(f"{'Standard Deviation':28} {res.get('stdev', 0.0):.5g} ({res.get('sigma_source', '')})")
    lines.append(f"{'Acceptable Defective Rate (δ)':28} {res.get('delta', 0.001):.4g}")
    lines.append(f"{'Producer Risk (α)':28} {res.get('alpha', 0.05):.4g}")
    if res.get("lsl") is not None:
        lines.append(f"{'Lower Spec Limit (LSL)':28} {res.get('lsl'):g}")
    if res.get("target") is not None:
        lines.append(f"{'Target':28} {res.get('target'):g}")
    if res.get("usl") is not None:
        lines.append(f"{'Upper Spec Limit (USL)':28} {res.get('usl'):g}")
    lines.append("")

    lines.append("Acceptance Control Limits")
    if res.get("uacl") is not None:
        lines.append(f"{'UACL (Upper Acceptance Limit)':32} {res.get('uacl', 0.0):.5g}")
    if res.get("apl_upper") is not None:
        lines.append(f"{'APL (Upper Acceptable Process Level)':32} {res.get('apl_upper', 0.0):.5g}")
    lines.append(f"{'Center Line':32} {res.get('center_line', 0.0):.5g}")
    if res.get("apl_lower") is not None:
        lines.append(f"{'APL (Lower Acceptable Process Level)':32} {res.get('apl_lower', 0.0):.5g}")
    if res.get("lacl") is not None:
        lines.append(f"{'LACL (Lower Acceptance Limit)':32} {res.get('lacl', 0.0):.5g}")
    lines.append("")

    if res.get("cp") is not None or res.get("cpk") is not None:
        lines.append("Process Capability Indices")
        if res.get("cp") is not None:
            lines.append(f"{'Cp':12} {res.get('cp', 0.0):.2f}")
        if res.get("cpk") is not None:
            lines.append(f"{'Cpk':12} {res.get('cpk', 0.0):.2f}")
        lines.append("")

    lines.append("Test Results for Acceptance Control Chart")
    signals = res.get("test1_signals", [])
    if signals:
        lines.append("TEST 1. One point beyond acceptance control limits.")
        lines.append(f"Test Failed at Subgroups: {', '.join(str(s) for s in signals)}")
    else:
        lines.append("No points failed the acceptance limits test.")

    return "\n".join(lines)
