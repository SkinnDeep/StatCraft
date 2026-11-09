"""Session window report generator for Poisson Regression.

Formats output matching Minitab session window styling:
- Regression Equation
- Method (Link function = Log)
- Analysis of Variance (Deviance table)
- Model Summary (Deviance R-sq, Adj Deviance R-sq, AIC, BIC)
- Coefficients (Term, Coef, SE Coef, 95% CI, Z-Value, P-Value)
- Relative Risk / Rate Ratios (Term, Relative Risk, 95% CI)
- Goodness-of-Fit Tests (Deviance, Pearson)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_poisson_regression_report(result: Dict[str, Any]) -> str:
    """Format Poisson regression results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Poisson Regression")
    lines.append(title)
    lines.append("")

    lines.append("Method")
    lines.append(f"{'Link function':<20} Log")
    if result.get("offset_name"):
        lines.append(f"{'Offset':<20} {result['offset_name']}")
    lines.append("")

    # Regression Equation
    eq = result.get("equation")
    if eq:
        lines.append("Regression Equation")
        lines.append(eq)
        lines.append("")

    # Coefficients
    lines.append("Coefficients")
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    hdr_coef = f"{'Term':<16}  {'Coef':>10}  {'SE Coef':>10}  {f'{conf_pct}% CI':^22}  {'Z-Value':>8}  {'P-Value':>8}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))

    coef_list = result.get("coefficients", [])
    for c in coef_list:
        term = c.get("term", "")
        b = c.get("coef", 0.0)
        se = c.get("se_coef", 0.0)
        ci_low = c.get("ci_lower", 0.0)
        ci_high = c.get("ci_upper", 0.0)
        z = c.get("z_value", 0.0)
        p = c.get("p_value", 0.0)
        ci_str = f"({ci_low:>.4f}, {ci_high:>.4f})"
        lines.append(f"{term:<16}  {b:>10.4f}  {se:>10.4f}  {ci_str:^22}  {z:>8.2f}  {p:>8.3f}")
    lines.append("")

    # Relative Risk
    lines.append("Relative Risk")
    hdr_rr = f"{'Term':<16}  {'Relative Risk':>14}  {f'{conf_pct}% CI':^22}"
    lines.append(hdr_rr)
    lines.append("-" * len(hdr_rr))
    for c in coef_list:
        if c.get("term") == "Constant":
            continue
        term = c.get("term", "")
        rr = c.get("relative_risk", 1.0)
        rr_low = c.get("rr_lower", 1.0)
        rr_high = c.get("rr_upper", 1.0)
        rr_ci = f"({rr_low:>.4f}, {rr_high:>.4f})"
        lines.append(f"{term:<16}  {rr:>14.4f}  {rr_ci:^22}")
    lines.append("")

    # Model Summary
    lines.append("Model Summary")
    hdr_mod = f"{'Deviance R-sq':>14}  {'Deviance R-sq(adj)':>19}  {'AIC':>10}  {'BIC':>10}"
    lines.append(hdr_mod)
    lines.append(
        f"{result.get('deviance_r_sq', 0.0):>13.2f}%  {result.get('deviance_r_sq_adj', 0.0):>18.2f}%  {result.get('aic', 0.0):>10.2f}  {result.get('bic', 0.0):>10.2f}"
    )
    lines.append("")

    # Goodness-of-Fit Tests
    lines.append("Goodness-of-Fit Tests")
    hdr_gof = f"{'Test':<14}  {'DF':>6}  {'Chi-Square':>12}  {'P-Value':>8}"
    lines.append(hdr_gof)
    lines.append("-" * len(hdr_gof))
    for g in result.get("goodness_of_fit", []):
        tname = g.get("test", "")
        df = g.get("df", 0)
        chi = g.get("chi_square", 0.0)
        pv = g.get("p_value", 0.0)
        lines.append(f"{tname:<14}  {df:>6}  {chi:>12.2f}  {pv:>8.3f}")
    lines.append("")

    # Analysis of Variance
    lines.append("Analysis of Variance")
    hdr_aov = f"{'Source':<14}  {'DF':>6}  {'Adj Dev':>12}  {'Adj MS':>12}  {'Chi-Square':>12}  {'P-Value':>8}"
    lines.append(hdr_aov)
    lines.append("-" * len(hdr_aov))
    for row in result.get("anova", []):
        src = row.get("source", "")
        df = row.get("df", 0)
        dev_val = row.get("adj_dev", 0.0)
        ms_val = row.get("adj_ms")
        chi_val = row.get("chi_square")
        p_val = row.get("p_value")
        ms_str = f"{ms_val:>12.2f}" if ms_val is not None else "".rjust(12)
        chi_str = f"{chi_val:>12.2f}" if chi_val is not None else "".rjust(12)
        p_str = f"{p_val:>8.3f}" if p_val is not None else "".rjust(8)
        lines.append(f"{src:<14}  {df:>6}  {dev_val:>12.2f}  {ms_str}  {chi_str}  {p_str}")

    return "\n".join(lines)
