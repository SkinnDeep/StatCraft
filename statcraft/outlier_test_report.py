"""Standard statistical text report for Grubbs' Outlier Test."""
from __future__ import annotations


def _fmt(val, dec=4):
    if val is None:
        return "*"
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


def format_outlier_report(result: dict) -> str:
    var_name = result.get('variable_name', 'Variable')
    n = result.get('n', 0)
    mean_val = result.get('mean', 0.0)
    stdev_val = result.get('stdev', 0.0)
    min_val = result.get('min', 0.0)
    max_val = result.get('max', 0.0)

    g_stat = result.get('g_stat', 0.0)
    g_crit = result.get('g_crit', 0.0)
    p_val = result.get('p_value', 1.0)
    alpha = result.get('alpha', 0.05)
    is_out = result.get('is_outlier', False)
    out_val = result.get('outlier_value')
    out_row = result.get('outlier_row')
    out_type = result.get('outlier_type', 'High')

    lines = [
        f"Outlier Test: {var_name}",
        "=" * 45,
        "",
        "Method",
        f"  Null hypothesis:          All data values come from the same normal population",
        f"  Alternative hypothesis:   Smallest or largest data value is an outlier",
        f"  Significance level:       α = {alpha}",
        "",
        "Descriptive Statistics",
        f"  N:                        {n}",
        f"  Mean:                     {_fmt(mean_val, 4)}",
        f"  StDev:                    {_fmt(stdev_val, 4)}",
        f"  Min:                      {_fmt(min_val, 4)}",
        f"  Max:                      {_fmt(max_val, 4)}",
        "",
        "Grubbs' Test",
        f"  Test statistic (G):       {_fmt(g_stat, 3)}",
        f"  Critical value:           {_fmt(g_crit, 3)}",
        f"  P-Value:                  {_fmt(p_val, 3) if p_val >= 0.001 else '< 0.001'}",
        "",
        "Conclusion",
    ]

    if is_out:
        lines.append(f"  An outlier is detected at row {out_row} ({out_type} value = {_fmt(out_val, 4)}).")
    else:
        lines.append("  There is not enough evidence to conclude that there is an outlier at the α significance level.")

    return "\n".join(lines)
