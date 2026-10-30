"""Session output formatting for Two-Sample Poisson Rate (StatCraft style)."""
from typing import Dict, Any, List


def format_two_sample_poisson_report(entry_or_result: Any) -> str:
    """Format two-sample Poisson rate results matching StatCraft session output."""
    data = entry_or_result
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    elif hasattr(data, "result"):
        data = data.result

    res = data.get("result", data)
    s1 = res.get("sample1", {})
    s2 = res.get("sample2", {})

    diff = res.get("difference", 0.0)
    conf = res.get("confidence_level", 95.0)
    conf_str = f"{conf:g}% CI for Difference"
    ci_lower = res.get("ci_lower")
    ci_upper = res.get("ci_upper")
    alt = res.get("alternative", "not_equal")
    hypo_diff = res.get("hypothesized_difference", 0.0)
    z_val = res.get("z_value")
    p_val = res.get("p_value")
    p_exact = res.get("p_value_exact")
    length = res.get("length_of_observation", 1.0)

    if ci_lower is not None and ci_upper is not None:
        ci_text = f"({ci_lower:.6f}, {ci_upper:.6f})"
    elif ci_lower is not None:
        ci_text = f"({ci_lower:.6f}, ∞)"
    elif ci_upper is not None:
        ci_text = f"(-∞, {ci_upper:.6f})"
    else:
        ci_text = "*"

    lines: List[str] = [
        "Test and CI for Two-Sample Poisson Rates",
        "",
        "Descriptive Statistics",
        f"  {'Sample':<10}  {'N':>6}  {'Total Occurrences':>17}  {'Total Exposure':>14}  {'Sample Rate':>11}",
        f"  {s1.get('name', 'Sample 1'):<10}  {s1.get('n', 0):6d}  {s1.get('total_occurrences', 0):17d}  {s1.get('total_exposure', 0.0):14g}  {s1.get('sample_rate', 0.0):11.6f}",
        f"  {s2.get('name', 'Sample 2'):<10}  {s2.get('n', 0):6d}  {s2.get('total_occurrences', 0):17d}  {s2.get('total_exposure', 0.0):14g}  {s2.get('sample_rate', 0.0):11.6f}",
        "",
        "Estimation for Difference",
        f"  {'Difference':>10}  {conf_str:>26}",
        f"  {diff:10.6f}  {ci_text:>26}",
        "  CI based on normal approximation",
    ]

    if length != 1.0:
        lines.append(f"  Length of observation = {length:g}")

    lines.append("")
    lines.append("Test")
    diff_sym = "=" if hypo_diff == 0 else f"= {hypo_diff:g}"
    lines.append(f"  Null hypothesis         H₀: rate 1 - rate 2 {diff_sym}")
    if alt == "less":
        lines.append(f"  Alternative hypothesis  H₁: rate 1 - rate 2 < {hypo_diff:g}")
    elif alt == "greater":
        lines.append(f"  Alternative hypothesis  H₁: rate 1 - rate 2 > {hypo_diff:g}")
    else:
        lines.append(f"  Alternative hypothesis  H₁: rate 1 - rate 2 ≠ {hypo_diff:g}")
    lines.append("")

    z_str = f"{z_val:.2f}" if z_val is not None else "*"
    p_str = f"{p_val:.3f}" if p_val is not None else "*"

    lines.append(f"  {'Method':<20}  {'Z-Value':>7}  {'P-Value':>7}")
    lines.append(f"  {'Normal approximation':<20}  {z_str:>7}  {p_str:>7}")
    if p_exact is not None:
        lines.append(f"  {'Exact':<20}  {'':>7}  {p_exact:7.3f}")

    return "\n".join(lines)
