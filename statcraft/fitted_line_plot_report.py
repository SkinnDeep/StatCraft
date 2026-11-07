"""Minitab-standard session report formatter for Fitted Line Plot."""
from __future__ import annotations

from typing import Any, Dict


def format_fitted_line_plot_report(result: Dict[str, Any]) -> str:
    """Format polynomial regression results matching Minitab 22 standard."""
    lines = []
    x_name = result.get("x_name", "X")
    y_name = result.get("y_name", "Y")
    m_type = result.get("model_type", "linear").capitalize()

    lines.append(f"Fitted Line Plot: {y_name} versus {x_name}\n")
    lines.append(f"Polynomial Regression Analysis: {y_name} versus {x_name} ({m_type})\n")

    # 1. Regression Equation
    lines.append("Regression Equation")
    lines.append(f"  {result.get('equation', '')}\n")

    # 2. Coefficients
    coefs = result.get("coefficients", [])
    if coefs:
        lines.append("Coefficients")
        lines.append(f"  {'Term':<15} {'Coef':>10} {'SE Coef':>10} {'T-Value':>10} {'P-Value':>10}")
        for c in coefs:
            p_str = "< 0.001" if c['p'] < 0.001 else f"{c['p']:.3f}"
            lines.append(f"  {c['term']:<15} {c['coef']:>10.4f} {c['se_coef']:>10.4f} {c['t']:>10.2f} {p_str:>10}")
        lines.append("")

    # 3. Model Summary
    s = result.get("s", 0.0)
    r2 = result.get("r_squared", 0.0) * 100.0
    r2_adj = result.get("r_squared_adj", 0.0) * 100.0
    r2_pred = result.get("r_squared_pred", 0.0) * 100.0

    lines.append("Model Summary")
    lines.append(f"  {'S':>10} {'R-sq':>10} {'R-sq(adj)':>12} {'R-sq(pred)':>12}")
    lines.append(f"  {s:>10.4f} {r2:>9.2f}% {r2_adj:>11.2f}% {r2_pred:>11.2f}%\n")

    # 4. Analysis of Variance
    anova = result.get("anova", {})
    if anova:
        lines.append("Analysis of Variance")
        lines.append(f"  {'Source':<16} {'DF':>5} {'Adj SS':>12} {'Adj MS':>12} {'F-Value':>10} {'P-Value':>10}")
        reg = anova.get("regression", {})
        p_reg = "< 0.001" if reg.get('p', 1.0) < 0.001 else f"{reg.get('p', 0.0):.3f}"
        lines.append(f"  {'Regression':<16} {reg.get('df', 1):>5} {reg.get('ss', 0.0):>12.2f} {reg.get('ms', 0.0):>12.2f} {reg.get('f', 0.0):>10.2f} {p_reg:>10}")

        seq = anova.get("sequential", [])
        for term in seq:
            p_t = "< 0.001" if term.get('p', 1.0) < 0.001 else f"{term.get('p', 0.0):.3f}"
            lines.append(f"    {term['source']:<14} {term['df']:>5} {term['ss']:>12.2f} {term['ms']:>12.2f} {term['f']:>10.2f} {p_t:>10}")

        err = anova.get("error", {})
        lines.append(f"  {'Error':<16} {err.get('df', 1):>5} {err.get('ss', 0.0):>12.2f} {err.get('ms', 0.0):>12.2f}")

        tot = anova.get("total", {})
        lines.append(f"  {'Total':<16} {tot.get('df', 1):>5} {tot.get('ss', 0.0):>12.2f}\n")

    # 5. Fits and Diagnostics for Unusual Observations
    unusual = result.get("unusual_observations", [])
    if unusual:
        lines.append("Fits and Diagnostics for Unusual Observations")
        lines.append(f"  {'Obs':>5} {y_name:>10} {'Fit':>10} {'Resid':>10} {'Std Resid':>10} {'Leverage':>10} {'Flag':>5}")
        for u in unusual:
            lines.append(
                f"  {u['obs']:>5} {u['y']:>10.4f} {u['fit']:>10.4f} {u['resid']:>10.4f} {u['std_resid']:>10.2f} {u['leverage']:>10.4f} {u['flag']:>5}"
            )
        lines.append("\n  R  Large residual")
        lines.append("  X  Unusual X (High leverage)\n")

    return "\n".join(lines)
