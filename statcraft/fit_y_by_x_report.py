"""Session report and structured table generation for JMP Fit Y by X."""
from __future__ import annotations

from typing import Any, Dict, List


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_fit_y_by_x_report(entry: Dict[str, Any]) -> str:
    """Format full text session report for Fit Y by X matching JMP style."""
    res = entry.get("result", entry)
    plat = res.get("platform", "bivariate")
    y_name = res.get("y_name", "Y")
    x_name = res.get("x_name", "X")

    lines = []

    if plat == "bivariate":
        lines.extend([
            f"Bivariate Fit of {y_name} By {x_name}",
            "=" * 60,
            f"Linear Fit",
            f"  {res.get('equation', '')}",
            "",
            "Summary of Fit",
            f"  RSquare:                         {res.get('r_sq', 0.0):.6f}",
            f"  RSquare Adj:                     {res.get('r_sq_adj', 0.0):.6f}",
            f"  Root Mean Square Error:          {res.get('rmse', 0.0):.6f}",
            f"  Mean of Response:                {res.get('mean_y', 0.0):.6f}",
            f"  Observations (or Sum Wgts):      {res.get('n', 0)}",
            "",
            "Analysis of Variance",
            f"  {'Source':15s} {'DF':>6s} {'Sum of Squares':>16s} {'Mean Square':>14s} {'F Ratio':>10s} {'Prob > F':>10s}",
            "  " + "-" * 75,
        ])
        an = res.get("anova", {})
        lines.append(f"  {'Model':15s} {an.get('df_model', 1):6d} {_fmt(an.get('ss_model'), 6):>16s} {_fmt(an.get('ms_model'), 6):>14s} {_fmt(an.get('f_ratio'), 4):>10s} {_fmt(an.get('p_val'), 4):>10s}")
        lines.append(f"  {'Error':15s} {an.get('df_error', 1):6d} {_fmt(an.get('ss_error'), 6):>16s} {_fmt(an.get('ms_error'), 6):>14s}")
        lines.append(f"  {'C. Total':15s} {an.get('df_total', 1):6d} {_fmt(an.get('ss_total'), 6):>16s}")
        lines.extend([
            "",
            "Parameter Estimates",
            f"  {'Term':15s} {'Estimate':>12s} {'Std Error':>12s} {'t Ratio':>10s} {'Prob > |t|':>12s}",
            "  " + "-" * 65,
        ])
        for pe in res.get("parameter_estimates", []):
            lines.append(f"  {pe.get('term', ''):15s} {_fmt(pe.get('estimate'), 6):>12s} {_fmt(pe.get('std_error'), 6):>12s} {_fmt(pe.get('t_ratio'), 2):>10s} {_fmt(pe.get('p_val'), 4):>12s}")

    elif plat == "oneway":
        lines.extend([
            f"Oneway Analysis of {y_name} By {x_name}",
            "=" * 60,
            f"Grand Mean: {res.get('grand_mean', 0.0):.4f} | Pooled SD: {res.get('s_pooled', 0.0):.4f}",
            "",
            "Oneway Anova",
            f"  {'Source':15s} {'DF':>6s} {'Sum of Squares':>16s} {'Mean Square':>14s} {'F Ratio':>10s} {'Prob > F':>10s}",
            "  " + "-" * 75,
        ])
        an = res.get("anova", {})
        lines.append(f"  {x_name:15s} {an.get('df_between', 1):6d} {_fmt(an.get('ss_between'), 6):>16s} {_fmt(an.get('ms_between'), 6):>14s} {_fmt(an.get('f_ratio'), 4):>10s} {_fmt(an.get('p_val'), 4):>10s}")
        lines.append(f"  {'Error':15s} {an.get('df_within', 1):6d} {_fmt(an.get('ss_within'), 6):>16s} {_fmt(an.get('ms_within'), 6):>14s}")
        lines.append(f"  {'C. Total':15s} {an.get('df_total', 1):6d} {_fmt(an.get('ss_total'), 6):>16s}")

        wan = res.get("welch_anova", {})
        lines.extend([
            "",
            "Welch's Test (Unequal Variances)",
            f"  F Ratio:   {_fmt(wan.get('f_ratio'), 4)}",
            f"  DF Num:    {wan.get('df_num', 1)}",
            f"  DF Denom:  {_fmt(wan.get('df_denom'), 4)}",
            f"  Prob > F:  {_fmt(wan.get('p_val'), 4)}",
            "",
            "Means for Oneway Anova",
            f"  {'Level':15s} {'Number':>8s} {'Mean':>12s} {'Std Dev':>12s} {'Std Err':>12s} {'Lower 95%':>12s} {'Upper 95%':>12s}",
            "  " + "-" * 88,
        ])
        for gs in res.get("group_stats", []):
            lines.append(f"  {str(gs.get('level')):15s} {gs.get('n', 0):8d} {_fmt(gs.get('mean'), 4):>12s} {_fmt(gs.get('std_dev'), 4):>12s} {_fmt(gs.get('std_error'), 4):>12s} {_fmt(gs.get('ci_lower'), 4):>12s} {_fmt(gs.get('ci_upper'), 4):>12s}")

        lines.extend([
            "",
            "All Pairs, Tukey-Kramer HSD",
            f"  {'Level - Level':25s} {'Difference':>12s} {'Std Error':>12s} {'Lower CL':>12s} {'Upper CL':>12s} {'p-Value':>10s}",
            "  " + "-" * 86,
        ])
        for tk in res.get("tukey_hsd", []):
            pair_lbl = f"{tk.get('level_1')} - {tk.get('level_2')}"
            sig_flag = " *" if tk.get("significant") else ""
            lines.append(f"  {pair_lbl:25s} {_fmt(tk.get('difference'), 4):>12s} {_fmt(tk.get('std_error'), 4):>12s} {_fmt(tk.get('lower_cl'), 4):>12s} {_fmt(tk.get('upper_cl'), 4):>12s} {_fmt(tk.get('p_val'), 4):>10s}{sig_flag}")

    elif plat == "contingency":
        lines.extend([
            f"Contingency Analysis of {y_name} By {x_name}",
            "=" * 60,
            f"Total Observations: {res.get('n', 0)}",
            "",
            "Tests",
            f"  {'Test':20s} {'ChiSquare':>12s} {'DF':>6s} {'Prob > ChiSq':>14s}",
            "  " + "-" * 56,
            f"  {'Likelihood Ratio':20s} {_fmt(res.get('g2'), 4):>12s} {res.get('df', 1):6d} {_fmt(res.get('p_g2'), 4):>14s}",
            f"  {'Pearson':20s} {_fmt(res.get('chi2'), 4):>12s} {res.get('df', 1):6d} {_fmt(res.get('p_chi2'), 4):>14s}",
            "",
            "Contingency Table",
        ])
        x_lvls = res.get("x_levels", [])
        hdr = f"  {'Level':15s} " + " ".join(f"{str(xl):>10s}" for xl in x_lvls) + "       Total"
        lines.append(hdr)
        lines.append("  " + "-" * len(hdr))
        for row in res.get("grid_rows", []):
            cnt_str = f"  {str(row.get('y_level')):15s} " + " ".join(f"{c.get('count', 0):10d}" for c in row.get("cells", [])) + f" {row.get('row_total', 0):10d}"
            lines.append(cnt_str)

    return "\n".join(lines)


