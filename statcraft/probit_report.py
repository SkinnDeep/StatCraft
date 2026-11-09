"""Session window report generator for Probit Analysis (Bioassay & LD50/EC50).

Formats output matching Minitab session window styling:
- Regression Equation
- Coefficients Table (Parameter, Coef, SE Coef, Z, P-Value)
- Goodness-of-Fit Tests (Pearson and Deviance Chi-Square)
- Table of Percentiles (Percent, Estimate, SE, 95% Fiducial CI)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_probit_report(result: Dict[str, Any]) -> str:
    """Format Probit Analysis results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Probit Analysis")
    lines.append(title)
    lines.append("")

    dist = result.get("distribution", "Probit")
    transform = result.get("dose_transform", "none")
    lines.append(f"Assumed distribution: {dist}")
    if transform != "none":
        lines.append(f"Dose transformation: {transform}")
    lines.append("")

    # Regression Equation
    eq = result.get("equation")
    if eq:
        lines.append("Regression Equation")
        lines.append(eq)
        lines.append("")

    # Coefficients Table
    lines.append("Coefficients")
    hdr_coef = f"{'Parameter':<16}  {'Coef':>10}  {'SE Coef':>10}  {'Z':>8}  {'P-Value':>8}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))

    for c in result.get("coefficients", []):
        term = c.get("term", "")
        b = c.get("coef", 0.0)
        se = c.get("se_coef", 0.0)
        z_val = c.get("z_value", 0.0)
        p_val = c.get("p_value", 0.0)
        lines.append(f"{term:<16}  {b:>10.4f}  {se:>10.4f}  {z_val:>8.2f}  {p_val:>8.3f}")
    lines.append("")

    # Goodness-of-Fit Tests
    gof = result.get("goodness_of_fit", {})
    lines.append("Goodness-of-Fit Tests")
    hdr_gof = f"{'Test':<16}  {'Chi-Square':>12}  {'DF':>6}  {'P-Value':>8}"
    lines.append(hdr_gof)
    lines.append("-" * len(hdr_gof))
    lines.append(f"{'Pearson':<16}  {gof.get('pearson_chi2', 0.0):>12.4f}  {gof.get('df', 1):>6}  {gof.get('pearson_p', 0.0):>8.3f}")
    lines.append(f"{'Deviance':<16}  {gof.get('deviance_chi2', 0.0):>12.4f}  {gof.get('df', 1):>6}  {gof.get('deviance_p', 0.0):>8.3f}")
    lines.append("")

    # Table of Percentiles
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    lines.append("Table of Percentiles")
    hdr_pct = f"{'Percent':>8}  {'Estimate':>12}  {'SE':>10}  {f'{conf_pct}% Fiducial CI':^24}"
    lines.append(hdr_pct)
    lines.append("-" * len(hdr_pct))

    for p in result.get("percentiles", []):
        pct = p.get("percent", 0.0)
        est = p.get("estimate", 0.0)
        se = p.get("se", 0.0)
        ci_l = p.get("ci_lower", 0.0)
        ci_u = p.get("ci_upper", 0.0)
        ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
        lines.append(f"{pct:>7.1f}%  {est:>12.4f}  {se:>10.4f}  {ci_str:^24}")
    lines.append("")

    return "\n".join(lines)
