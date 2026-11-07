"""Report generator for Johnson Transformation (Stat > Quality Tools > Johnson Transformation).

Generates Minitab 22-standard plain text reports.
"""

from __future__ import annotations

from typing import Any, Dict, List


def generate_johnson_report(result: Dict[str, Any]) -> str:
    """Format Minitab 22-standard text session report for Johnson Transformation."""
    var_name = result.get("variable_name", "Variable")
    n = result.get("n_samples", 0)
    p_crit = result.get("p_threshold", 0.10)
    family = result.get("family", "")
    fn = result.get("function", "")
    passed = result.get("passed", False)
    target_store = result.get("store_column_name", "")

    orig = result.get("original", {})
    trans = result.get("transformed", {})

    lines: List[str] = []
    lines.append(f"Johnson Transformation for {var_name}")
    lines.append(f"Sample Size (N) = {n}")
    lines.append("")
    lines.append("Transformation Function")
    lines.append(f"System: {family}")
    lines.append(f"{fn}")
    lines.append(f"P-Value to select best fit: {p_crit:.2f} (Status: {'Accepted' if passed else 'Rejected'})")
    lines.append("")
    lines.append("Goodness of Fit Test (Normality)")
    lines.append("")
    lines.append(f"{'Data':<20} {'AD':>8} {'P':>10}")
    lines.append("-" * 40)

    orig_ad = orig.get("ad", 0.0)
    orig_p = orig.get("p_value", 0.0)
    orig_p_str = "<0.001" if orig_p < 0.001 else f"{orig_p:.3f}"
    lines.append(f"{'Original Data':<20} {orig_ad:>8.3f} {orig_p_str:>10}")

    trans_ad = trans.get("ad", 0.0)
    trans_p = trans.get("p_value", 0.0)
    trans_p_str = "<0.001" if trans_p < 0.001 else f"{trans_p:.3f}"
    lines.append(f"{'Transformed Data':<20} {trans_ad:>8.3f} {trans_p_str:>10}")

    lines.append("")
    if target_store:
        lines.append(f"Transformed data stored in column: {target_store}")
    return "\n".join(lines)
