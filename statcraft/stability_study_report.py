"""Session window report generator for Stability Study (Shelf Life Estimation per ICH Q1E).

Formats output matching Minitab session window styling:
- Study Title and Setup
- Model Selection Outcome per ICH Q1E Decision Tree
- Analysis of Variance (ANCOVA) Poolability Tests
- Regression Equations by Batch
- Batch Parameters Table
- Shelf Life Estimation Table (Individual Batches and Overall Minimum)
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_stability_study_report(result: Dict[str, Any]) -> str:
    """Format Stability Study results into a Minitab session text report."""
    lines: List[str] = []
    lines.append(result.get("title", "Stability Study"))
    lines.append("")

    resp_name = result.get("response_name", "Response")
    time_name = result.get("time_name", "Time")
    batch_name = result.get("batch_name", "Batch")
    lines.append(f"Response: {resp_name}")
    lines.append(f"Time:     {time_name}")
    lines.append(f"Batch:    {batch_name}")
    lines.append(f"Number of Batches: {result.get('n_batches', 0)}")
    lines.append(f"Number of Observations: {result.get('n_obs', 0)}")

    lsl = result.get("lsl")
    usl = result.get("usl")
    if lsl is not None:
        lines.append(f"Lower Specification Limit (LSL): {lsl:g}")
    if usl is not None:
        lines.append(f"Upper Specification Limit (USL): {usl:g}")

    alpha_p = result.get("alpha_pool", 0.25)
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    lines.append(f"Significance level for pooling batches: {alpha_p:.2f}")
    lines.append(f"Confidence level for shelf life: {conf_pct}% (one-sided)")
    lines.append("")

    # Model Selection
    lines.append("Model Selection (ICH Q1E Decision Rule)")
    lines.append(f"Selected Model: {result.get('selected_model', '')}")
    lines.append("")

    # ANCOVA Poolability Tests
    lines.append("Analysis of Variance (Tests for Pooling Batches)")
    hdr_anc = f"{'Source':<28}  {'DF':>4}  {'Adj SS':>12}  {'Adj MS':>12}  {'F-Value':>8}  {'P-Value':>8}  {'Decision':<12}"
    lines.append(hdr_anc)
    lines.append("-" * len(hdr_anc))

    for t in result.get("ancova_tests", []):
        src = t.get("source", "")
        df = t.get("df", 0)
        ss = t.get("ss", 0.0)
        ms = t.get("ms", 0.0)
        f_val = t.get("f_value", 0.0)
        p_val = t.get("p_value", 0.0)
        dec = "Poolable" if t.get("poolable") else "Do Not Pool"
        lines.append(f"{src:<28}  {df:>4}  {ss:>12.4f}  {ms:>12.4f}  {f_val:>8.2f}  {p_val:>8.3f}  {dec:<12}")
    lines.append("")

    # Regression Equations
    lines.append("Regression Equations")
    for eq in result.get("equations", []):
        b_id = eq.get("batch", "")
        formula = eq.get("equation", "")
        lines.append(f"Batch {b_id}: {formula}")
    lines.append("")

    # Coefficients Table
    lines.append("Batch Parameter Estimates")
    hdr_coef = f"{'Batch':<12}  {'Intercept':>12}  {'SE Intercept':>12}  {'Slope':>12}  {'SE Slope':>12}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))

    for br in result.get("batch_results", []):
        b_id = str(br.get("batch", ""))
        b0 = br.get("intercept", 0.0)
        se0 = br.get("se_intercept", 0.0)
        b1 = br.get("slope", 0.0)
        se1 = br.get("se_slope", 0.0)
        lines.append(f"{b_id:<12}  {b0:>12.4f}  {se0:>12.4f}  {b1:>12.4f}  {se1:>12.4f}")
    lines.append("")

    # Shelf Life Table
    lines.append(f"Estimated Shelf Life ({conf_pct}% One-Sided Confidence)")
    hdr_shelf = f"{'Batch':<12}  {'Shelf Life':>16}  {'Units':<10}"
    lines.append(hdr_shelf)
    lines.append("-" * len(hdr_shelf))

    for br in result.get("batch_results", []):
        b_id = str(br.get("batch", ""))
        sl = br.get("shelf_life")
        sl_str = f"{sl:.2f}" if sl is not None else ">= Long term"
        lines.append(f"{b_id:<12}  {sl_str:>16}  {time_name:<10}")

    lines.append("-" * len(hdr_shelf))
    overall_sl = result.get("overall_shelf_life")
    overall_str = f"{overall_sl:.2f} {time_name}" if overall_sl is not None else ">= Long term"
    lines.append(f"Overall Product Shelf Life: {overall_str}")
    lines.append("")

    return "\n".join(lines)
