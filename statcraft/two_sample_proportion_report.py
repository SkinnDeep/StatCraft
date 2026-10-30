"""Report formatting for native StatCraft Two-Sample Proportion test."""
from __future__ import annotations
from typing import Any, Dict, List


def format_two_sample_proportion_report(entry: Dict[str, Any]) -> str:
    """Format Two-Sample Proportion test output matching StatCraft session layout."""
    res = entry.get("result", {})
    s1 = res.get("sample1", {})
    s2 = res.get("sample2", {})
    if not s1 or not s2:
        return "No Two-Sample Proportion results available."

    conf_level = res.get("confidence_level", 95.0)
    conf_str = f"{int(conf_level) if conf_level.is_integer() else conf_level}%"
    hyp_diff = res.get("hypothesized_difference", 0.0)
    alt = res.get("alternative", "not_equal")
    diff = res.get("difference", 0.0)

    header_title = "Test and CI for Two Proportions"

    lines: List[str] = [
        header_title,
        "─" * 76,
        "",
        header_title,
        "",
        "Descriptive Statistics",
        f"  {'Sample':<16} {'N':>6} {'Event':>8} {'Sample p':>12}",
        f"  {s1['name']:<16} {s1['n']:>6} {s1['events']:>8} {s1['sample_p']:>12.6f}",
        f"  {s2['name']:<16} {s2['n']:>6} {s2['events']:>8} {s2['sample_p']:>12.6f}",
        "",
        "Estimation for Difference",
    ]

    # CI header label
    if alt == "greater_than":
        ci_hdr = f"{conf_str} Lower Bound for Difference"
        ci_val = f"{res['ci_lower']:10.6f}" if res.get("ci_lower") is not None else "*"
    elif alt == "less_than":
        ci_hdr = f"{conf_str} Upper Bound for Difference"
        ci_val = f"{res['ci_upper']:10.6f}" if res.get("ci_upper") is not None else "*"
    else:
        ci_hdr = f"{conf_str} CI for Difference"
        lo = f"{res['ci_lower']:10.6f}" if res.get("ci_lower") is not None else "*"
        hi = f"{res['ci_upper']:10.6f}" if res.get("ci_upper") is not None else "*"
        ci_val = f"({lo.strip()}, {hi.strip()})"

    lines.append(f"  {'Difference':>12}       {ci_hdr}")
    lines.append(f"  {diff:12.6f}       {ci_val}")
    lines.append("  CI based on normal approximation")

    lines.append("")
    lines.append("Test")

    if alt == "less_than":
        alt_op = "<"
    elif alt == "greater_than":
        alt_op = ">"
    else:
        alt_op = "≠"

    lines.append(f"  Null hypothesis         H0: p1 - p2 = {hyp_diff}")
    lines.append(f"  Alternative hypothesis  H1: p1 - p2 {alt_op} {hyp_diff}")
    lines.append(f"  {'Method':<24} {'Z-Value':>10} {'P-Value':>10}")

    z_val = f"{res['z_statistic']:10.2f}" if res.get("z_statistic") is not None else "         *"
    p_val = f"{res['p_value']:10.3f}" if res.get("p_value") is not None else "         *"
    lines.append(f"  {'Normal approximation':<24} {z_val} {p_val}")

    if res.get("fisher_p_value") is not None:
        fisher_p = f"{res['fisher_p_value']:10.3f}"
        lines.append(f"  {'Fisher\'s exact':<24} {'':>10} {fisher_p}")

    return "\n".join(lines)
