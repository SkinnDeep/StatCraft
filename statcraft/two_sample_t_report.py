"""Report formatting for native StatCraft Two-Sample t."""
from __future__ import annotations
from typing import Any, Dict


def format_two_sample_t_report(entry: Dict[str, Any]) -> str:
    res = entry.get("result", {})
    if not res:
        return entry.get("report", "")

    s1 = res["sample1"]
    s2 = res["sample2"]
    title = entry.get("title", f"Two-Sample T-Test and CI: {s1['name']}, {s2['name']}")
    created = entry.get("created_at", "")

    lines = []
    lines.append(title)
    if created:
        lines.append(created)
    lines.append("─" * 76)
    lines.append("")
    lines.append(title)
    lines.append("")

    # Method
    lines.append("Method")
    lines.append(f"  μ₁: mean of {s1['name']}")
    lines.append(f"  μ₂: mean of {s2['name']}")
    lines.append("  Difference: μ₁ - μ₂")
    if res.get("assume_equal_variances"):
        lines.append("  Equal variances are assumed for this analysis.")
    else:
        lines.append("  Equal variances are not assumed for this analysis.")
    lines.append("")

    # Descriptive Statistics
    lines.append("Descriptive Statistics")
    lines.append(f"  {'Sample':<16} {'N':>6} {'Mean':>10} {'StDev':>10} {'SE Mean':>10}")
    lines.append(f"  {s1['name']:<16} {s1['n']:>6} {s1['mean']:>10.4f} {s1['stdev']:>10.4f} {s1['se_mean']:>10.4f}")
    lines.append(f"  {s2['name']:<16} {s2['n']:>6} {s2['mean']:>10.4f} {s2['stdev']:>10.4f} {s2['se_mean']:>10.4f}")
    lines.append("")

    # Estimation for Difference
    conf = res.get("confidence_level", 95.0)
    conf_str = f"{conf:g}% CI for"
    lines.append("Estimation for Difference")
    lines.append(f"  {'Difference':>10}   {conf_str:<18}")

    diff = res.get("difference", 0.0)
    ci_low = res.get("ci_lower")
    ci_up = res.get("ci_upper")
    alt = res.get("alternative", "not_equal")

    if alt == "less_than":
        ci_text = f"(-∞, {ci_up:.4f})"
    elif alt == "greater_than":
        ci_text = f"({ci_low:.4f}, ∞)"
    else:
        ci_text = f"({ci_low:.4f}, {ci_up:.4f})"

    lines.append(f"  {diff:>10.4f}   {ci_text:<18}")
    if res.get("assume_equal_variances") and res.get("pooled_stdev") is not None:
        lines.append(f"  Pooled StDev = {res['pooled_stdev']:.4f}")
    lines.append("")

    # Test
    hyp_diff = res.get("hypothesized_difference", 0.0)
    lines.append("Test")
    lines.append(f"  Null hypothesis         H0: μ₁ - μ₂ = {hyp_diff:g}")
    if alt == "less_than":
        alt_sym = "<"
    elif alt == "greater_than":
        alt_sym = ">"
    else:
        alt_sym = "≠"
    lines.append(f"  Alternative hypothesis  H1: μ₁ - μ₂ {alt_sym} {hyp_diff:g}")

    t_val = res.get("t_statistic", 0.0)
    df = res.get("df", 0)
    p_val = res.get("p_value", 1.0)
    lines.append(f"  {'T-Value':>10} {'DF':>6} {'P-Value':>10}")
    lines.append(f"  {t_val:>10.2f} {df:>6} {p_val:>10.3f}")

    return "\n".join(lines)
