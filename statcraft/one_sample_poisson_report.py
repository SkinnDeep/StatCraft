"""Session output formatting for One-Sample Poisson Rate (StatCraft style)."""
from typing import Dict, Any, List


def format_one_sample_poisson_report(entry_or_result: Any) -> str:
    """Format one-sample Poisson rate results matching StatCraft session output."""
    data = entry_or_result
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    elif hasattr(data, "result"):
        data = data.result

    samples = data.get("samples", [])
    if not samples and "n" in data:
        samples = [data]

    lines: List[str] = []
    for s_idx, res in enumerate(samples):
        if s_idx > 0:
            lines.append("")
            lines.append("-" * 60)
            lines.append("")

        sample_name = res.get("sample_name", "Sample")
        n = res["n"]
        total_occurrences = res["total_occurrences"]
        total_exposure = res["total_exposure"]
        sample_rate = res["sample_rate"]
        length = res.get("length_of_observation", 1.0)
        conf = res["confidence_level"]
        conf_str = f"{conf:g}% CI for Rate"
        alt = res["alternative"]
        method = res["method"]
        ci_lower = res["ci_lower"]
        ci_upper = res["ci_upper"]

        if ci_lower is not None and ci_upper is not None:
            ci_text = f"({ci_lower:.6f}, {ci_upper:.6f})"
        elif ci_lower is not None:
            ci_text = f"({ci_lower:.6f}, ∞)"
        elif ci_upper is not None:
            ci_text = f"(-∞, {ci_upper:.6f})"
        else:
            ci_text = "*"

        lines.append(f"Test and CI for One-Sample Poisson Rate: {sample_name}")
        lines.append("")
        lines.append("Descriptive Statistics")
        hdr = f"{'N':>6}  {'Total Occurrences':>17}  {'Total Exposure':>14}  {'Sample Rate':>11}  {conf_str}"
        lines.append(hdr)
        row = f"{n:6d}  {total_occurrences:17d}  {total_exposure:14g}  {sample_rate:11.6f}  {ci_text}"
        lines.append(row)

        if length != 1.0:
            lines.append(f"Length of observation = {length:g}")

        hypothesized_rate = res.get("hypothesized_rate")
        if hypothesized_rate is not None:
            lines.append("")
            lines.append("Test")
            lines.append(f"  Null hypothesis         H₀: rate = {hypothesized_rate:g}")
            if alt == "less":
                lines.append(f"  Alternative hypothesis  H₁: rate < {hypothesized_rate:g}")
            elif alt == "greater":
                lines.append(f"  Alternative hypothesis  H₁: rate > {hypothesized_rate:g}")
            else:
                lines.append(f"  Alternative hypothesis  H₁: rate ≠ {hypothesized_rate:g}")
            lines.append("")

            p_val = res.get("p_value")
            p_str = f"{p_val:.3f}" if p_val is not None else "*"
            if method == "normal_approx":
                z_val = res.get("z_value")
                z_str = f"{z_val:.2f}" if z_val is not None else "*"
                lines.append(f"  {'Method':<20}  {'Z-Value':>7}  {'P-Value':>7}")
                lines.append(f"  {'Normal approximation':<20}  {z_str:>7}  {p_str:>7}")
            else:
                lines.append(f"  {'Method':<6}  {'P-Value':>7}")
                lines.append(f"  {'Exact':<6}  {p_str:>7}")

    return "\n".join(lines)
