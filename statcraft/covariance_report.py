"""Covariance Report Formatter for StatCraft.

Formats Standard statistical lower-triangular covariance matrix session output.
"""
from __future__ import annotations


def format_covariance_report(result: dict) -> str:
    lines = []
    lines.append("Covariances")
    lines.append("")
    lines.append(f"Missing Value Policy: {result.get('missing', 'Pairwise')} deletion")
    lines.append("")

    variables = result.get('variables', [])
    matrix = result.get('matrix', [])
    n_matrix = result.get('n_matrix', [])

    # Format lower triangular matrix table
    col_width = 16
    var_width = max(len(v) for v in variables) if variables else 12
    var_width = max(var_width + 2, 14)

    # Column headers
    header_line = "".ljust(var_width) + "".join(v[:14].rjust(col_width) for v in variables)
    lines.append(header_line)

    for i, var_row in enumerate(variables):
        row_str = var_row.ljust(var_width)
        for j in range(i + 1):
            val = matrix[i][j]
            val_str = f"{val:.6g}" if val is not None else "*"
            row_str += val_str.rjust(col_width)
        lines.append(row_str)

    if result.get('warnings'):
        lines.append("")
        for w in result['warnings']:
            lines.append(f"* NOTE * {w}")

    return "\n".join(lines)
