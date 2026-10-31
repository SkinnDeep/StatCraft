"""Report formatting and structured table extraction for Accelerated Life Testing (ALT).

Matches Minitab 22 and JMP session window and interactive card structures.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_alt_report(entry: Dict[str, Any]) -> str:
    """Format full session text report matching Minitab 22 Accelerated Life Testing."""
    res = entry.get("result", entry)
    time_name = str(res.get("time_name", "Time"))
    stress_name = str(res.get("stress_name", "Stress"))
    model = str(res.get("model", "arrhenius")).replace("_", " ").title()
    dist = str(res.get("distribution", "weibull")).capitalize()
    conf = float(res.get("confidence", 95.0))

    lines = [
        f"Accelerated Life Testing: {time_name} versus {stress_name}",
        "",
        "Model Description",
        f"  Response: {time_name}",
        f"  Stress factor: {stress_name}",
        f"  Relationship: {model}",
        f"  Assumed distribution: {dist}",
        f"  Estimation method: Maximum Likelihood (MLE)",
        "",
        "Censoring Information       Count",
        f"  Uncensored observations     {res.get('n_failed', 0)}",
        f"  Right censored observations {res.get('n_censored', 0)}",
        f"  Total observations          {res.get('n_total', 0)}",
        "",
        f"Model Summary",
        f"  Log-Likelihood: {_fmt(res.get('log_likelihood'), 3)}",
        f"  AIC:            {_fmt(res.get('aic'), 3)}",
        f"  BIC:            {_fmt(res.get('bic'), 3)}",
        "",
        "Parameter Estimates",
        f"  {'Parameter':28s} {'Estimate':>10s} {'SE Coef':>10s} {f'{conf:g}% Normal CI':>24s} {'Z':>8s} {'P':>8s}",
        "  " + "-" * 92,
    ]

    for p in res.get("params_table", []):
        param_str = p.get("parameter", "")
        est = _fmt(p.get("estimate"), 4)
        se = _fmt(p.get("se"), 4)
        ci_str = f"({_fmt(p.get('ci_lower'), 4)}, {_fmt(p.get('ci_upper'), 4)})"
        z_str = _fmt(p.get("z_val"), 2)
        p_str = _fmt(p.get("p_val"), 4)
        lines.append(f"  {param_str:28s} {est:>10s} {se:>10s} {ci_str:>24s} {z_str:>8s} {p_str:>8s}")

    use_s = res.get("use_stress")
    pcts = res.get("percentiles", [])
    if use_s is not None and pcts:
        lines.extend([
            "",
            f"Table of Percentiles at Normal Use Conditions ({stress_name} = {use_s})",
            f"  {'Percentile':16s} {'Estimate':>12s} {'SE Coef':>12s} {f'{conf:g}% Normal CI':>26s}",
            "  " + "-" * 70,
        ])
        for pct in pcts:
            lbl = pct.get("label", f"{pct.get('percentile', 0)}%")
            est = _fmt(pct.get("estimate"), 4)
            se = _fmt(pct.get("se"), 4)
            ci_str = f"({_fmt(pct.get('ci_lower'), 4)}, {_fmt(pct.get('ci_upper'), 4)})"
            lines.append(f"  {lbl:16s} {est:>12s} {se:>12s} {ci_str:>26s}")

    afs = res.get("acceleration_factors", [])
    if use_s is not None and afs:
        lines.extend([
            "",
            f"Acceleration Factors Relative to Use Condition ({stress_name} = {use_s})",
            f"  {stress_name:>12s} {'Acceleration Factor':>22s}",
            "  " + "-" * 36,
        ])
        for af in afs:
            s_val = _fmt(af.get("stress"), 2)
            af_val = _fmt(af.get("acceleration_factor"), 4)
            lines.append(f"  {s_val:>12s} {af_val:>22s}")

    return "\n".join(lines)


def get_alt_structured_tables(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured card tables for rich Report tab rendering."""
    tables = []
    time_name = str(res.get("time_name", "Time"))
    stress_name = str(res.get("stress_name", "Stress"))
    conf = float(res.get("confidence", 95.0))

    # 1. Model Summary & Censoring Information
    desc_rows = [
        ["Response", time_name],
        ["Stress Factor", stress_name],
        ["Acceleration Relationship", str(res.get("model", "arrhenius")).replace("_", " ").title()],
        ["Assumed Distribution", str(res.get("distribution", "weibull")).capitalize()],
        ["Uncensored Observations (Failures)", str(res.get("n_failed", 0))],
        ["Right-Censored Observations", str(res.get("n_censored", 0))],
        ["Total Observations", str(res.get("n_total", 0))],
        ["Log-Likelihood", _fmt(res.get("log_likelihood"), 3)],
        ["AIC", _fmt(res.get("aic"), 3)],
        ["BIC", _fmt(res.get("bic"), 3)],
    ]
    tables.append({
        "title": "Model Summary & Censoring Information",
        "headers": ["Measure", "Value"],
        "rows": desc_rows,
    })

    # 2. Parameter Estimates
    param_headers = ["Parameter", "Estimate", "SE Coef", f"{conf:g}% Normal CI", "Z-Value", "P-Value"]
    param_rows = []
    for p in res.get("params_table", []):
        param_rows.append([
            p.get("parameter", ""),
            _fmt(p.get("estimate"), 4),
            _fmt(p.get("se"), 4),
            f"({_fmt(p.get('ci_lower'), 4)}, {_fmt(p.get('ci_upper'), 4)})",
            _fmt(p.get("z_val"), 2),
            _fmt(p.get("p_val"), 4),
        ])
    tables.append({
        "title": "Parameter Estimates",
        "headers": param_headers,
        "rows": param_rows,
    })

    # 3. Percentiles at Use Condition
    use_s = res.get("use_stress")
    pcts = res.get("percentiles", [])
    if use_s is not None and pcts:
        pct_headers = ["Percentile", "Estimate (Life)", "SE Coef", f"{conf:g}% Normal CI"]
        pct_rows = []
        for pct in pcts:
            pct_rows.append([
                pct.get("label", f"{pct.get('percentile', 0)}%"),
                _fmt(pct.get("estimate"), 4),
                _fmt(pct.get("se"), 4),
                f"({_fmt(pct.get('ci_lower'), 4)}, {_fmt(pct.get('ci_upper'), 4)})",
            ])
        tables.append({
            "title": f"Table of Percentiles at Use Conditions ({stress_name} = {use_s})",
            "headers": pct_headers,
            "rows": pct_rows,
        })

    # 4. Acceleration Factors
    afs = res.get("acceleration_factors", [])
    if use_s is not None and afs:
        af_headers = [f"Stress ({stress_name})", "Acceleration Factor (AF)"]
        af_rows = []
        for af in afs:
            af_rows.append([
                _fmt(af.get("stress"), 2),
                _fmt(af.get("acceleration_factor"), 4),
            ])
        tables.append({
            "title": f"Acceleration Factors Relative to Normal Use ({stress_name} = {use_s})",
            "headers": af_headers,
            "rows": af_rows,
        })

    return tables
