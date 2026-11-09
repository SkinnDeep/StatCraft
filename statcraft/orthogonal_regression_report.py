"""Session window report generator for Orthogonal Regression (Deming Regression).

Formats output matching Minitab session window styling:
- Title and Error Variance Ratio
- Regression Equation
- Coefficients Table (Predictor, Coef, SE Coef, 95% CI, T-Value, P-Value)
- Test of Slope = 1 (Hypothesis, T-Value, P-Value)
- Error Variances Table (Predictor, Response)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_orthogonal_regression_report(result: Dict[str, Any]) -> str:
    """Format Orthogonal Regression results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Orthogonal Regression")
    lines.append(title)
    lines.append("")

    resp_name = result.get("response_name", "Y")
    pred_name = result.get("predictor_name", "X")
    ratio = result.get("error_variance_ratio", 1.0)
    lines.append(f"Error Variance Ratio ({resp_name} / {pred_name}): {ratio:.4g}")
    lines.append("")

    # Regression Equation
    eq = result.get("equation")
    if eq:
        lines.append("Regression Equation")
        lines.append(eq)
        lines.append("")

    # Coefficients Table
    lines.append("Coefficients")
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    hdr_coef = f"{'Predictor':<16}  {'Coef':>10}  {'SE Coef':>10}  {f'{conf_pct}% CI':^22}  {'T-Value':>8}  {'P-Value':>8}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))

    for c in result.get("coefficients", []):
        term = c.get("term", "")
        b = c.get("coef", 0.0)
        se = c.get("se_coef", 0.0)
        t_val = c.get("t_value", 0.0)
        p_val = c.get("p_value", 0.0)
        ci_l = c.get("ci_lower", 0.0)
        ci_u = c.get("ci_upper", 0.0)
        ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
        lines.append(f"{term:<16}  {b:>10.4f}  {se:>10.4f}  {ci_str:^22}  {t_val:>8.2f}  {p_val:>8.3f}")
    lines.append("")

    # Test of Slope = 1
    t_test = result.get("test_slope_1", {})
    t_stat = t_test.get("t_value", 0.0)
    p_stat = t_test.get("p_value", 0.0)
    lines.append("Test of Slope = 1")
    lines.append("Hypothesis: H0: Slope = 1 versus H1: Slope != 1")
    lines.append(f"T-Value = {t_stat:.2f}, P-Value = {p_stat:.3f}")
    lines.append("")

    # Error Variances
    lines.append("Error Variances")
    hdr_ev = f"{'Variable':<16}  {'Error Variance':>14}"
    lines.append(hdr_ev)
    lines.append("-" * len(hdr_ev))
    ev_x = result.get("error_variance_x", 0.0)
    ev_y = result.get("error_variance_y", 0.0)
    lines.append(f"{pred_name:<16}  {ev_x:>14.4f}")
    lines.append(f"{resp_name:<16}  {ev_y:>14.4f}")

    return "\n".join(lines)
