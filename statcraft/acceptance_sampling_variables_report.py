"""Session report formatter for Acceptance Sampling by Variables.

Matches Minitab standard layout:
- Sampling plan parameters: Sample Size n, Critical distance k
- Specification limits (LSL, USL) and Standard Deviation (known sigma or sample s)
- Accept / Reject decision criteria
- Risk table at AQL and RQL
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "*"
    return f"{val:.{dec}f}"


def generate_acceptance_sampling_variables_report(result: Dict[str, Any]) -> str:
    """Format Acceptance Sampling by Variables results into Minitab session report."""
    lines: List[str] = []
    title = "Acceptance Sampling by Variables"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    n = result.get("n", 0)
    k = result.get("k", 0.0)
    aql = result.get("aql", 0.0)
    rql = result.get("rql", 0.0)
    alpha = result.get("actual_alpha", 0.0)
    beta = result.get("actual_beta", 0.0)
    lsl = result.get("lsl")
    usl = result.get("usl")
    spec_type = result.get("spec_type", "lower")
    sigma_known = result.get("sigma_known", False)
    sigma = result.get("sigma")
    lot_size = result.get("lot_size")
    aoql = result.get("aoql", 0.0)

    sd_str = f"Known (sigma = {_fmt(sigma, 4)})" if sigma_known else "Unknown (sample s)"
    lines.append(f"Standard Deviation: {sd_str}")
    if spec_type == "double":
        lines.append(f"Specification Limits: Lower (LSL) = {_fmt(lsl, 4)}, Upper (USL) = {_fmt(usl, 4)}")
    elif spec_type == "lower":
        lines.append(f"Specification Limit: Lower (LSL) = {_fmt(lsl, 4)}")
    else:
        lines.append(f"Specification Limit: Upper (USL) = {_fmt(usl, 4)}")

    if lot_size is not None:
        lines.append(f"Lot Size: {lot_size}")
    lines.append("")

    lines.append("Generated Sampling Plan:")
    lines.append(f"  Sample Size (n):        {n}")
    lines.append(f"  Critical Distance (k):   {_fmt(k, 4)}")
    lines.append("")

    # Accept / Reject rule
    lines.append("Acceptance Criteria:")
    s_label = "sigma" if sigma_known else "s"
    if spec_type == "lower":
        lines.append(f"  Accept lot if (Mean - LSL) / {s_label} >= {_fmt(k, 4)}; otherwise reject.")
    elif spec_type == "upper":
        lines.append(f"  Accept lot if (USL - Mean) / {s_label} >= {_fmt(k, 4)}; otherwise reject.")
    else:
        lines.append(f"  Accept lot if (Mean - LSL) / {s_label} >= {_fmt(k, 4)} AND (USL - Mean) / {s_label} >= {_fmt(k, 4)}; otherwise reject.")
    lines.append("")

    lines.append("Risk Analysis:")
    lines.append(f"  {'Quality Level':<24} {'Defective %':>12} {'Prob(Accept)':>14}")
    lines.append("  " + "-" * 52)
    lines.append(f"  {'AQL (Acceptable Quality)':<24} {aql * 100.0:>11.2f}% {1.0 - alpha:>14.4f}")
    lines.append(f"  {'RQL (Rejectable Quality)':<24} {rql * 100.0:>11.2f}% {beta:>14.4f}")
    lines.append("")
    lines.append(f"Average Outgoing Quality Limit (AOQL): {aoql * 100.0:.3f}%")
    lines.append("")

    return "\n" + "\n".join(lines)
