"""Session window report generator for Distribution Analysis (Arbitrary Censoring).

Formats output matching Minitab session window styling:
- Title and Distribution
- Summary of Current Observations (Exact, Left, Right, Interval, Total)
- Estimation Method and Log-Likelihood
- Table of Parameter Estimates with SE and CI
- Table of Percentiles (1, 5, 10, 50, 90, 95, 99) with SE and CI
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_reliability_arbitrary_report(result: Dict[str, Any]) -> str:
    """Format Arbitrary Censoring Reliability results into a Minitab session text report."""
    lines: List[str] = []
    title = result.get("title", "Distribution Analysis (Arbitrary Censoring)")
    lines.append(title)
    lines.append("")

    # Summary of Current Observations
    lines.append("Summary of Current Observations")
    counts = result.get("counts", {})
    lines.append(f"{'Exact failures':<26} {counts.get('exact', 0):>8}")
    lines.append(f"{'Left censored':<26} {counts.get('left', 0):>8}")
    lines.append(f"{'Right censored':<26} {counts.get('right', 0):>8}")
    lines.append(f"{'Interval censored':<26} {counts.get('interval', 0):>8}")
    lines.append(f"{'Total':<26} {counts.get('total', 0):>8}")
    lines.append("")

    lines.append("Estimation Method: Maximum Likelihood")
    lines.append(f"Log-Likelihood = {result.get('log_likelihood', 0.0):.2f}")
    lines.append("")

    # Table of Parameter Estimates
    lines.append("Table of Parameter Estimates")
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    hdr_param = f"{'Parameter':<16}  {'Estimate':>12}  {'SE Coef':>12}  {f'{conf_pct}% Normal CI':^24}"
    lines.append(hdr_param)
    lines.append("-" * len(hdr_param))

    for p in result.get("parameters", []):
        pname = p.get("parameter", "")
        est = p.get("estimate", 0.0)
        se = p.get("se", 0.0)
        ci_l = p.get("ci_lower", 0.0)
        ci_u = p.get("ci_upper", 0.0)
        ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
        lines.append(f"{pname:<16}  {est:>12.4f}  {se:>12.4f}  {ci_str:^24}")
    lines.append("")

    # Table of Percentiles
    lines.append("Table of Percentiles")
    hdr_pct = f"{'Percent':<10}  {'Percentile':>14}  {'SE Coef':>12}  {f'{conf_pct}% Normal CI':^24}"
    lines.append(hdr_pct)
    lines.append("-" * len(hdr_pct))

    for row in result.get("percentiles", []):
        pct = row.get("percent", 0)
        q_est = row.get("percentile", 0.0)
        se = row.get("se", 0.0)
        ci_l = row.get("ci_lower", 0.0)
        ci_u = row.get("ci_upper", 0.0)
        ci_str = f"({ci_l:>.4f}, {ci_u:>.4f})"
        lines.append(f"{pct:<10}  {q_est:>14.4f}  {se:>12.4f}  {ci_str:^24}")

    return "\n".join(lines)
