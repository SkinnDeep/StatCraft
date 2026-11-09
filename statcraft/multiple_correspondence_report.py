"""Session window report generator for Multiple Correspondence Analysis (MCA).

Formats output matching Minitab session window styling:
- Multiple Correspondence Analysis Header
- Principal Inertias (Eigenvalues, Proportion, Cumulative)
- Column (Category) Coordinates Table
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_multiple_correspondence_report(result: Dict[str, Any]) -> str:
    """Format Multiple Correspondence Analysis results into a Minitab session text report."""
    lines: List[str] = []
    lines.append(result.get("title", "Multiple Correspondence Analysis"))
    lines.append("")

    lines.append(f"Number of Observations: {result.get('n_obs', 0)}")
    lines.append(f"Number of Variables:    {result.get('n_vars', 0)}")
    lines.append(f"Number of Categories:   {result.get('n_categories', 0)}")
    lines.append(f"Total Inertia:          {result.get('total_inertia', 0.0):.4f}")
    lines.append("")

    # Principal Inertias Table
    lines.append("Principal Inertias")
    hdr_in = f"{'Axis':<8}  {'Inertia':>12}  {'Proportion':>12}  {'Cumulative':>12}"
    lines.append(hdr_in)
    lines.append("-" * len(hdr_in))

    for row in result.get("inertia_table", []):
        ax = f"Axis {row.get('axis', 1)}"
        ine = row.get("inertia", 0.0)
        prop = row.get("proportion", 0.0)
        cum = row.get("cumulative", 0.0)
        lines.append(f"{ax:<8}  {ine:>12.4f}  {prop:>12.4f}  {cum:>12.4f}")
    lines.append("")

    # Category Coordinates Table
    n_comp = result.get("n_components", 2)
    coord_hdrs = "  ".join(f"{f'Coord {a+1}':>10}" for a in range(n_comp))

    lines.append("Category Coordinates")
    hdr_cat = f"{'Variable':<14}  {'Category':<12}  {'Mass':>8}  {'Quality':>8}  {'Rel Inertia':>12}  {coord_hdrs}"
    lines.append(hdr_cat)
    lines.append("-" * len(hdr_cat))

    for c in result.get("category_table", []):
        v = c.get("variable", "")
        cat = c.get("category", "")
        mass = c.get("mass", 0.0)
        qual = c.get("quality", 0.0)
        rel_in = c.get("relative_inertia", 0.0)
        coords = "  ".join(f"{c.get(f'coord_{a+1}', 0.0):>10.3f}" for a in range(n_comp))
        lines.append(f"{v:<14}  {cat:<12}  {mass:>8.3f}  {qual:>8.3f}  {rel_in:>12.3f}  {coords}")
    lines.append("")

    return "\n".join(lines)
