"""Session report formatter for Acceptance Sampling by Attributes matching Minitab standard."""
from __future__ import annotations

from typing import Any, Dict


def generate_acceptance_sampling_report(result: Dict[str, Any]) -> str:
    """Format Acceptance Sampling by Attributes results into standard Minitab statistical text report."""
    lines = []
    settings = result.get("settings", {})
    title = settings.get("title") or "Acceptance Sampling by Attributes"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Plan Summary
    meas_type = "Go / no go (defective parts)" if result.get("measurement_type") == "defective" else "Number of defects"
    lines.append(f"Measurement type : {meas_type}")
    lot_size_str = f"{result['lot_size']:,}" if result.get("lot_size") else "Infinite / Unspecified (Binomial)"
    lines.append(f"Lot size         : {lot_size_str}")
    lines.append("")

    # Generated / Compared Plan Table
    lines.append("Sampling Plan")
    lines.append("-" * 45)
    lines.append(f"  {'Sample Size (n)':<24}: {result['sample_size']}")
    lines.append(f"  {'Acceptance Number (c)':<24}: {result['acceptance_number']}")
    lines.append("-" * 45)
    lines.append(f"  Accept lot if defectives <= {result['acceptance_number']}; otherwise reject.")
    lines.append("")

    # Quality Levels and Risks Table
    lines.append("Quality Levels and Risks")
    lines.append("-" * 65)
    lines.append(f"{'Quality Level':<22} {'Defect Rate':>12} {'Prob Accept':>14} {'Prob Reject':>14}")
    lines.append("-" * 65)
    aql_pct = result["aql"] * 100.0
    rql_pct = result["rql"] * 100.0
    p_acc_aql = result["actual_p_accept_aql"]
    p_rej_aql = result["actual_alpha"]
    p_acc_rql = result["actual_p_accept_rql"]
    p_rej_rql = 1.0 - p_acc_rql

    lines.append(f"{'AQL (Acceptable)':<22} {aql_pct:>11.2f}% {p_acc_aql:>14.4f} {p_rej_aql:>14.4f} (Alpha)")
    lines.append(f"{'RQL / LTPD (Reject)':<22} {rql_pct:>11.2f}% {p_acc_rql:>14.4f} (Beta) {p_rej_rql:>14.4f}")
    lines.append("-" * 65)
    lines.append("")

    # Average Outgoing Quality (AOQ) & AOQL
    aoql_pct = result.get("aoql", 0.0) * 100.0
    p_aoql_pct = result.get("p_at_aoql", 0.0) * 100.0
    lines.append("Average Outgoing Quality (AOQ)")
    lines.append("-" * 55)
    lines.append(f"  {'AOQL (Quality Limit)':<26}: {aoql_pct:.3f}%")
    lines.append(f"  {'At Incoming Defect Rate':<26}: {p_aoql_pct:.3f}%")
    lines.append("-" * 55)
    lines.append("")

    return "\n".join(lines)
