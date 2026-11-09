"""Session window report generator for Nonlinear Regression.

Formats output matching Minitab session window styling:
- Regression Equation and Model type
- Parameter Estimates Table (Parameter, Estimate, SE, T-Value, P-Value, 95% CI)
- Model Summary (S, R-sq, R-sq(adj))
- Analysis of Variance Table (Regression, Residual Error, Corrected Total)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_nonlinear_regression_report(result: Dict[str, Any]) -> str:
    """Format Nonlinear Regression results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Nonlinear Regression")
    lines.append(title)
    lines.append("")

    lines.append("Method")
    lines.append(f"{'Model':<20} {result.get('model_name', 'Nonlinear')}")
    lines.append(f"{'Algorithm':<20} Levenberg-Marquardt")
    lines.append(f"{'Iterations':<20} {result.get('iterations', 0)}")
    lines.append("")

    # Parameter Estimates
    lines.append("Parameter Estimates")
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    hdr_param = f"{'Parameter':<14}  {'Estimate':>12}  {'SE Coef':>12}  {'T-Value':>8}  {'P-Value':>8}  {f'{conf_pct}% CI':^22}"
    lines.append(hdr_param)
    lines.append("-" * len(hdr_param))

    for p in result.get("parameters", []):
        pname = p.get("parameter", "")
        est = p.get("estimate", 0.0)
        se = p.get("se", 0.0)
        t_val = p.get("t_value", 0.0)
        p_val = p.get("p_value", 0.0)
        ci_l = p.get("ci_lower", 0.0)
        ci_u = p.get("ci_upper", 0.0)
        ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
        lines.append(f"{pname:<14}  {est:>12.4f}  {se:>12.4f}  {t_val:>8.2f}  {p_val:>8.3f}  {ci_str:^22}")
    lines.append("")

    # Model Summary
    lines.append("Model Summary")
    lines.append(f"{'S':>10}  {'R-sq':>8}  {'R-sq(adj)':>10}")
    lines.append(
        f"{result.get('s', 0.0):>10.4f}  {result.get('r_sq', 0.0):>7.2f}%  {result.get('r_sq_adj', 0.0):>9.2f}%"
    )
    lines.append("")

    # Analysis of Variance
    lines.append("Analysis of Variance")
    hdr_aov = f"{'Source':<18}  {'DF':>6}  {'SS':>12}  {'MS':>12}  {'F-Value':>8}  {'P-Value':>8}"
    lines.append(hdr_aov)
    lines.append("-" * len(hdr_aov))

    for row in result.get("anova", []):
        src = row.get("source", "")
        df = row.get("df", 0)
        ss = row.get("ss", 0.0)
        ms = row.get("ms")
        f_val = row.get("f")
        p_val = row.get("p_value")

        ms_str = f"{ms:>12.4f}" if ms is not None else "".rjust(12)
        f_str = f"{f_val:>8.2f}" if f_val is not None and not (isinstance(f_val, float) and math.isnan(f_val)) else "".rjust(8)
        p_str = f"{p_val:>8.3f}" if p_val is not None else "".rjust(8)
        lines.append(f"{src:<18}  {df:>6}  {ss:>12.4f}  {ms_str}  {f_str}  {p_str}")

    return "\n".join(lines)


import math
