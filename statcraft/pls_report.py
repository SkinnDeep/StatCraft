"""Session window report generator for Partial Least Squares Regression.

Formats output matching Minitab session window styling:
- Method and optimal components
- Model Selection and Validation table (Components, X-Variance, R-sq, PRESS, R-sq(pred))
- Model Summary (Components, S, R-sq, R-sq(pred))
- Regression Equation
- Coefficients table (Standardized Coef, Unstandardized Coef, VIP)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_pls_report(result: Dict[str, Any]) -> str:
    """Format Partial Least Squares results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Partial Least Squares Regression")
    lines.append(title)
    lines.append("")

    lines.append("Method")
    lines.append(f"{'Cross-validation':<30} Leave-one-out")
    lines.append(f"{'Selected number of components':<30} {result.get('optimal_components', 1)}")
    lines.append("")

    # Model Selection and Validation Table
    lines.append("Model Selection and Validation")
    hdr_sel = f"{'Components':<10}  {'X-Variance (%)':>14}  {'Cum X-Var (%)':>14}  {'R-sq (%)':>10}  {'PRESS':>10}  {'R-sq (pred) (%)':>16}"
    lines.append(hdr_sel)
    lines.append("-" * len(hdr_sel))

    opt_c = result.get("optimal_components", 1)
    for rec in result.get("model_selection", []):
        c_num = rec.get("component", 1)
        x_var = rec.get("x_variance", 0.0)
        cum_x = rec.get("cum_x_variance", 0.0)
        rsq = rec.get("r_sq", 0.0)
        press = rec.get("press", 0.0)
        rsq_p = rec.get("r_sq_pred", 0.0)
        mark = " *" if c_num == opt_c else ""
        lines.append(
            f"{c_num:<10}  {x_var:>14.2f}  {cum_x:>14.2f}  {rsq:>10.2f}  {press:>10.2f}  {rsq_p:>15.2f}%{mark}"
        )
    lines.append("")

    # Model Summary
    lines.append("Model Summary")
    lines.append(
        f"Selected Components = {opt_c}, "
        f"S = {result.get('s', 0.0):.4f}, "
        f"R-sq = {result.get('r_sq', 0.0):.2f}%, "
        f"R-sq (pred) = {result.get('r_sq_pred', 0.0):.2f}%, "
        f"Cum X-Variance = {result.get('cum_x_var', 0.0):.2f}%"
    )
    lines.append("")

    # Regression Equation
    resp_name = result.get("response_name", "Y")
    intercept = result.get("intercept", 0.0)
    coef_list = result.get("coefficients", [])
    eq_parts = [f"{intercept:.4f}"]
    for c in coef_list:
        pname = c.get("predictor", "")
        b = c.get("unstd_coef", 0.0)
        sign = "+ " if b >= 0 else "- "
        eq_parts.append(f"{sign}{abs(b):.4f} {pname}")
    lines.append("Regression Equation")
    lines.append(f"{resp_name} = {' '.join(eq_parts)}")
    lines.append("")

    # Coefficients Table
    lines.append("Coefficients")
    hdr_coef = f"{'Predictor':<16}  {'Std Coef':>12}  {'Unstd Coef':>12}  {'VIP':>8}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))
    lines.append(f"{'Constant':<16}  {'':>12}  {intercept:>12.4f}  {'':>8}")

    for c in coef_list:
        pname = c.get("predictor", "")
        std_b = c.get("std_coef", 0.0)
        unstd_b = c.get("unstd_coef", 0.0)
        vip_val = c.get("vip", 1.0)
        lines.append(f"{pname:<16}  {std_b:>12.4f}  {unstd_b:>12.4f}  {vip_val:>8.2f}")

    return "\n".join(lines)
