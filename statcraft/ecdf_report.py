"""Minitab-Identical Session Report Formatter for Empirical Cumulative Distribution Function (ECDF).
"""
from __future__ import annotations

from typing import Any, Dict


def format_ecdf_report(result: Dict[str, Any]) -> str:
    """Format session text report for Empirical CDF."""
    lines: list[str] = []
    var_name = result.get('variable_name', 'X')
    grp_name = result.get('group_name')
    dist = result.get('distribution', 'None')
    conf = result.get('confidence', 0.95)

    lines.append(f'Empirical Cumulative Distribution Function (ECDF) of {var_name}')
    lines.append('═' * 76)
    if grp_name:
        lines.append(f'Grouped by: {grp_name}')
    lines.append(f'Confidence Level: {conf*100:g}% (Simultaneous Dvoretzky-Kiefer-Wolfowitz Band)')
    if dist != 'None':
        lines.append(f'Fitted Distribution Overlay: {dist}')
    lines.append('')

    series = result.get('series', [])
    for s in series:
        g_name = s.get('group', var_name)
        n = s.get('n', 0)
        mean = s.get('mean', 0.0)
        sd = s.get('stdev', 0.0)
        med = s.get('median', 0.0)
        eps = s.get('epsilon', 0.0)

        lines.append(f'Group: {g_name}')
        lines.append(f'  Sample Size (N)     = {n}')
        lines.append(f'  Mean                = {mean:.5f}')
        lines.append(f'  Standard Deviation  = {sd:.5f}')
        lines.append(f'  Median              = {med:.5f}')
        lines.append(f'  Band Half-Width (ε) = {eps:.5f}')

        fit_p = s.get('fit_params', {})
        if fit_p:
            p_strs = [f'{k} = {v:.5f}' for k, v in fit_p.items()]
            lines.append(f'  Fitted Parameters: {", ".join(p_strs)}')
        lines.append('')

        # Percentiles Table
        lines.append('  Percentiles')
        if dist != 'None':
            hdr = f'    {"Percent":<10}{"Empirical":>14}{"Fitted":>14}'
        else:
            hdr = f'    {"Percent":<10}{"Empirical":>14}'
        lines.append(hdr)
        lines.append('    ' + '─' * (len(hdr) - 4))

        for row in s.get('percentiles', []):
            pct = row['percent']
            emp = row['empirical']
            fit = row.get('fitted')
            if fit is not None:
                lines.append(f'    {pct:<10}{emp:>14.4f}{fit:>14.4f}')
            else:
                lines.append(f'    {pct:<10}{emp:>14.4f}')
        lines.append('')

    return '\n'.join(lines)
