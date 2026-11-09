"""Session window report generator for Repairable Systems Analysis.

Formats output matching Minitab session window styling:
1. Nonparametric Growth Curve (Mean Cumulative Function - MCF):
   - Header, Sample Summary (Systems, Total Events)
   - MCF Table (Time, Events, Systems At Risk, MCF Estimate, SE, 95% CI)

2. Parametric Growth Curve (Power Law / Crow-AMSAA):
   - Parameter Estimates (Shape beta MLE & Unbiased, Scale lambda, SE, 95% CIs)
   - Trend Tests for Constant Failure Rate (MIL-HDBK-189 and Laplace Test)
   - Table of Cumulative Events, Failure Rate, and MTBF Horizons
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_repairable_systems_report(result: Dict[str, Any]) -> str:
    """Format Nonparametric or Parametric Growth Curve results into Minitab session text report."""
    analysis = result.get("analysis")
    if analysis == "nonparametric_growth_curve":
        return _format_nonparametric_mcf(result)
    elif analysis == "parametric_growth_curve":
        return _format_parametric_growth(result)
    return str(result.get("title", "Repairable Systems Analysis"))


def _format_nonparametric_mcf(res: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(res.get("title", "Nonparametric Growth Curve (MCF)"))
    lines.append("")

    sys_name = res.get("system_name", "System")
    t_name = res.get("time_name", "Time")
    lines.append(f"System Variable: {sys_name}")
    lines.append(f"Time Variable:   {t_name}")
    lines.append(f"Number of Systems: {res.get('n_systems', 0)}")
    lines.append(f"Total Recurrent Events: {res.get('total_events', 0)}")
    lines.append("")

    # MCF Table
    conf_pct = int(round(res.get("confidence", 0.95) * 100))
    lines.append("Mean Cumulative Function (MCF) Table")
    hdr = f"{'Time':>10}  {'Events':>8}  {'At Risk':>8}  {'MCF':>10}  {'SE MCF':>10}  {f'{conf_pct}% CI':^22}"
    lines.append(hdr)
    lines.append("-" * len(hdr))

    table = res.get("mcf_table", [])
    # Display at most 30 rows evenly spaced if table is large
    step = max(1, len(table) // 30) if len(table) > 40 else 1
    display_rows = table[::step]
    if table and table[-1] not in display_rows:
        display_rows.append(table[-1])

    for row in display_rows:
        t = row.get("time", 0.0)
        ev = row.get("events", 0)
        risk = row.get("at_risk", 0)
        mcf = row.get("mcf", 0.0)
        se = row.get("se", 0.0)
        ci_l = row.get("ci_lower", 0.0)
        ci_u = row.get("ci_upper", 0.0)
        ci_str = f"({ci_l:.4f}, {ci_u:.4f})"
        lines.append(f"{t:>10.2f}  {ev:>8}  {risk:>8}  {mcf:>10.4f}  {se:>10.4f}  {ci_str:^22}")

    lines.append("")
    return "\n".join(lines)


def _format_parametric_growth(res: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(res.get("title", "Parametric Growth Curve (Power Law / Crow-AMSAA)"))
    lines.append("")

    sys_name = res.get("system_name", "System")
    t_name = res.get("time_name", "Time")
    lines.append(f"System Variable: {sys_name}")
    lines.append(f"Time Variable:   {t_name}")
    lines.append(f"Number of Systems: {res.get('n_systems', 0)}")
    lines.append(f"Total Recurrent Events: {res.get('total_events', 0)}")
    lines.append("")

    # Parameter Estimates
    p = res.get("parameters", {})
    conf_pct = int(round(res.get("confidence", 0.95) * 100))
    lines.append("Parameter Estimates (Power Law Process: mu(t) = lambda * t^beta)")
    hdr_p = f"{'Parameter':<18}  {'Estimate':>10}  {'SE':>10}  {f'{conf_pct}% CI':^24}"
    lines.append(hdr_p)
    lines.append("-" * len(hdr_p))

    ci_b = p.get("ci_beta", (0.0, 0.0))
    ci_b_str = f"({ci_b[0]:.4f}, {ci_b[1]:.4f})"
    lines.append(f"{'Shape (beta, MLE)':<18}  {p.get('shape_beta_mle', 0.0):>10.4f}  {p.get('se_beta', 0.0):>10.4f}  {ci_b_str:^24}")
    lines.append(f"{'Shape (Unbiased)':<18}  {p.get('shape_beta_unbiased', 0.0):>10.4f}")

    ci_l = p.get("ci_lambda", (0.0, 0.0))
    ci_l_str = f"({ci_l[0]:.4e}, {ci_l[1]:.4e})"
    lines.append(f"{'Scale (lambda, MLE)':<18}  {p.get('scale_lambda_mle', 0.0):>10.4e}  {p.get('se_lambda', 0.0):>10.4e}  {ci_l_str:^24}")
    lines.append("")

    # Trend Tests
    tt = res.get("trend_tests", {})
    lines.append("Tests for Constant Failure Rate (H0: beta = 1 versus H1: beta != 1)")
    hdr_t = f"{'Test':<20}  {'Statistic':>12}  {'DF / Z':>10}  {'P-Value':>10}"
    lines.append(hdr_t)
    lines.append("-" * len(hdr_t))
    lines.append(f"{'MIL-HDBK-189 (ChiSq)':<20}  {tt.get('mil_hdbk_stat', 0.0):>12.2f}  {tt.get('mil_hdbk_df', 1):>10}  {tt.get('mil_hdbk_p', 0.0):>10.4f}")
    lines.append(f"{'Laplace (Standard Norm)':<20}  {tt.get('laplace_z', 0.0):>12.2f}  {'Z':>10}  {tt.get('laplace_p', 0.0):>10.4f}")
    lines.append("")
    lines.append(f"Conclusion: {tt.get('trend_description', '')}")
    lines.append("")

    # Event, Failure Rate & MTBF Horizons
    lines.append(f"Estimated Cumulative Events, Failure Rate, and MTBF Horizons")
    hdr_pred = f"{'Time':>10}  {'Cum Events':>12}  {'Failure Rate':>14}  {'MTBF':>12}  {f'{conf_pct}% MTBF CI':^24}"
    lines.append(hdr_pred)
    lines.append("-" * len(hdr_pred))

    for r in res.get("predictions", []):
        t = r.get("time", 0.0)
        cum_ev = r.get("cumulative_events", 0.0)
        fr = r.get("failure_rate", 0.0)
        mtbf = r.get("mtbf", 0.0)
        ci_l = r.get("ci_mtbf_lower", 0.0)
        ci_u = r.get("ci_mtbf_upper", 0.0)
        ci_str = f"({ci_l:.2f}, {ci_u:.2f})"
        lines.append(f"{t:>10.1f}  {cum_ev:>12.2f}  {fr:>14.4e}  {mtbf:>12.2f}  {ci_str:^24}")

    lines.append("")
    return "\n".join(lines)
