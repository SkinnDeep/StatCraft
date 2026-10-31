"""Report formatting and structured table extraction for Evaluating the Measurement Process (EMP).

References Dr. Donald J. Wheeler's EMP methodology (EMP III) and JMP EMP Gauge analysis.
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


def format_emp_report(entry: Dict[str, Any]) -> str:
    """Format full text session report for Wheeler EMP Analysis matching JMP & Minitab style."""
    res = entry.get("result", entry)
    meas_name = str(res.get("meas_name", "Measurement"))
    part_name = str(res.get("part_name", "Part"))
    op_name = str(res.get("op_name", "Operator"))

    rho = float(res.get("rho", 0.0))
    attenuation = float(res.get("attenuation", 0.0))
    emp_class = str(res.get("emp_class", "First Class"))
    class_desc = str(res.get("class_desc", ""))
    pe = float(res.get("probable_error", 0.0))
    res_val = float(res.get("resolution", 0.0))
    res_status = str(res.get("resolution_status", ""))

    lines = [
        f"Evaluating the Measurement Process (EMP) — Wheeler Method",
        f"Response: {meas_name} | Part: {part_name} | Operator: {op_name}",
        "",
        "Measurement System Classification",
        f"  Intraclass Correlation (ICC / ρ): {rho:.4f} ({rho*100:.1f}%)",
        f"  Process Signal Attenuation:       {attenuation:.4f} ({attenuation*100:.1f}%)",
        f"  Monitor Classification:           {emp_class}",
        f"  Assessment:                       {class_desc}",
        "",
        "Measurement Precision & Resolution Diagnostics",
        f"  Probable Error (PE = 0.6745·σe):  {pe:.4f}",
        f"  Smallest Effective Unit (0.2–2·PE): {0.2*pe:.4f} to {2.0*pe:.4f}",
        f"  Observed Measurement Resolution:  {res_val:.4f}",
        f"  Resolution Diagnosis:             {res_status}",
        "",
        "Variance Components Breakdown",
        f"  {'Source':30s} {'Variance':>12s} {'% of Total':>12s} {'Std Dev':>12s}",
        "  " + "-" * 68,
    ]

    for c in res.get("components", []):
        src = c.get("source", "")
        v = _fmt(c.get("var"), 5)
        pct = f"{c.get('pct', 0.0):.2f}%"
        sd = _fmt(c.get("sd"), 5)
        lines.append(f"  {src:30s} {v:>12s} {pct:>12s} {sd:>12s}")

    lines.extend([
        "",
        "Shift Detection Probabilities (Shift in Process Mean)",
        f"  {'Shift':>8s} {'Effective Shift':>18s} {'Subgroup 1':>12s} {'Subgroups 1-2':>14s} {'Subgroups 1-3':>14s} {'Subgroups 1-4':>14s}",
        "  " + "-" * 82,
    ])

    for s in res.get("shift_table", []):
        sh = str(s.get("shift", ""))
        de = _fmt(s.get("delta_eff"), 3)
        p1 = f"{s.get('p_subgroup_1', 0.0)*100:.1f}%"
        p2 = f"{s.get('p_subgroup_2', 0.0)*100:.1f}%"
        p3 = f"{s.get('p_subgroup_3', 0.0)*100:.1f}%"
        p4 = f"{s.get('p_subgroup_4', 0.0)*100:.1f}%"
        lines.append(f"  {sh:>8s} {de:>18s} {p1:>12s} {p2:>14s} {p3:>14s} {p4:>14s}")

    return "\n".join(lines)


def get_emp_structured_tables(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured card tables for rich Report tab rendering."""
    tables = []

    # 1. Classification & Diagnostics summary
    diag_rows = [
        ["Intraclass Correlation (ICC / ρ)", f"{res.get('rho', 0.0):.4f} ({res.get('rho', 0.0)*100:.1f}%)"],
        ["Process Signal Attenuation", f"{res.get('attenuation', 0.0):.4f} ({res.get('attenuation', 0.0)*100:.1f}%)"],
        ["Wheeler Classification", str(res.get("emp_class", ""))],
        ["Probable Error (PE)", f"{res.get('probable_error', 0.0):.4f}"],
        ["Smallest Effective Unit (0.2·PE – 2·PE)", f"{0.2*res.get('probable_error', 0.0):.4f} – {2.0*res.get('probable_error', 0.0):.4f}"],
        ["Observed Resolution", f"{res.get('resolution', 0.0):.4f}"],
        ["Resolution Diagnosis", str(res.get("resolution_status", ""))],
    ]
    tables.append({
        "title": "Wheeler EMP Classification & Resolution Diagnostics",
        "headers": ["Metric", "Value"],
        "rows": diag_rows,
    })

    # 2. Variance components table
    vc_rows = []
    for c in res.get("components", []):
        vc_rows.append([
            c.get("source", ""),
            f"{c.get('var', 0.0):.5f}",
            f"{c.get('pct', 0.0):.2f}%",
            f"{c.get('sd', 0.0):.5f}",
        ])
    tables.append({
        "title": "Variance Components Breakdown",
        "headers": ["Source", "Variance", "% of Total", "Std Dev"],
        "rows": vc_rows,
    })

    # 3. Shift detection table
    shift_rows = []
    for s in res.get("shift_table", []):
        shift_rows.append([
            str(s.get("shift", "")),
            f"{s.get('delta_eff', 0.0):.3f}",
            f"{s.get('p_subgroup_1', 0.0)*100:.1f}%",
            f"{s.get('p_subgroup_2', 0.0)*100:.1f}%",
            f"{s.get('p_subgroup_3', 0.0)*100:.1f}%",
            f"{s.get('p_subgroup_4', 0.0)*100:.1f}%",
        ])
    tables.append({
        "title": "Shift Detection Probabilities Across Subgroups",
        "headers": ["Shift", "Effective Shift (δ)", "Subgroup 1", "Subgroups 1–2", "Subgroups 1–3", "Subgroups 1–4"],
        "rows": shift_rows,
    })

    return tables
