"""Report formatting for native StatCraft Paired t test."""
from __future__ import annotations
from typing import Any, Dict, List


def format_paired_t_report(entry: Dict[str, Any]) -> str:
    """Format Paired t test output matching StatCraft session layout."""
    res = entry.get("result", {})
    if not res:
        return "No Paired t results available."

    data_format = res.get("data_format", 1)
    s1_name = res.get("sample1_name", "Sample 1")
    s2_name = res.get("sample2_name", "Sample 2")
    conf_level = res.get("confidence_level", 95.0)
    conf_str = f"{int(conf_level) if conf_level.is_integer() else conf_level}%"
    hyp_diff = res.get("hypothesized_difference", 0.0)
    alt = res.get("alternative", "not_equal")
    diffs = res.get("differences", {})

    header_title = f"Paired T-Test and CI: {s1_name}, {s2_name}" if data_format != 2 else "Paired T-Test and CI"

    lines: List[str] = [
        header_title,
        "─" * 76,
        "",
        header_title,
        "",
    ]

    # CI header label
    if alt == "greater_than":
        ci_hdr = f"{conf_str} Lower Bound for μ_difference"
    elif alt == "less_than":
        ci_hdr = f"{conf_str} Upper Bound for μ_difference"
    else:
        ci_hdr = f"{conf_str} CI for μ_difference"

    if data_format == 2:  # Summarized
        lines.append("Descriptive Statistics: Differences")
        lines.append(f"  {'N':>6} {'Mean':>10} {'StDev':>10} {'SE Mean':>10}")
        lines.append(f"  {diffs['n']:>6} {diffs['mean']:>10.4f} {diffs['sd']:>10.4f} {diffs['se_mean']:>10.4f}")
    else:  # Raw columns
        lines.append("Descriptive Statistics")
        lines.append(f"  {'Sample':<16} {'N':>6} {'Mean':>10} {'StDev':>10} {'SE Mean':>10}")
        s1 = res.get("sample1", {})
        s2 = res.get("sample2", {})
        lines.append(f"  {s1['name']:<16} {s1['n']:>6} {s1['mean']:>10.4f} {s1['sd']:>10.4f} {s1['se_mean']:>10.4f}")
        lines.append(f"  {s2['name']:<16} {s2['n']:>6} {s2['mean']:>10.4f} {s2['sd']:>10.4f} {s2['se_mean']:>10.4f}")

    lines.append("")
    lines.append("Estimation for Paired Difference")
    lines.append(f"  {'Mean':>10} {'StDev':>10} {'SE Mean':>10}   {ci_hdr}")

    ci_val = ""
    if alt == "greater_than":
        ci_val = f"{diffs['ci_lower']:10.4f}" if diffs.get("ci_lower") is not None else ""
    elif alt == "less_than":
        ci_val = f"{diffs['ci_upper']:10.4f}" if diffs.get("ci_upper") is not None else ""
    else:
        if diffs.get("ci_lower") is not None and diffs.get("ci_upper") is not None:
            ci_val = f"({diffs['ci_lower']:.4f}, {diffs['ci_upper']:.4f})"
    lines.append(f"  {diffs['mean']:>10.4f} {diffs['sd']:>10.4f} {diffs['se_mean']:>10.4f}   {ci_val}")

    lines.append("")
    if data_format == 2:
        lines.append("μ_difference: mean of differences")
    else:
        lines.append(f"μ_difference: mean of ({s1_name} - {s2_name})")

    lines.append("")
    lines.append("Test")
    hyp_formatted = f"{int(hyp_diff) if hyp_diff.is_integer() else hyp_diff}"
    lines.append(f"  Null hypothesis         H0: μ_difference = {hyp_formatted}")
    if alt == "less_than":
        lines.append(f"  Alternative hypothesis  H1: μ_difference < {hyp_formatted}")
    elif alt == "greater_than":
        lines.append(f"  Alternative hypothesis  H1: μ_difference > {hyp_formatted}")
    else:
        lines.append(f"  Alternative hypothesis  H1: μ_difference ≠ {hyp_formatted}")

    lines.append(f"   {'T-Value':>8}   {'DF':>6}   {'P-Value':>8}")
    t_val = res.get("t_statistic", 0.0)
    df_val = res.get("df", 0)
    p_val = res.get("p_value", 1.0)
    lines.append(f"   {t_val:>8.2f}   {df_val:>6}   {p_val:>8.3f}")

    return "\n".join(lines)
