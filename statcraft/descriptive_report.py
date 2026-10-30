"""Standard statistical Descriptive Statistics Report Formatter for StatCraft."""
from __future__ import annotations


def format_descriptive_stats_report(result: dict) -> str:
    columns = result.get('columns', [])
    if not columns:
        return ""

    lines = []
    lines.append("Descriptive Statistics")
    lines.append("")

    # Standard StatCraft table header
    # Variable        N   N*     Mean  SE Mean    StDev   Minimum        Q1     Median        Q3     Maximum
    header = "Variable".ljust(16) + "N".rjust(6) + "N*".rjust(6) + "Mean".rjust(12) + "SE Mean".rjust(11) + "StDev".rjust(12) + "Minimum".rjust(12) + "Q1".rjust(10) + "Median".rjust(11) + "Q3".rjust(10) + "Maximum".rjust(12)
    lines.append(header)

    for col in columns:
        name = str(col.get('name', 'C'))[:14].ljust(16)
        n = str(col.get('count', 0)).rjust(6)
        n_star = str(col.get('missing', 0)).rjust(6)

        mean = f"{col['mean']:.4f}".rjust(12) if col.get('mean') is not None else "*".rjust(12)
        se_mean = f"{col['standard_error']:.4f}".rjust(11) if col.get('standard_error') is not None else "*".rjust(11)
        stdev = f"{col['sample_stdev']:.4f}".rjust(12) if col.get('sample_stdev') is not None else "*".rjust(12)
        c_min = f"{col['minimum']:.4f}".rjust(12) if col.get('minimum') is not None else "*".rjust(12)
        q1 = f"{col['q1']:.4f}".rjust(10) if col.get('q1') is not None else "*".rjust(10)
        median = f"{col['median']:.4f}".rjust(11) if col.get('median') is not None else "*".rjust(11)
        q3 = f"{col['q3']:.4f}".rjust(10) if col.get('q3') is not None else "*".rjust(10)
        c_max = f"{col['maximum']:.4f}".rjust(12) if col.get('maximum') is not None else "*".rjust(12)

        lines.append(name + n + n_star + mean + se_mean + stdev + c_min + q1 + median + q3 + c_max)

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
