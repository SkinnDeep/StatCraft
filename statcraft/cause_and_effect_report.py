"""Minitab 22 standard session report formatter for Cause-and-Effect (%Fishbone) diagrams."""
from __future__ import annotations

from typing import Any, Dict


def format_cause_and_effect_report(result: Dict[str, Any]) -> str:
    """Format Cause-and-Effect session report matching Minitab 22 text output."""
    lines = []
    title = result.get("title", "Cause-and-Effect Diagram")
    effect = result.get("effect", "Effect")
    branches = result.get("branches", [])
    tot_causes = result.get("total_causes", 0)

    lines.append("=" * 76)
    lines.append(f"  {title.upper()}")
    lines.append("=" * 76)
    lines.append("")
    lines.append(f"Effect:                 {effect}")
    lines.append(f"Active Branches:        {len(branches)}")
    lines.append(f"Total Causes Specified: {tot_causes}")
    lines.append("")
    lines.append("-" * 76)
    lines.append(f"{'Branch #':<10} {'Category Label':<24} {'Causes Count':>12}")
    lines.append("-" * 76)

    for b in branches:
        idx_str = f"Branch {b.get('branch_index', '')}"
        lbl_str = b.get("label", "") or "(No Label)"
        cnt = b.get("count", 0)
        lines.append(f"{idx_str:<10} {lbl_str:<24} {cnt:>12}")

    lines.append("-" * 76)
    lines.append("")
    lines.append("--- Detailed Cause Breakdown by Branch ---")
    lines.append("")

    for b in branches:
        lbl_str = b.get("label", "") or f"Branch {b.get('branch_index', '')}"
        causes = b.get("causes", [])
        lines.append(f"• {lbl_str} ({len(causes)} causes):")
        if causes:
            for c in causes:
                lines.append(f"    - {c}")
        else:
            lines.append("    (No causes assigned to this branch)")
        lines.append("")

    return "\n".join(lines)
