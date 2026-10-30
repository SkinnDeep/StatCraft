"""Report formatting for native StatCraft One-Sample Proportion test."""
from __future__ import annotations
from typing import Any, Dict, List


def format_one_sample_proportion_report(entry: Dict[str, Any]) -> str:
    """Format One-Sample Proportion test output matching StatCraft session layout."""
    res = entry.get("result", {})
    samples: List[Dict[str, Any]] = res.get("samples", [])
    if not samples:
        return "No One-Sample Proportion results available."

    conf_level = res.get("confidence_level", 95.0)
    conf_str = f"{int(conf_level) if conf_level.is_integer() else conf_level}%"
    perform_test = res.get("perform_test", True)
    hyp_p = res.get("hypothesized_proportion", 0.5)
    alt = res.get("alternative", "not_equal")
    method = res.get("method", "exact")

    multi = len(samples) > 1
    sample_names = ", ".join(s["name"] for s in samples)
    header_title = f"Test and CI for One Proportion: {sample_names}" if res.get("data_format") != 2 else "Test and CI for One Proportion"

    lines: List[str] = [
        header_title,
        "─" * 76,
        "",
        header_title,
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

    lines.append(f"  {'Sample':<16} {'N':>6} {'Event':>8} {'Sample p':>12}   {ci_hdr}")
    for s in samples:
        ci_val = ""
        if alt == "greater_than":
            ci_val = f"{s['ci_lower']:10.6f}" if s["ci_lower"] is not None else ""
        elif alt == "less_than":
            ci_val = f"{s['ci_upper']:10.6f}" if s["ci_upper"] is not None else ""
        else:
            lo = f"{s['ci_lower']:10.6f}" if s["ci_lower"] is not None else "*"
            hi = f"{s['ci_upper']:10.6f}" if s["ci_upper"] is not None else "*"
            ci_val = f"({lo.strip()}, {hi.strip()})"

        lines.append(f"  {s['name']:<16} {s['n']:>6} {s['events']:>8} {s['sample_p']:>12.6f}   {ci_val}")

    if perform_test:
        lines.append("")
        lines.append("Test")
        hyp_formatted = f"{hyp_p}"

        if alt == "less_than":
            alt_op = "<"
        elif alt == "greater_than":
            alt_op = ">"
        else:
            alt_op = "≠"

        lines.append(f"  Null hypothesis         H0: p = {hyp_formatted}")
        lines.append(f"  Alternative hypothesis  H1: p {alt_op} {hyp_formatted}")
        lines.append(f"  Method                 {'Normal approximation' if method == 'normal' else 'Exact'}")

        if method == "normal":
            if multi:
                lines.append(f"  {'Sample':<16} {'Z-Value':>10} {'P-Value':>10}")
                for s in samples:
                    z_str = f"{s['z_statistic']:10.2f}" if s["z_statistic"] is not None else "*"
                    p_str = f"{s['p_value']:10.3f}" if s["p_value"] is not None else "*"
                    lines.append(f"  {s['name']:<16} {z_str} {p_str}")
            else:
                s0 = samples[0]
                lines.append(f"  Z-Value                {s0['z_statistic']:.2f}" if s0["z_statistic"] is not None else "  Z-Value                *")
                lines.append(f"  P-Value                {s0['p_value']:.3f}" if s0["p_value"] is not None else "  P-Value                *")
        else:
            if multi:
                lines.append(f"  {'Sample':<16} {'P-Value':>10}")
                for s in samples:
                    p_str = f"{s['p_value']:10.3f}" if s["p_value"] is not None else "*"
                    lines.append(f"  {s['name']:<16} {p_str}")
            else:
                s0 = samples[0]
                lines.append(f"  P-Value                {s0['p_value']:.3f}" if s0["p_value"] is not None else "  P-Value                *")

    return "\n".join(lines)
