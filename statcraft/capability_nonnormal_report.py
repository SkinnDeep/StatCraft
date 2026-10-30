"""Session report formatting for Nonnormal Capability Analysis."""

from __future__ import annotations
from typing import Any, Dict


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_nonnormal_capability_report(entry: Dict[str, Any]) -> str:
    """Format full session text report matching StatCraft."""
    res = entry.get("result", entry)
    var_name = entry.get("variable_name", entry.get("title", "Measurement"))
    method = res.get("method", "weibull")
    is_vda = (res.get("naming_convention") == "aiag_vda")

    lines = [
        f"\n\nNonnormal Capability Analysis of {var_name}",
        f"Distribution/Transformation: {method.capitalize()}",
        "",
        "Process Information",
        f"  Sample Size:          {res.get('n_total', 0)}",
        f"  Lower Spec (LSL):     {_fmt(res.get('lsl'))}",
        f"  Upper Spec (USL):     {_fmt(res.get('usl'))}",
        f"  Target:               {_fmt(res.get('target'))}",
        "",
    ]

    fit = res.get("fit_info", {})
    if "parameters" in fit:
        lines.append("Distribution Parameters")
        for k, v in fit["parameters"].items():
            lines.append(f"  {k.capitalize()}: {v:.5f}")
        if "ad_stat" in fit:
            lines.append(f"  Anderson-Darling (AD): {fit['ad_stat']:.3f}")
        lines.append("")
    elif "lambda" in fit:
        lines.append("Box-Cox Transformation")
        lines.append(f"  Estimated Lambda: {fit['lambda']:.4f}")
        lines.append("")

    lines.append("Process Percentiles")
    lines.append(f"  0.135% (Lower):       {_fmt(res.get('p_lower'))}")
    lines.append(f"  50.0%  (Median):      {_fmt(res.get('p_median'))}")
    lines.append(f"  99.865% (Upper):      {_fmt(res.get('p_upper'))}")
    lines.append("")

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

    exp = res.get("expected_ppm", {})
    obs = res.get("observed_ppm", {})
    lines.append("Parts Per Million (PPM)")
    lines.append(f"  Expected Below LSL:   {_fmt(exp.get('below'), 2)}")
    lines.append(f"  Expected Above USL:   {_fmt(exp.get('above'), 2)}")
    lines.append(f"  Expected Total:       {_fmt(exp.get('total'), 2)}")
    lines.append(f"  Observed Below LSL:   {_fmt(obs.get('below'), 2)}")
    lines.append(f"  Observed Above USL:   {_fmt(obs.get('above'), 2)}")
    lines.append(f"  Observed Total:       {_fmt(obs.get('total'), 2)}")
    lines.append("")

    z_bench = res.get("benchmark_z", {})
    lines.append("Benchmark Z Statistics")
    lines.append(f"  Z.Bench:              {_fmt(z_bench.get('z_bench'), 2)}")
    if z_bench.get("z_lsl") is not None:
        lines.append(f"  Z.LSL:                {_fmt(z_bench.get('z_lsl'), 2)}")
    if z_bench.get("z_usl") is not None:
        lines.append(f"  Z.USL:                {_fmt(z_bench.get('z_usl'), 2)}")
    lines.append("")

    return "\n".join(lines)
