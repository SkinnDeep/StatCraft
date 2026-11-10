"""Minitab-Identical Session Report Formatter for Marginal Plot.
"""
from __future__ import annotations

from typing import Any, Dict


def format_marginal_plot_report(result: Dict[str, Any]) -> str:
    """Format session text report for Marginal Plot."""
    lines: list[str] = []
    y_name = result.get('y_name', 'Y')
    x_name = result.get('x_name', 'X')
    m_type = result.get('marginal_type', 'histogram').capitalize()
    n = result.get('n', 0)

    lines.append(f'Marginal Plot of {y_name} vs {x_name}')
    lines.append('═' * 76)
    lines.append(f'Marginal Type: {m_type}')
    if result.get('show_normal_curve'):
        lines.append('Fit: Normal density curve overlay')
    lines.append(f'Number of complete observations: {n}')
    lines.append('')

    # Correlation
    r = result.get('correlation', 0.0)
    p = result.get('p_value', 1.0)
    slope = result.get('slope', 0.0)
    intercept = result.get('intercept', 0.0)

    lines.append('Correlation & Fitted Line')
    lines.append(f'  Pearson correlation of {y_name} and {x_name} = {r:.4f}')
    lines.append(f'  P-Value = {p:.4f}')
    lines.append(f'  Regression Equation: {y_name} = {intercept:.4f} + {slope:.4f} {x_name}')
    lines.append('')

    # Descriptive Statistics Table
    lines.append('Summary Statistics')
    header = f'{"Variable":<18}{"N":>6}{"Mean":>12}{"StDev":>12}{"Min":>10}{"Median":>10}{"Max":>10}'
    lines.append(header)
    lines.append('─' * len(header))

    xs = result.get('x_stats', {})
    ys = result.get('y_stats', {})

    def fmt_row(var_name: str, st: Dict[str, Any]) -> str:
        box = st.get('box', {})
        return (
            f'{var_name:<18}'
            f'{n:>6}'
            f'{st.get("mean", 0.0):>12.4f}'
            f'{st.get("stdev", 0.0):>12.4f}'
            f'{st.get("min", 0.0):>10.4f}'
            f'{box.get("median", 0.0):>10.4f}'
            f'{st.get("max", 0.0):>10.4f}'
        )

    lines.append(fmt_row(x_name, xs))
    lines.append(fmt_row(y_name, ys))
    lines.append('')

    return '\n'.join(lines)
