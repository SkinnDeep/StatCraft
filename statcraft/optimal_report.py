"""Report formatting and structured table extraction for D-Optimal Custom Designs and Design Diagnostics.

Matches JMP Pro "Evaluate Design" and Minitab 22 "Optimal Design" session structure.
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


def format_optimal_design_report(entry: Dict[str, Any]) -> str:
    """Format full session text report for D-Optimal Custom Design generation and evaluation."""
    res = entry.get("result", entry)
    design_name = str(res.get("design_name", "Custom D-Optimal Design"))
    n_runs = int(res.get("n_runs", 0))
    model_order = str(res.get("model_order", "interactions")).capitalize()
    eval_res = res.get("eval", {})

    d_eff = float(eval_res.get("d_efficiency", 0.0))
    a_eff = float(eval_res.get("a_efficiency", 0.0))
    g_eff = float(eval_res.get("g_efficiency", 0.0))
    avg_var = float(eval_res.get("average_variance", 0.0))
    max_var = float(eval_res.get("max_variance", 0.0))
    p_terms = int(eval_res.get("n_terms", 0))
    df_error = max(0, n_runs - p_terms)

    lines = [
        f"Custom Design (D-Optimal) — {design_name}",
        "",
        "Design Summary",
        f"  Number of runs:           {n_runs}",
        f"  Number of factors:        {len(res.get('factors', []))}",
        f"  Assumed model structure:  {model_order}",
        f"  Model terms estimated:    {p_terms}",
        f"  Degrees of freedom error: {df_error}",
        "",
        "Design Optimality & Diagnostics",
        f"  D-Efficiency:             {d_eff:.2f}% (Maximizes |X'X|; minimizes parameter variance)",
        f"  A-Efficiency:             {a_eff:.2f}% (Minimizes trace((X'X)^-1); average coef variance)",
        f"  G-Efficiency:             {g_eff:.2f}% (Minimizes peak prediction variance)",
        f"  Average Prediction Var:   {avg_var:.4f}",
        f"  Maximum Prediction Var:   {max_var:.4f}",
        "",
        "Factors Description",
        f"  {'Factor Name':24s} {'Type':16s} {'Settings / Range':28s}",
        "  " + "-" * 70,
    ]

    for f in res.get("factors", []):
        f_name = str(f.get("name", ""))
        f_kind = str(f.get("kind", "continuous")).capitalize()
        if f.get("kind") == "continuous":
            sett = f"{f.get('low', -1)} to {f.get('high', 1)}"
        else:
            levs = f.get("levels", ["L1", "L2"])
            sett = f"[{', '.join(levs)}]"
        lines.append(f"  {f_name:24s} {f_kind:16s} {sett:28s}")

    # Correlated terms table (off-diagonal correlations > 0.01)
    corr_mat = eval_res.get("correlation_matrix", [])
    term_names = res.get("term_names", [])
    correlated_pairs = []

    if corr_mat and term_names:
        for i in range(1, len(term_names)):
            for j in range(i + 1, len(term_names)):
                r_val = abs(corr_mat[i][j])
                if r_val > 0.01:
                    correlated_pairs.append((term_names[i], term_names[j], r_val))

    if correlated_pairs:
        lines.extend([
            "",
            "Correlated Model Effects (Confounding / Aliasing)",
            f"  {'Effect 1':20s} {'Effect 2':20s} {'Absolute Correlation (|r|)':>26s}",
            "  " + "-" * 68,
        ])
        for t1, t2, r in sorted(correlated_pairs, key=lambda it: it[2], reverse=True)[:15]:
            lines.append(f"  {t1:20s} {t2:20s} {r:>26.4f}")
    else:
        lines.extend([
            "",
            "Orthogonality Assessment: All model effects are completely orthogonal (|r| = 0.000).",
        ])

    return "\n".join(lines)


def get_optimal_structured_tables(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured card tables for rich Report tab rendering."""
    tables = []
    eval_res = res.get("eval", {})
    n_runs = int(res.get("n_runs", 0))
    p_terms = int(eval_res.get("n_terms", 0))

    # 1. Design Summary & Optimality
    diag_rows = [
        ["Total Runs (N)", str(n_runs)],
        ["Estimated Model Terms (p)", str(p_terms)],
        ["Degrees of Freedom for Error", str(max(0, n_runs - p_terms))],
        ["D-Efficiency", f"{eval_res.get('d_efficiency', 0.0):.2f}%"],
        ["A-Efficiency", f"{eval_res.get('a_efficiency', 0.0):.2f}%"],
        ["G-Efficiency", f"{eval_res.get('g_efficiency', 0.0):.2f}%"],
        ["Average Prediction Variance", f"{eval_res.get('average_variance', 0.0):.4f}"],
        ["Maximum Prediction Variance", f"{eval_res.get('max_variance', 0.0):.4f}"],
    ]
    tables.append({
        "title": "Design Diagnostics & Efficiency Summary",
        "headers": ["Metric", "Value"],
        "rows": diag_rows,
    })

    # 2. Factor Definitions
    factor_rows = []
    for f in res.get("factors", []):
        f_name = str(f.get("name", ""))
        f_kind = str(f.get("kind", "continuous")).capitalize()
        if f.get("kind") == "continuous":
            sett = f"{f.get('low', -1)} to {f.get('high', 1)}"
        else:
            levs = f.get("levels", ["L1", "L2"])
            sett = f"[{', '.join(levs)}]"
        factor_rows.append([f_name, f_kind, sett])

    tables.append({
        "title": "Factors and Settings",
        "headers": ["Factor", "Type", "Range / Levels"],
        "rows": factor_rows,
    })

    # 3. Aliasing / Correlation Table
    corr_mat = eval_res.get("correlation_matrix", [])
    term_names = res.get("term_names", [])
    corr_rows = []
    if corr_mat and term_names:
        for i in range(1, len(term_names)):
            for j in range(i + 1, len(term_names)):
                r_val = abs(corr_mat[i][j])
                if r_val > 0.01:
                    status = "High Confounding" if r_val > 0.5 else ("Moderate Correlation" if r_val > 0.2 else "Low Correlation")
                    corr_rows.append([term_names[i], term_names[j], f"{r_val:.4f}", status])

    if corr_rows:
        tables.append({
            "title": "Correlated Model Effects (Aliasing)",
            "headers": ["Effect 1", "Effect 2", "|Correlation|", "Status"],
            "rows": sorted(corr_rows, key=lambda it: float(it[2]), reverse=True)[:20],
        })

    return tables
