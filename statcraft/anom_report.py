"""Minitab 22 standard session report formatter for Analysis of Means (ANOM)."""
from __future__ import annotations

from typing import Any, Dict


def format_anom_report(result: Dict[str, Any]) -> str:
    """Format Analysis of Means session report matching Minitab 22 text output."""
    res_type = result.get("type", "one_way")
    if res_type == "two_way":
        return _format_anom_twoway_report(result)
    return _format_anom_oneway_report(result)


def _format_anom_oneway_report(result: Dict[str, Any]) -> str:
    lines = []
    title = result.get("title", "Analysis of Means")
    resp_name = result.get("response_name", "Response")
    factor_name = result.get("factor_name", "Factor")
    dist = result.get("distribution", "normal").capitalize()
    alpha = float(result.get("alpha", 0.05))
    grand_mean = float(result.get("grand_mean", 0.0))
    crit_val = float(result.get("critical_value", 0.0))

    lines.append("=" * 76)
    lines.append(f"  {title.upper()}")
    lines.append("=" * 76)
    lines.append("")
    lines.append(f"Distribution:   {dist}")
    lines.append(f"Response:       {resp_name}")
    lines.append(f"Factor:         {factor_name}")
    lines.append(f"Alpha Level:    {alpha:g}  (Decision limits: α = {alpha:g})")
    lines.append(f"Center Line:    {grand_mean:.4f}")
    if dist.lower() == "normal":
        lines.append(f"Pooled StDev:   {float(result.get('pooled_sd', 0.0)):.4f} (df = {result.get('df', 0)})")
    lines.append(f"Critical Value: {crit_val:.4f}")
    lines.append("")
    lines.append("-" * 76)
    lines.append(f"{'Factor Level':<16} {'N':>6} {'Mean/Rate':>12} {'LDL':>10} {'Center':>10} {'UDL':>10} {'Signif':>8}")
    lines.append("-" * 76)

    for l in result.get("levels", []):
        lvl = str(l.get("level", ""))[:15]
        n_val = l.get("n", 0)
        mean_val = float(l.get("mean", 0.0))
        ldl = float(l.get("ldl", 0.0))
        udl = float(l.get("udl", 0.0))
        sig = "*" if l.get("significant") else ""
        lines.append(f"{lvl:<16} {n_val:>6} {mean_val:>12.4f} {ldl:>10.4f} {grand_mean:>10.4f} {udl:>10.4f} {sig:>8}")

    lines.append("-" * 76)
    if result.get("outliers_detected"):
        lines.append("* Indicates a factor level mean that differs significantly from the overall mean.")
    else:
        lines.append("No factor level means differ significantly from the overall mean at the specified α level.")
    lines.append("")
    return "\n".join(lines)


def _format_anom_twoway_report(result: Dict[str, Any]) -> str:
    lines = []
    title = result.get("title", "Two-Way Analysis of Means")
    resp_name = result.get("response_name", "Response")
    f1_name = result.get("factor1_name", "Factor 1")
    f2_name = result.get("factor2_name", "Factor 2")
    alpha = float(result.get("alpha", 0.05))
    grand_mean = float(result.get("grand_mean", 0.0))
    s_p = float(result.get("pooled_sd", 0.0))
    df = result.get("df", 0)

    lines.append("=" * 76)
    lines.append(f"  {title.upper()}")
    lines.append("=" * 76)
    lines.append("")
    lines.append(f"Distribution:   Normal")
    lines.append(f"Response:       {resp_name}")
    lines.append(f"Factors:        {f1_name}, {f2_name}")
    lines.append(f"Alpha Level:    {alpha:g}")
    lines.append(f"Center Line:    {grand_mean:.4f}")
    lines.append(f"Pooled StDev:   {s_p:.4f} (df = {df})")
    lines.append("")

    # Main Effects Factor 1
    lines.append("--- Main Effects: " + f1_name + " ---")
    f1 = result.get("factor1", {})
    lines.append(f"{'Level':<16} {'N':>6} {'Mean':>12} {'LDL':>10} {'Center':>10} {'UDL':>10} {'Signif':>8}")
    lines.append("-" * 76)
    for l in f1.get("levels", []):
        sig = "*" if l.get("significant") else ""
        lines.append(f"{str(l['level'])[:15]:<16} {l['n']:>6} {float(l['mean']):>12.4f} {float(l['ldl']):>10.4f} {grand_mean:>10.4f} {float(l['udl']):>10.4f} {sig:>8}")
    lines.append("")

    # Main Effects Factor 2
    lines.append("--- Main Effects: " + f2_name + " ---")
    f2 = result.get("factor2", {})
    lines.append(f"{'Level':<16} {'N':>6} {'Mean':>12} {'LDL':>10} {'Center':>10} {'UDL':>10} {'Signif':>8}")
    lines.append("-" * 76)
    for l in f2.get("levels", []):
        sig = "*" if l.get("significant") else ""
        lines.append(f"{str(l['level'])[:15]:<16} {l['n']:>6} {float(l['mean']):>12.4f} {float(l['ldl']):>10.4f} {grand_mean:>10.4f} {float(l['udl']):>10.4f} {sig:>8}")
    lines.append("")

    # Interaction Effects
    lines.append("--- Two-Way Interaction Effects (" + f1_name + " * " + f2_name + ") ---")
    inter = result.get("interaction", {})
    lines.append(f"{'Interaction Cell':<24} {'N':>6} {'Effect':>12} {'LDL':>10} {'Center':>10} {'UDL':>10} {'Signif':>8}")
    lines.append("-" * 76)
    for l in inter.get("levels", []):
        sig = "*" if l.get("significant") else ""
        lines.append(f"{str(l['level'])[:23]:<24} {l['n']:>6} {float(l['mean']):>12.4f} {float(l['ldl']):>10.4f} {0.0:>10.4f} {float(l['udl']):>10.4f} {sig:>8}")
    lines.append("-" * 76)
    lines.append("* Indicates significant deviation from overall mean or interaction reference.")
    lines.append("")
    return "\n".join(lines)
