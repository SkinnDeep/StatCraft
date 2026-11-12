"""Standard statistical Descriptive Statistics Report Formatter for StatCraft."""
from __future__ import annotations


_DEFAULT_STAT_KEYS = (
    "count", "missing", "mean", "standard_error", "sample_stdev",
    "minimum", "q1", "median", "q3", "maximum",
)

_STAT_LABELS = {
    "count": ("N", 6),
    "missing": ("N*", 6),
    "n_total": ("Total", 7),
    "mean": ("Mean", 12),
    "standard_error": ("SE Mean", 11),
    "sample_stdev": ("StDev", 12),
    "sample_variance": ("Variance", 12),
    "coef_var": ("CoefVar", 11),
    "trimmed_mean": ("TrMean", 12),
    "sum": ("Sum", 12),
    "minimum": ("Minimum", 12),
    "q1": ("Q1", 10),
    "median": ("Median", 11),
    "q3": ("Q3", 10),
    "maximum": ("Maximum", 12),
    "range": ("Range", 12),
    "iqr": ("IQR", 10),
    "skewness": ("Skewness", 11),
    "kurtosis": ("Kurtosis", 11),
    "mode": ("Mode", 11),
}

_INT_KEYS = {"count", "missing", "n_total"}


def format_descriptive_stats_report(result: dict) -> str:
    columns = result.get('columns', [])
    if not columns:
        return ""

    has_groups = any(col.get('by_level') is not None for col in columns)
    selected = result.get('selected_statistics')
    stat_keys = [k for k in (selected or _DEFAULT_STAT_KEYS) if k in _STAT_LABELS]
    if not stat_keys:
        stat_keys = list(_DEFAULT_STAT_KEYS)

    lines = []
    lines.append("Descriptive Statistics")
    lines.append("")

    header = "Variable".ljust(16)
    if has_groups:
        by_hdr = str(columns[0].get('by_variable') or 'Group')[:14]
        header += by_hdr.ljust(16)
    for k in stat_keys:
        lbl, width = _STAT_LABELS[k]
        header += lbl.rjust(width)
    lines.append(header)

    for col in columns:
        row_str = str(col.get('name', 'C'))[:14].ljust(16)
        if has_groups:
            row_str += str(col.get('by_level', ''))[:14].ljust(16)
        for k in stat_keys:
            _, width = _STAT_LABELS[k]
            val = col.get(k)
            if val is None:
                cell = "*"
            elif k in _INT_KEYS:
                cell = str(int(val))
            else:
                cell = f"{val:.4f}"
            row_str += cell.rjust(width)
        lines.append(row_str)

    has_warnings = False
    for col in columns:
        for warning in col.get("warnings", []):
            if not has_warnings:
                lines.append("")
                has_warnings = True
            lines.append("  Note (" + str(col.get('name', 'C')) + "): " + warning)

    lines.append("")
    lines.append("N* counts missing values. StDev and SE Mean use sample variance (n-1).")
    return "\n".join(lines)
