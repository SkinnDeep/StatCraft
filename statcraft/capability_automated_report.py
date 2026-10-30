"""Session report formatting for Nonparametric and Automated Capability Analysis."""

from __future__ import annotations
from typing import Any, Dict


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_nonparametric_capability_report(entry: Dict[str, Any]) -> str:
    """Format session text report for Nonparametric Capability Analysis."""
    res = entry.get("result", entry)
    var_name = res.get("variable_name", entry.get("variable_name", res.get("variable", "Measurement")))
    is_vda = (res.get("naming_convention") == "aiag_vda")

    lines = [
        f"\n\nNonparametric Capability Analysis of {var_name}",
        "Method: Distribution-Free (Empirical Percentiles)",
        "",
        "Process Information",
        f"  Sample Size (N):      {res.get('n_total', 0)}",
        f"  Lower Spec (LSL):     {_fmt(res.get('lsl'))}",
        f"  Upper Spec (USL):     {_fmt(res.get('usl'))}",
        f"  Target:               {_fmt(res.get('target'))}",
        "",
        "Empirical Percentiles",
        f"  0.135% (Lower):       {_fmt(res.get('p_lower'))}",
        f"  50.0%  (Median):      {_fmt(res.get('p_median'))}",
        f"  99.865% (Upper):      {_fmt(res.get('p_upper'))}",
        "",
    ]

    idx = res.get("indices", {})
    lines.append("Overall Capability")
    if is_vda:
        lines.append(f"  Cnp:                  {_fmt(idx.get('cnp', idx.get('pp')))}")
        lines.append(f"  Cnpl:                 {_fmt(idx.get('cnpl', idx.get('ppl')))}")
        lines.append(f"  Cnpu:                 {_fmt(idx.get('cnpu', idx.get('ppu')))}")
        lines.append(f"  Cnpk:                 {_fmt(idx.get('cnpk', idx.get('ppk')))}")
    else:
        lines.append(f"  Pp:                   {_fmt(idx.get('pp'))}")
        lines.append(f"  PPL:                  {_fmt(idx.get('ppl'))}")
        lines.append(f"  PPU:                  {_fmt(idx.get('ppu'))}")
        lines.append(f"  Ppk:                  {_fmt(idx.get('ppk'))}")
    lines.append("")

    obs = res.get("observed_ppm", {})
    lines.append("Observed Performance (PPM)")
    lines.append(f"  Observed < LSL:       {_fmt(obs.get('below'), 2)}")
    lines.append(f"  Observed > USL:       {_fmt(obs.get('above'), 2)}")
    lines.append(f"  Observed Total:       {_fmt(obs.get('total'), 2)}")
    lines.append("")

    z_bench = res.get("benchmark_z", {})
    if "z_bench" in z_bench:
        lines.append(f"Benchmark Z (Observed): {_fmt(z_bench.get('z_bench'), 2)}")
        lines.append("")

    return "\n".join(lines)


def format_automated_capability_report(entry: Dict[str, Any]) -> str:
    """Format session text report for Automated Capability Analysis (Distribution Tournament)."""
    res = entry.get("result", entry)
    var_name = res.get("variable_name", entry.get("variable_name", res.get("variable", "Measurement")))

    lines = [
        f"\n\nAutomated Capability Analysis of {var_name}",
        "",
        "Goodness-of-Fit Tournament Summary",
        "  Distribution / Model         AD Stat      p-value",
        "  --------------------------------------------------",
    ]

    tourney = res.get("tournament", [])
    for row in tourney:
        d_name = row.get("distribution", "")
        ad = row.get("ad_stat", 0.0)
        p_val = row.get("p_val", 0.0)
        lines.append(f"  {d_name:28s} {_fmt(ad,3):>8}     {_fmt(p_val,3):>8}")
    lines.append("")

    best = res.get("best_fit", {})
    lines.append(f"Selected Best Fit Model: {best.get('distribution', 'Weibull')}")
    lines.append("")

    # Include nonnormal report section
    from .capability_nonnormal_report import format_nonnormal_capability_report
    lines.append(format_nonnormal_capability_report(entry))
    lines.extend(str(message) for message in res.get("warnings", []))
    return "\n".join(lines)
