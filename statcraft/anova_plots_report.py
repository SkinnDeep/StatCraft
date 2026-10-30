"""Session report formatters for Main Effects and Interactions plots."""
from __future__ import annotations

from typing import Any


def format_main_effects_report(result: dict[str, Any]) -> str:
    """Format Minitab 22 session report for Main Effects Plot."""
    resp = result.get("response_name", "Response")
    count = result.get("count", 0)
    grand_mean = result.get("grand_mean", 0.0)

    lines = [
        f"Main Effects Plot for {resp}",
        "",
        f"Data Means (Grand Mean = {grand_mean:.4f}, N = {count})",
        ""
    ]

    for summ in result.get("factor_summaries", []):
        f_name = summ.get("factor_name", "Factor")
        lines.append(f"Factor: {f_name}")
        lines.append(f"  {'Level':<14} {'N':>8} {'Mean':>12} {'StDev':>12}")
        lines.append("  " + "-" * 48)
        for s in summ.get("level_stats", []):
            lvl = str(s.get("level"))
            n_val = s.get("count", 0)
            m_val = s.get("mean", 0.0)
            sd_val = s.get("stdev", 0.0)
            lines.append(f"  {lvl:<14} {n_val:>8} {m_val:>12.4f} {sd_val:>12.4f}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_interactions_report(result: dict[str, Any]) -> str:
    """Format Minitab 22 session report for Interactions Plot."""
    resp = result.get("response_name", "Response")
    fa_name = result.get("factor_a_name", "Factor A")
    fb_name = result.get("factor_b_name", "Factor B")
    count = result.get("count", 0)
    grand_mean = result.get("grand_mean", 0.0)

    lines = [
        f"Interaction Plot for {resp}",
        f"Data Means: {fa_name} by {fb_name} (Grand Mean = {grand_mean:.4f}, N = {count})",
        ""
    ]

    levels_a = result.get("levels_a", [])
    levels_b = result.get("levels_b", [])
    cell_stats = result.get("cell_stats", {})

    # Header row
    header = f"  {fa_name:<14}"
    for b in levels_b:
        header += f" {str(b):>12}"
    header += f" {'Mean':>12}"
    lines.append(header)
    lines.append("  " + "-" * (14 + 13 * (len(levels_b) + 1)))

    # Rows for each level of Factor A
    for a in levels_a:
        row = f"  {str(a):<14}"
        row_vals = []
        for b in levels_b:
            st = cell_stats.get(a, {}).get(b, {})
            m = st.get("mean")
            if m is not None:
                row += f" {m:>12.4f}"
                row_vals.append(m)
            else:
                row += f" {'*':>12}"
        if row_vals:
            row_mean = sum(row_vals) / len(row_vals)
            row += f" {row_mean:>12.4f}"
        else:
            row += f" {'*':>12}"
        lines.append(row)

    # Column marginal means (Factor B)
    lines.append("  " + "-" * (14 + 13 * (len(levels_b) + 1)))
    col_row = f"  {'Mean':<14}"
    for b in levels_b:
        mb = next((s["mean"] for s in result.get("marginal_b", []) if s["level"] == b), None)
        if mb is not None:
            col_row += f" {mb:>12.4f}"
        else:
            col_row += f" {'*':>12}"
    col_row += f" {grand_mean:>12.4f}"
    lines.append(col_row)

    return "\n".join(lines).rstrip()
