"""Text session report formatter for Attribute Gage Study (Analytic Method)."""
from __future__ import annotations

from typing import Any, Dict


def generate_attribute_gage_report(result: Dict[str, Any], reference_col: str = "Reference", accept_col: str = "Acceptances") -> str:
    """Format Attribute Gage Study results into standard Minitab statistical text report."""
    lines = []
    settings = result.get("settings", {})
    gage_info = settings.get("gage_info", {})

    title = settings.get("title") or "Attribute Gage Study (Analytic Method)"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    info_items = [
        ("Gage name", gage_info.get("gage_name")),
        ("Date of study", gage_info.get("date_of_study")),
        ("Reported by", gage_info.get("reported_by")),
        ("Miscellaneous", gage_info.get("misc")),
    ]
    if any(v for _, v in info_items):
        lines.append("Gage Information:")
        for lbl, val in info_items:
            if val:
                lines.append(f"  {lbl:<18}: {val}")
        lines.append("")

    # Part observations table
    parts_table = result.get("parts_table", [])
    if parts_table:
        lines.append("Gage Performance Table")
        lines.append("-" * 75)
        lines.append(f"{'Part':<12} {'Reference':>12} {'Trials':>8} {'Acceptances':>13} {'Adj Prob':>12} {'Z-Score':>12}")
        lines.append("-" * 75)
        for row in parts_table:
            lines.append(
                f"{row['part']:<12} "
                f"{row['reference']:>12.4f} "
                f"{row['trials']:>8d} "
                f"{row['acceptances']:>13d} "
                f"{row['adj_prob']:>12.4f} "
                f"{row['z_score']:>12.4f}"
            )
        lines.append("-" * 75)
        lines.append("  * Extreme probabilities adjusted using AIAG standard (0.5/m or (m-0.5)/m)")
        lines.append("")

    # Regression Equation
    reg = result.get("regression", {})
    intercept = reg.get("intercept", 0.0)
    slope = reg.get("slope", 0.0)
    r2 = reg.get("r_squared", 0.0)
    sign = "+" if slope >= 0 else "-"

    lines.append("Regression Equation")
    lines.append(f"  Z = {intercept:.4f} {sign} {abs(slope):.4f} * {reference_col}")
    lines.append(f"  R-Sq = {r2 * 100.0:.2f}%")
    lines.append("")

    # Gage Bias Evaluation
    bias = result.get("bias_metrics", {})
    lines.append("Gage Bias Evaluation")
    lines.append(f"  {'Target (Standard)':<30}: {bias.get('target', 0.0):.6g}")
    lines.append(f"  {'50% Acceptance Point (X_0.5)':<30}: {bias.get('x_half', 0.0):.6g}")
    lines.append(f"  {'Bias':<30}: {bias.get('bias', 0.0):.6g}")
    lines.append(f"  {'Std Error of Bias':<30}: {bias.get('se_bias', 0.0):.6g}")
    lines.append(f"  {'T-Statistic':<30}: {bias.get('t_statistic', 0.0):.4f}")
    lines.append(f"  {'DF':<30}: {bias.get('df', 1)}")
    p_val = bias.get('p_value', 1.0)
    alpha = bias.get('alpha', 0.05)
    lines.append(f"  {'P-Value':<30}: {p_val:.4f} ({'Significant at alpha=' + str(alpha) if bias.get('is_significant') else 'Not Significant'})")
    lines.append("")

    # Gage Repeatability
    rep = result.get("repeatability", {})
    lines.append("Gage Repeatability")
    lines.append(f"  {'Pre-Adjusted Repeatability':<30}: {rep.get('pre_adjusted', 0.0):.6g}")
    lines.append(f"  {'Adjusted Repeatability':<30}: {rep.get('adjusted', 0.0):.6g}")
    lines.append(f"  {'Adjustment Factor':<30}: {rep.get('adjustment_factor', 1.08):.2f}")
    lines.append(f"  {'Study Multiplier':<30}: {rep.get('study_multiplier', 5.15):.2f}")
    if rep.get("tolerance") is not None:
        lines.append(f"  {'Tolerance':<30}: {rep.get('tolerance', 0.0):.6g}")
        if rep.get("pct_repeatability") is not None:
            lines.append(f"  {'% Repeatability (%Tolerance)':<30}: {rep.get('pct_repeatability', 0.0):.2f}%")
    lines.append("")

    return "\n".join(lines)
