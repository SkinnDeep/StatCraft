"""Report formatting for native StatCraft One-Sample Z test."""
from __future__ import annotations
from typing import Any, Dict, List


def format_one_sample_z_report(entry: Dict[str, Any]) -> str:
    """Format One-Sample Z test output matching StatCraft session layout."""
    res = entry.get("result", {})
    samples: List[Dict[str, Any]] = res.get("samples", [])
    if not samples:
        return "No One-Sample Z results available."

    sigma = res.get("sigma", 1.0)
    conf_level = res.get("confidence_level", 95.0)
    conf_str = f"{int(conf_level) if conf_level.is_integer() else conf_level}%"
    perform_test = res.get("perform_test", True)
    hyp_mean = res.get("hypothesized_mean", 0.0)
    alt = res.get("alternative", "not_equal")

    multi = len(samples) > 1
    sample_names = ", ".join(s["name"] for s in samples)
    header_title = f"One-Sample Z: {sample_names}" if res.get("data_format") != 2 else "One-Sample Z"
    sigma_formatted = f"{int(sigma) if sigma.is_integer() else sigma}"

    lines: List[str] = [
        header_title,
        "─" * 76,
        "",
        header_title,
        "",
        f"Known standard deviation = {sigma_formatted}",
        "",
        "Descriptive Statistics",
    ]

    # CI header label
    if alt == "greater_than":
        ci_hdr = f"{conf_str} Lower Bound"
    elif alt == "less_than":
        ci_hdr = f"{conf_str} Upper Bound"
    else:
        ci_hdr = f"{conf_str} CI"

    if multi:
        lines.append(f"  {'Sample':<16} {'N':>6} {'Mean':>10} {'SE Mean':>10}   {ci_hdr}")
        for s in samples:
            ci_val = ""
            if alt == "greater_than":
                ci_val = f"{s['ci_lower']:10.4f}" if s["ci_lower"] is not None else ""
            elif alt == "less_than":
                ci_val = f"{s['ci_upper']:10.4f}" if s["ci_upper"] is not None else ""
            else:
                if s["ci_lower"] is not None and s["ci_upper"] is not None:
                    ci_val = f"({s['ci_lower']:.4f}, {s['ci_upper']:.4f})"
            lines.append(
                f"  {s['name']:<16} {s['n']:>6} {s['mean']:>10.4f} {s['se_mean']:>10.4f}   {ci_val}"
            )
    else:
        s = samples[0]
        lines.append(f"  {'N':>6} {'Mean':>10} {'SE Mean':>10}   {ci_hdr}")
        ci_val = ""
        if alt == "greater_than":
            ci_val = f"{s['ci_lower']:10.4f}" if s["ci_lower"] is not None else ""
        elif alt == "less_than":
            ci_val = f"{s['ci_upper']:10.4f}" if s["ci_upper"] is not None else ""
        else:
            if s["ci_lower"] is not None and s["ci_upper"] is not None:
                ci_val = f"({s['ci_lower']:.4f}, {s['ci_upper']:.4f})"
        lines.append(
            f"  {s['n']:>6} {s['mean']:>10.4f} {s['se_mean']:>10.4f}   {ci_val}"
        )

    lines.append("")
    if multi:
        lines.append("μ: mean of each sample")
    elif res.get("data_format") == 2:
        lines.append("μ: mean of sample")
    else:
        lines.append(f"μ: mean of {samples[0]['name']}")

    if perform_test:
        lines.append("")
        lines.append("Test")
        hyp_formatted = f"{int(hyp_mean) if hyp_mean.is_integer() else hyp_mean}"
        lines.append(f"  Null hypothesis         H0: μ = {hyp_formatted}")
        if alt == "less_than":
            lines.append(f"  Alternative hypothesis  H1: μ < {hyp_formatted}")
        elif alt == "greater_than":
            lines.append(f"  Alternative hypothesis  H1: μ > {hyp_formatted}")
        else:
            lines.append(f"  Alternative hypothesis  H1: μ ≠ {hyp_formatted}")

        if multi:
            lines.append(f"  {'Sample':<16} {'Z-Value':>10} {'P-Value':>10}")
            for s in samples:
                z_str = f"{s['z_statistic']:.2f}" if s["z_statistic"] is not None else ""
                p_str = f"{s['p_value']:.3f}" if s["p_value"] is not None else ""
                lines.append(f"  {s['name']:<16} {z_str:>10} {p_str:>10}")
        else:
            s = samples[0]
            lines.append(f"   {'Z-Value':>8}   {'P-Value':>8}")
            z_str = f"{s['z_statistic']:.2f}" if s["z_statistic"] is not None else ""
            p_str = f"{s['p_value']:.3f}" if s["p_value"] is not None else ""
            lines.append(f"   {z_str:>8}   {p_str:>8}")

    return "\n".join(lines)
