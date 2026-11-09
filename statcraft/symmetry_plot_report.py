"""Session report formatter for Symmetry Plot matching Minitab standard."""
from __future__ import annotations

from typing import Any, Dict


def generate_symmetry_plot_report(result: Dict[str, Any], variable_name: str = "C1") -> str:
    """Format Symmetry Plot results into standard Minitab statistical text report."""
    lines = []
    settings = result.get("settings", {})
    title = settings.get("title") or f"Symmetry Plot for {variable_name}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Summary Statistics Table
    lines.append("Summary Statistics")
    lines.append("-" * 55)
    lines.append(f"  {'Sample Size (N)':<28}: {result['n']}")
    if result.get("n_missing", 0) > 0:
        lines.append(f"  {'Missing Observations':<28}: {result['n_missing']}")
    lines.append(f"  {'Mean':<28}: {result['mean']:.4f}")
    lines.append(f"  {'Standard Deviation':<28}: {result['stdev']:.4f}")
    lines.append(f"  {'Median':<28}: {result['median']:.4f}")
    lines.append(f"  {'Skewness':<28}: {result['skewness']:+.4f} ({result.get('skew_label', 'Unknown')})")
    lines.append("-" * 55)
    lines.append(f"  Assessment: {result.get('assessment', '')}")
    lines.append("")

    # Detailed distance pairs table (first 25 rows to avoid overflow)
    points_table = result.get("points_table", [])
    if points_table:
        lines.append("Distance from Median Table")
        lines.append("-" * 72)
        lines.append(f"{'Rank':>6} {'Lower Obs':>14} {'Upper Obs':>14} {'Lower Dist':>12} {'Upper Dist':>12} {'Diff':>10}")
        lines.append("-" * 72)
        for row in points_table[:30]:
            lines.append(
                f"{row['rank']:>6d} "
                f"{row['lower_obs']:>14.4f} "
                f"{row['upper_obs']:>14.4f} "
                f"{row['lower_dist']:>12.4f} "
                f"{row['upper_dist']:>12.4f} "
                f"{row['discrepancy']:>+10.4f}"
            )
        if len(points_table) > 30:
            lines.append(f"  ... [{len(points_table) - 30} additional distance pairs omitted for brevity]")
        lines.append("-" * 72)
        lines.append("  * Lower Dist = Median - Lower Obs; Upper Dist = Upper Obs - Median")
        lines.append("")

    return "\n".join(lines)