def get_fit_y_by_x_structured_tables(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured card tables for Report workbook rendering."""
    tables = []
    plat = res.get("platform", "bivariate")
    y_name = res.get("y_name", "Y")
    x_name = res.get("x_name", "X")

    if plat == "bivariate":
        # 1. Summary of fit
        tables.append({
            "title": "Summary of Fit",
            "headers": ["Metric", "Value"],
            "rows": [
                ["RSquare", f"{res.get('r_sq', 0.0):.6f}"],
                ["RSquare Adj", f"{res.get('r_sq_adj', 0.0):.6f}"],
                ["Root Mean Square Error", f"{res.get('rmse', 0.0):.6f}"],
                ["Mean of Response", f"{res.get('mean_y', 0.0):.6f}"],
                ["Observations (Sum Wgts)", str(res.get("n", 0))],
            ]
        })

        # 2. ANOVA
        an = res.get("anova", {})
        tables.append({
            "title": "Analysis of Variance",
            "headers": ["Source", "DF", "Sum of Squares", "Mean Square", "F Ratio", "Prob > F"],
            "rows": [
                ["Model", str(an.get("df_model", 1)), f"{an.get('ss_model', 0.0):.5f}", f"{an.get('ms_model', 0.0):.5f}", f"{an.get('f_ratio', 0.0):.4f}", f"{an.get('p_val', 1.0):.4f}"],
                ["Error", str(an.get("df_error", 1)), f"{an.get('ss_error', 0.0):.5f}", f"{an.get('ms_error', 0.0):.5f}", "", ""],
                ["C. Total", str(an.get("df_total", 1)), f"{an.get('ss_total', 0.0):.5f}", "", "", ""]
            ]
        })

        # 3. Parameter Estimates
        pe_rows = []
        for pe in res.get("parameter_estimates", []):
            pe_rows.append([
                pe.get("term", ""),
                f"{pe.get('estimate', 0.0):.5f}",
                f"{pe.get('std_error', 0.0):.5f}",
                f"{pe.get('t_ratio', 0.0):.2f}",
                f"{pe.get('p_val', 1.0):.4f}"
            ])
        tables.append({
            "title": "Parameter Estimates",
            "headers": ["Term", "Estimate", "Std Error", "t Ratio", "Prob > |t|"],
            "rows": pe_rows
        })

    elif plat == "oneway":
        # 1. ANOVA
        an = res.get("anova", {})
        tables.append({
            "title": f"Oneway ANOVA: {y_name} by {x_name}",
            "headers": ["Source", "DF", "Sum of Squares", "Mean Square", "F Ratio", "Prob > F"],
            "rows": [
                [x_name, str(an.get("df_between", 1)), f"{an.get('ss_between', 0.0):.5f}", f"{an.get('ms_between', 0.0):.5f}", f"{an.get('f_ratio', 0.0):.4f}", f"{an.get('p_val', 1.0):.4f}"],
                ["Error", str(an.get("df_within", 1)), f"{an.get('ss_within', 0.0):.5f}", f"{an.get('ms_within', 0.0):.5f}", "", ""],
                ["C. Total", str(an.get("df_total", 1)), f"{an.get('ss_total', 0.0):.5f}", "", "", ""]
            ]
        })

        # 2. Welch's Test
        wan = res.get("welch_anova", {})
        tables.append({
            "title": "Welch's Test (Robust to Unequal Variances)",
            "headers": ["Test", "F Ratio", "DF Num", "DF Denom", "Prob > F"],
            "rows": [
                ["Welch", f"{wan.get('f_ratio', 0.0):.4f}", str(wan.get("df_num", 1)), f"{wan.get('df_denom', 1.0):.4f}", f"{wan.get('p_val', 1.0):.4f}"]
            ]
        })

        # 3. Means & Standard Deviations
        m_rows = []
        for gs in res.get("group_stats", []):
            m_rows.append([
                str(gs.get("level")),
                str(gs.get("n", 0)),
                f"{gs.get('mean', 0.0):.4f}",
                f"{gs.get('std_dev', 0.0):.4f}",
                f"{gs.get('std_error', 0.0):.4f}",
                f"{gs.get('ci_lower', 0.0):.4f}",
                f"{gs.get('ci_upper', 0.0):.4f}"
            ])
        tables.append({
            "title": "Means and Standard Deviations for Oneway Anova",
            "headers": ["Level", "Number", "Mean", "Std Dev", "Std Err", "Lower 95%", "Upper 95%"],
            "rows": m_rows
        })

        # 4. Quantiles
        q_rows = []
        for gs in res.get("group_stats", []):
            q_rows.append([
                str(gs.get("level")),
                f"{gs.get('min', 0.0):.4f}",
                f"{gs.get('q25', 0.0):.4f}",
                f"{gs.get('median', 0.0):.4f}",
                f"{gs.get('q75', 0.0):.4f}",
                f"{gs.get('max', 0.0):.4f}"
            ])
        tables.append({
            "title": "Quantiles by Level",
            "headers": ["Level", "Minimum", "25%", "Median", "75%", "Maximum"],
            "rows": q_rows
        })

        # 5. All Pairs Tukey-Kramer HSD
        tk_rows = []
        for tk in res.get("tukey_hsd", []):
            tk_rows.append([
                f"{tk.get('level_1')} vs {tk.get('level_2')}",
                f"{tk.get('difference', 0.0):.4f}",
                f"{tk.get('std_error', 0.0):.4f}",
                f"{tk.get('lower_cl', 0.0):.4f}",
                f"{tk.get('upper_cl', 0.0):.4f}",
                f"{tk.get('p_val', 1.0):.4f}",
                "Yes *" if tk.get("significant") else "No"
            ])
        tables.append({
            "title": "All Pairs, Tukey-Kramer HSD (q = 0.05)",
            "headers": ["Comparison", "Difference", "Std Error", "Lower CL", "Upper CL", "p-Value", "Significant?"],
            "rows": tk_rows
        })

    elif plat == "contingency":
        # 1. Tests
        tables.append({
            "title": "Tests of Independence",
            "headers": ["Test", "ChiSquare", "DF", "Prob > ChiSq"],
            "rows": [
                ["Likelihood Ratio", f"{res.get('g2', 0.0):.4f}", str(res.get("df", 1)), f"{res.get('p_g2', 1.0):.4f}"],
                ["Pearson", f"{res.get('chi2', 0.0):.4f}", str(res.get("df", 1)), f"{res.get('p_chi2', 1.0):.4f}"]
            ]
        })

        # 2. Contingency Table
        x_lvls = res.get("x_levels", [])
        c_headers = [f"{y_name} \\ {x_name}"] + [str(xl) for xl in x_lvls] + ["Total"]
        c_rows = []
        for r in res.get("grid_rows", []):
            row_vals = [str(r.get("y_level"))] + [str(c.get("count", 0)) for c in r.get("cells", [])] + [str(r.get("row_total", 0))]
            c_rows.append(row_vals)
        tables.append({
            "title": "Contingency Table (Frequencies)",
            "headers": c_headers,
            "rows": c_rows
        })

    return tables
