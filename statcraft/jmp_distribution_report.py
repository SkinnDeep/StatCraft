"""Session report and structured tables for JMP Distribution platform."""
from __future__ import annotations

from typing import Any, Dict, List


def format_jmp_distribution_report(entry: Dict[str, Any]) -> str:
    """Format full text session report for JMP Distribution."""
    res = entry.get("result", entry)
    variables = res.get("variables", [])
    lines = [
        "JMP Distribution Platform",
        "=" * 60,
        ""
    ]

    for var in variables:
        v_name = var.get("variable", "Variable")
        v_type = var.get("type", "continuous")

        lines.append(f"Distributions: {v_name}")
        lines.append("-" * 40)

        if v_type == "continuous":
            lines.append("Quantiles")
            lines.append(f"  {'Level':15s} {'Quantile':>14s}")
            lines.append("  " + "-" * 32)
            q_dict = var.get("quantiles", {})
            for q_name, q_val in q_dict.items():
                lines.append(f"  {q_name:15s} {q_val:14.5f}")

            lines.append("")
            lines.append("Summary Statistics")
            lines.append(f"  {'Statistic':25s} {'Value':>14s}")
            lines.append("  " + "-" * 42)
            lines.append(f"  {'Mean':25s} {var.get('mean', 0.0):14.5f}")
            lines.append(f"  {'Std Dev':25s} {var.get('std_dev', 0.0):14.5f}")
            lines.append(f"  {'Std Err Mean':25s} {var.get('std_err', 0.0):14.5f}")
            lines.append(f"  {'Upper 95% Mean':25s} {var.get('ci_upper', 0.0):14.5f}")
            lines.append(f"  {'Lower 95% Mean':25s} {var.get('ci_lower', 0.0):14.5f}")
            lines.append(f"  {'N':25s} {var.get('n', 0):14d}")
            lines.append(f"  {'Sum':25s} {var.get('sum', 0.0):14.5f}")
            lines.append(f"  {'Variance':25s} {var.get('variance', 0.0):14.5f}")
            lines.append(f"  {'Skewness':25s} {var.get('skewness', 0.0):14.5f}")
            lines.append(f"  {'Kurtosis':25s} {var.get('kurtosis', 0.0):14.5f}")
            lines.append(f"  {'CV (%)':25s} {var.get('cv', 0.0):14.5f}")
            lines.append("")
        else:
            lines.append("Frequencies")
            lines.append(f"  {'Level':20s} {'Count':>8s} {'Prob':>10s} {'Cum Count':>10s} {'Cum Prob':>10s}")
            lines.append("  " + "-" * 62)
            for f in var.get("frequencies", []):
                lines.append(f"  {f['level'][:20]:20s} {f['count']:8d} {f['prob']:10.5f} {f['cum_count']:10d} {f['cum_prob']:10.5f}")
            lines.append("")

    return "\n".join(lines)


def get_jmp_distribution_structured_tables(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate structured table cards for ModernWindow display."""
    tables = []
    variables = res.get("variables", [])

    for var in variables:
        v_name = var.get("variable", "Variable")
        v_type = var.get("type", "continuous")

        if v_type == "continuous":
            # 1. Quantiles Table
            q_rows = []
            q_dict = var.get("quantiles", {})
            for q_name, q_val in q_dict.items():
                q_rows.append([q_name, f"{q_val:.5f}"])

            tables.append({
                "title": f"Quantiles: {v_name}",
                "headers": ["Quantile Level", "Value"],
                "rows": q_rows
            })

            # 2. Summary Statistics Table
            s_rows = [
                ["Mean", f"{var.get('mean', 0.0):.5f}"],
                ["Std Dev", f"{var.get('std_dev', 0.0):.5f}"],
                ["Std Err Mean", f"{var.get('std_err', 0.0):.5f}"],
                ["Upper 95% Mean", f"{var.get('ci_upper', 0.0):.5f}"],
                ["Lower 95% Mean", f"{var.get('ci_lower', 0.0):.5f}"],
                ["N (Observations)", str(var.get('n', 0))],
                ["Sum", f"{var.get('sum', 0.0):.5f}"],
                ["Variance", f"{var.get('variance', 0.0):.5f}"],
                ["Skewness", f"{var.get('skewness', 0.0):.5f}"],
                ["Kurtosis", f"{var.get('kurtosis', 0.0):.5f}"],
                ["CV (%)", f"{var.get('cv', 0.0):.3f}%"],
            ]
            tables.append({
                "title": f"Summary Statistics: {v_name}",
                "headers": ["Measure", "Value"],
                "rows": s_rows
            })

            # 3. Extreme Observations
            ext_rows = []
            for low, high in zip(var.get("lowest_5", []), var.get("highest_5", [])):
                ext_rows.append([
                    str(low.get("row", "")), f"{low.get('value', 0.0):.4f}",
                    str(high.get("row", "")), f"{high.get('value', 0.0):.4f}"
                ])
            if ext_rows:
                tables.append({
                    "title": f"Extreme Observations: {v_name}",
                    "headers": ["Lowest Row", "Lowest Value", "Highest Row", "Highest Value"],
                    "rows": ext_rows
                })

        else:
            # Categorical Frequencies Table
            f_rows = []
            for f in var.get("frequencies", []):
                f_rows.append([
                    str(f.get("level", "")),
                    str(f.get("count", 0)),
                    f"{f.get('prob', 0.0):.5f}",
                    f"{f.get('std_err', 0.0):.5f}",
                    str(f.get("cum_count", 0)),
                    f"{f.get('cum_prob', 0.0):.5f}"
                ])
            tables.append({
                "title": f"Frequencies: {v_name}",
                "headers": ["Level", "Count", "Probability", "Std Error", "Cum Count", "Cum Prob"],
                "rows": f_rows
            })

    return tables
