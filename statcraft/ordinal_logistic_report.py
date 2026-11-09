"""Session window report generator for Ordinal Logistic Regression.

Formats output matching Minitab session window styling:
- Response Information table (Categories, Counts)
- Logistic Regression Table (Thresholds & Predictor coefficients with SE, Z, P, CI)
- Odds Ratios Table (Predictor, Odds Ratio, 95% CI)
- Goodness-of-Fit Tests (Pearson & Deviance Chi-Square, DF, P-Value)
- Measures of Association (Concordant, Discordant, Tied pairs, Somers' D, Gamma, Kendall's Tau-a)
- Model Summary (Log-Likelihood, Deviance R-sq, AIC, BIC)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_ordinal_logistic_report(result: Dict[str, Any]) -> str:
    """Format Ordinal Logistic Regression results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Ordinal Logistic Regression")
    lines.append(title)
    lines.append("")

    # Response Information
    lines.append("Response Information")
    resp_name = result.get("response_name", "Response")
    levels = result.get("levels", [])
    counts = result.get("counts_by_level", [])
    n_tot = result.get("n_obs", sum(counts))

    hdr_resp = f"{'Variable':<14}  {'Value':<16}  {'Count':>8}"
    lines.append(hdr_resp)
    lines.append("-" * len(hdr_resp))

    for idx, lvl in enumerate(levels):
        var_col = resp_name if idx == 0 else ""
        lines.append(f"{var_col:<14}  {str(lvl):<16}  {counts[idx]:>8}")
    lines.append(f"{'':<14}  {'Total':<16}  {n_tot:>8}")
    lines.append("")

    # Logistic Regression Table
    lines.append("Logistic Regression Table")
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    hdr_coef = f"{'Predictor':<16}  {'Coef':>10}  {'SE Coef':>10}  {'Z-Value':>8}  {'P-Value':>8}  {f'{conf_pct}% CI':^22}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))

    for c in result.get("coefficients", []):
        tname = c.get("term", "")
        b = c.get("coef", 0.0)
        se = c.get("se_coef", 0.0)
        z = c.get("z_value", 0.0)
        p = c.get("p_value", 0.0)
        ci_l = c.get("ci_lower", 0.0)
        ci_u = c.get("ci_upper", 0.0)
        ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
        lines.append(f"{tname:<16}  {b:>10.4f}  {se:>10.4f}  {z:>8.2f}  {p:>8.3f}  {ci_str:^22}")
    lines.append("")

    # Odds Ratios
    odds_list = result.get("odds_ratios", [])
    if odds_list:
        lines.append("Odds Ratios")
        hdr_or = f"{'Predictor':<16}  {'Odds Ratio':>12}  {f'{conf_pct}% CI':^22}"
        lines.append(hdr_or)
        lines.append("-" * len(hdr_or))
        for o in odds_list:
            pname = o.get("predictor", "")
            or_val = o.get("odds_ratio", 1.0)
            ci_l = o.get("ci_lower", 1.0)
            ci_u = o.get("ci_upper", 1.0)
            ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
            lines.append(f"{pname:<16}  {or_val:>12.4f}  {ci_str:^22}")
        lines.append("")

    # Goodness-of-Fit Tests
    lines.append("Goodness-of-Fit Tests")
    hdr_gof = f"{'Method':<14}  {'Chi-Square':>12}  {'DF':>6}  {'P-Value':>8}"
    lines.append(hdr_gof)
    lines.append("-" * len(hdr_gof))
    for g in result.get("goodness_of_fit", []):
        mname = g.get("method", "")
        chi = g.get("chi_square", 0.0)
        df = g.get("df", 0)
        p = g.get("p_value", 0.0)
        lines.append(f"{mname:<14}  {chi:>12.2f}  {df:>6}  {p:>8.3f}")
    lines.append("")

    # Measures of Association
    assoc = result.get("association", {})
    if assoc:
        lines.append("Measures of Association")
        lines.append(f"{'Pairs':<14}  {'Number':>8}  {'Percent':>9}  {'Summary Measures':<24}")
        lines.append("-" * 62)
        c_num = assoc.get("concordant", 0)
        c_pct = assoc.get("pct_concordant", 0.0)
        d_num = assoc.get("discordant", 0)
        d_pct = assoc.get("pct_discordant", 0.0)
        t_num = assoc.get("tied", 0)
        t_pct = assoc.get("pct_tied", 0.0)
        tot_num = assoc.get("total_pairs", 0)

        lines.append(f"{'Concordant':<14}  {c_num:>8}  {c_pct:>8.1f}%  Somers' D               {assoc.get('somers_d', 0.0):>6.2f}")
        lines.append(f"{'Discordant':<14}  {d_num:>8}  {d_pct:>8.1f}%  Goodman-Kruskal Gamma   {assoc.get('gamma', 0.0):>6.2f}")
        lines.append(f"{'Tied':<14}  {t_num:>8}  {t_pct:>8.1f}%  Kendall's Tau-a         {assoc.get('kendalls_tau_a', 0.0):>6.2f}")
        lines.append(f"{'Total':<14}  {tot_num:>8}  {100.0:>8.1f}%")
        lines.append("")

    # Model Summary
    lines.append("Model Summary")
    lines.append(
        f"Log-Likelihood = {result.get('log_likelihood', 0.0):.2f}, "
        f"Deviance R-sq = {result.get('deviance_r_sq', 0.0):.2f}%, "
        f"AIC = {result.get('aic', 0.0):.2f}, "
        f"BIC = {result.get('bic', 0.0):.2f}"
    )

    return "\n".join(lines)
