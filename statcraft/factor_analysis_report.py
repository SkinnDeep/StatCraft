"""Session window report generator for Factor Analysis.

Formats output matching Minitab session window styling:
- Principal Component Factor Analysis header
- Eigenvalues of the Correlation Matrix
- Unrotated Factor Loadings and Communalities
- Rotated Factor Loadings and Communalities
- Variance Explained and % of Total Variance
- Factor Score Coefficients
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_factor_analysis_report(result: Dict[str, Any]) -> str:
    """Format Factor Analysis results into a Minitab session text report."""
    lines: List[str] = []
    lines.append(result.get("title", "Factor Analysis"))
    lines.append("")

    rot = result.get("rotation", "Varimax")
    lines.append(f"Extraction Method: Principal Components")
    lines.append(f"Rotation:          {rot}")
    lines.append(f"Number of Variables: {result.get('n_vars', 0)}")
    lines.append(f"Number of Factors:   {result.get('n_factors', 0)}")
    lines.append(f"Number of Observations: {result.get('n_obs', 0)}")
    lines.append("")

    # Eigenvalues of the correlation matrix
    lines.append("Eigenvalues of the Correlation Matrix")
    hdr_eig = f"{'Component':<12}  {'Eigenvalue':>12}  {'Proportion':>12}  {'Cumulative':>12}"
    lines.append(hdr_eig)
    lines.append("-" * len(hdr_eig))

    for ev in result.get("eigenvalues", []):
        comp = f"Comp {ev.get('component', 1)}"
        val = ev.get("eigenvalue", 0.0)
        prop = ev.get("proportion", 0.0)
        cum = ev.get("cumulative", 0.0)
        lines.append(f"{comp:<12}  {val:>12.4f}  {prop:>12.3f}  {cum:>12.3f}")
    lines.append("")

    fac_labels = result.get("factor_labels", [])
    num_fac = len(fac_labels)

    # Unrotated Loadings Table
    lines.append("Unrotated Factor Loadings and Communalities")
    hdr_fac = f"{'Variable':<14}  " + "  ".join(f"{fl:>10}" for fl in fac_labels) + f"  {'Communality':>12}"
    lines.append(hdr_fac)
    lines.append("-" * len(hdr_fac))

    for row in result.get("unrotated_loadings", []):
        v = row.get("variable", "")
        fac_vals = "  ".join(f"{row.get(fl, 0.0):>10.3f}" for fl in fac_labels)
        comm = row.get("communality", 0.0)
        lines.append(f"{v:<14}  {fac_vals}  {comm:>12.3f}")

    lines.append("-" * len(hdr_fac))
    unrot_vars = result.get("unrotated_variance", [])
    unrot_props = result.get("unrotated_prop_var", [])
    var_str = "  ".join(f"{v:>10.3f}" for v in unrot_vars)
    prop_str = "  ".join(f"{p:>10.3f}" for p in unrot_props)
    lines.append(f"{'Variance':<14}  {var_str}")
    lines.append(f"{'% Var':<14}  {prop_str}")
    lines.append("")

    # Rotated Loadings Table (if rotation applied)
    if rot != "None":
        lines.append(f"Rotated Factor Loadings and Communalities ({rot} Rotation)")
        lines.append(hdr_fac)
        lines.append("-" * len(hdr_fac))

        for row in result.get("rotated_loadings", []):
            v = row.get("variable", "")
            fac_vals = "  ".join(f"{row.get(fl, 0.0):>10.3f}" for fl in fac_labels)
            comm = row.get("communality", 0.0)
            lines.append(f"{v:<14}  {fac_vals}  {comm:>12.3f}")

        lines.append("-" * len(hdr_fac))
        rot_vars = result.get("rotated_variance", [])
        rot_props = result.get("rotated_prop_var", [])
        var_r_str = "  ".join(f"{v:>10.3f}" for v in rot_vars)
        prop_r_str = "  ".join(f"{p:>10.3f}" for p in rot_props)
        lines.append(f"{'Variance':<14}  {var_r_str}")
        lines.append(f"{'% Var':<14}  {prop_r_str}")
        lines.append("")

    # Factor Score Coefficients Table
    lines.append("Factor Score Coefficients")
    hdr_score = f"{'Variable':<14}  " + "  ".join(f"{fl:>10}" for fl in fac_labels)
    lines.append(hdr_score)
    lines.append("-" * len(hdr_score))

    for row in result.get("score_coefficients", []):
        v = row.get("variable", "")
        fac_vals = "  ".join(f"{row.get(fl, 0.0):>10.3f}" for fl in fac_labels)
        lines.append(f"{v:<14}  {fac_vals}")
    lines.append("")

    return "\n".join(lines)
