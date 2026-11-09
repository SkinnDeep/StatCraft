"""Session window report generator for Gage R&R Study (Expanded).

Formats output matching Minitab session window styling:
- Title and Design factors
- Analysis of Variance Table (Source, DF, SS, MS, F, P)
- Variance Components Table (Source, VarComp, %Contribution)
- Gage Evaluation Table (Source, StdDev, Study Var, %Study Var, %Tolerance, %Process)
- Number of Distinct Categories (ndc)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_gage_rr_expanded_report(result: Dict[str, Any]) -> str:
    """Format Expanded Gage R&R results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Gage R&R Study (Expanded)")
    lines.append(title)
    lines.append("")

    # ANOVA Table
    lines.append("Analysis of Variance")
    hdr_aov = f"{'Source':<24}  {'DF':>6}  {'SS':>12}  {'MS':>12}  {'F-Value':>8}  {'P-Value':>8}"
    lines.append(hdr_aov)
    lines.append("-" * len(hdr_aov))

    for row in result.get("anova", []):
        src = row.get("source", "")
        df = row.get("df", 0)
        ss = row.get("ss", 0.0)
        ms = row.get("ms")
        f_val = row.get("f")
        p_val = row.get("p_value")

        ms_str = f"{ms:>12.4f}" if ms is not None else "".rjust(12)
        f_str = f"{f_val:>8.2f}" if f_val is not None and not (isinstance(f_val, float) and math.isnan(f_val)) else "".rjust(8)
        p_str = f"{p_val:>8.3f}" if p_val is not None else "".rjust(8)

        lines.append(f"{src:<24}  {df:>6}  {ss:>12.4f}  {ms_str}  {f_str}  {p_str}")
    lines.append("")

    lines.append("Gage R&R")
    # Variance Components Table
    lines.append("Variance Components")
    hdr_vc = f"{'Source':<32}  {'VarComp':>10}  {'%Contribution':>14}"
    lines.append(hdr_vc)
    lines.append("-" * len(hdr_vc))

    for row in result.get("variance_components", []):
        src = row.get("source", "")
        vc = row.get("var_comp", 0.0)
        pct = row.get("pct_contribution", 0.0)
        lines.append(f"{src:<32}  {vc:>10.5f}  {pct:>13.2f}%")
    lines.append("")

    # Gage Evaluation Table
    mult = result.get("study_multiplier", 6.0)
    has_tol = result.get("tolerance") is not None
    has_proc = result.get("process_stdev") is not None

    hdr_eval = f"{'Source':<32}  {'StdDev':>10}  {f'Study Var ({mult:g}*SD)':>16}  {'%Study Var':>12}"
    if has_tol:
        hdr_eval += f"  {'%Tolerance':>12}"
    if has_proc:
        hdr_eval += f"  {'%Process':>12}"

    lines.append("Gage Evaluation")
    lines.append(hdr_eval)
    lines.append("-" * len(hdr_eval))

    for row in result.get("gage_evaluation", []):
        src = row.get("source", "")
        sd = row.get("std_dev", 0.0)
        sv = row.get("study_var", 0.0)
        pct_sv = row.get("pct_study_var", 0.0)

        row_str = f"{src:<32}  {sd:>10.5f}  {sv:>16.5f}  {pct_sv:>11.2f}%"
        if has_tol:
            tol_val = row.get("pct_tolerance")
            tol_str = f"{tol_val:>11.2f}%" if tol_val is not None else "".rjust(12)
            row_str += f"  {tol_str}"
        if has_proc:
            proc_val = row.get("pct_process")
            proc_str = f"{proc_val:>11.2f}%" if proc_val is not None else "".rjust(12)
            row_str += f"  {proc_str}"
        lines.append(row_str)
    lines.append("")

    # Number of Distinct Categories
    ndc = result.get("ndc", 1)
    lines.append(f"Number of Distinct Categories = {ndc}")

    return "\n".join(lines)


import math
