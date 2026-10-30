"""Session window text report formatting for Reliability Distribution Analysis."""

from __future__ import annotations
from typing import Any, Dict


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_reliability_report(entry: Dict[str, Any]) -> str:
    """Format full session text report matching StatCraft."""
    res = entry.get("result", entry)
    var_name = res.get("variable_name", entry.get("variable_name", res.get("variable", "Lifetime")))
    dist = res.get("dist_name", "weibull").capitalize()

    lines = [
        f"\n\nDistribution Analysis: {var_name}",
        f"Variable: {var_name}",
        f"Assumed distribution: {dist}",
        "",
        "Censoring Information       Count",
        f"  Uncensored value            {res.get('n_events', 0)}",
        f"  Right censored value        {res.get('n_censored', 0)}",
        f"  Total observations          {res.get('n_total', 0)}",
        "",
        "Estimation Method: Maximum Likelihood (MLE)",
        f"Log-Likelihood: {_fmt(res.get('log_likelihood'), 3)}",
        "",
        "Table of Parameters",
    ]

    params = res.get("parameters", {})
    for k, v in params.items():
        lines.append(f"  {k.capitalize():15s}: {_fmt(v)}")
    lines.append(f"  Mean Time To Failure (MTTF): {_fmt(res.get('mttf'))}")
    lines.append("")

    lines.append("Table of Percentiles")
    level = res.get('confidence_level', 0.95) * 100
    lines.append(f"  Percent     Estimate       {level:g}% confidence interval")
    lines.append('  Method: ' + res.get('inference_method', 'Not retained in this snapshot'))
    lines.append("                           Lower          Upper")
    lines.append("  ---------------------------------------------")

    ptable = res.get("percentile_table", [])
    for row in ptable:
        pct = row.get("percent", 0.0)
        est = row.get("estimate", 0.0)
        low = row.get("lower", 0.0)
        high = row.get("upper", 0.0)
        lines.append(f"  {pct:5.1f}%   {_fmt(est):>12}   {_fmt(low):>12}   {_fmt(high):>12}")
    lines.append("")

    lines.extend(['', 'Goodness of Fit', '  AD: ' + _fmt(res.get('ad_stat')), '  Method: ' + res.get('ad_method', 'Not retained')])
    lines.extend(str(message) for message in res.get('warnings', []))
    return "\n".join(lines)
