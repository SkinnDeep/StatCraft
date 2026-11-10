"""Minitab-Identical Session Report Formatter for Probability Distribution Plot.
"""
from __future__ import annotations

from typing import Any, Dict


def format_probability_distribution_report(result: Dict[str, Any]) -> str:
    """Format session text report for Probability Distribution Plot."""
    lines: list[str] = []
    dist = result.get('distribution', 'Normal')
    params = result.get('parameters', {})
    mode = result.get('mode', 'single')

    lines.append('Probability Distribution Plot')
    lines.append('═' * 76)
    lines.append(f'Distribution: {dist}')

    param_strs = []
    for k, v in params.items():
        name = k.replace('_', ' ').capitalize()
        param_strs.append(f'{name} = {v:g}' if isinstance(v, (int, float)) else f'{name} = {v}')
    if param_strs:
        lines.append(', '.join(param_strs))
    lines.append('')

    if mode == 'probability':
        shade_by = result.get('shade_by', 'probability').replace('_', ' ').capitalize()
        tail = result.get('tail', 'both')
        tail_map = {
            'right': 'Right Tail (Upper)',
            'left': 'Left Tail (Lower)',
            'both': 'Both Tails (Two-Sided)',
            'middle': 'Middle (Interval)',
        }
        lines.append('Shaded Area Analysis')
        lines.append(f'  Define Shaded Area By: {shade_by}')
        lines.append(f'  Selected Region:       {tail_map.get(tail, tail.capitalize())}')
        lines.append(f'  Total Probability:     {result.get("total_shaded_prob", 0.0):.6f}')
        lines.append('')

        cutoffs = result.get('cutoffs', [])
        if cutoffs:
            lines.append('Critical Values and Tail Probabilities')
            for i, c in enumerate(cutoffs, 1):
                x_val = c.get('x', 0.0)
                p_val = c.get('p', 0.0)
                lines.append(f'  Cutoff {i}:   {x_val:>12.5f}    Tail Probability: {p_val:.6f}')
            lines.append('')
    else:
        lines.append('Display Mode: View Single Distribution Curve')
        lines.append('')

    lines.append('Distribution Characteristics')
    lines.append(f'  Mean:               {result.get("mean", 0.0):>12.6f}')
    lines.append(f'  Variance:           {result.get("variance", 0.0):>12.6f}')
    lines.append(f'  Standard Deviation: {result.get("stdev", 0.0):>12.6f}')
    lines.append('')

    return '\n'.join(lines)
