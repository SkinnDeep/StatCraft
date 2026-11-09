"""Session window report generator for Regression with Life Data (Accelerated Failure Time / Parametric Survival).

Formats output matching Minitab session window styling:
- Censoring Information Summary
- Regression Table (Term, Coef, SE Coef, Z, P-Value, 95% CI)
- Distribution Parameters Table (Scale, Shape, SE, 95% CI)
- Log-Likelihood and Model Fit
- Table of Percentiles at Mean Predictor Values
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_life_regression_report(result: Dict[str, Any]) -> str:
    """Format Regression with Life Data results into a Minitab session text report."""
    lines: List[str] = []
    lines.append(result.get("title", "Regression with Life Data"))
    lines.append("")

    dist = result.get("distribution", "Weibull")
    lines.append(f"Assumed distribution: {dist}")
    lines.append("")

    # Censoring Summary
    lines.append("Censoring Information")
    lines.append(f"  Uncensored observations:    {result.get('n_failures', 0)}")
    lines.append(f"  Right censored observations:{result.get('n_censored', 0)}")
    lines.append(f"  Total observations:         {result.get('n_obs', 0)}")
    lines.append("")

    # Coefficients Table
    conf_pct = int(round(result.get("confidence", 0.95) * 100))
    lines.append("Regression Table")
    hdr_coef = f"{'Term':<16}  {'Coef':>10}  {'SE Coef':>10}  {'Z':>8}  {'P-Value':>8}  {f'{conf_pct}% CI':^22}"
    lines.append(hdr_coef)
    lines.append("-" * len(hdr_coef))

    for c in result.get("coefficients", []):
        t = c.get("term", "")
        b = c.get("coef", 0.0)
        se = c.get("se_coef", 0.0)
        z = c.get("z_value", 0.0)
        p = c.get("p_value", 0.0)
        ci_l = c.get("ci_lower", 0.0)
        ci_u = c.get("ci_upper", 0.0)
        ci_str = f"({ci_l:.4f}, {ci_u:.4f})"
        lines.append(f"{t:<16}  {b:>10.4f}  {se:>10.4f}  {z:>8.2f}  {p:>8.3f}  {ci_str:^22}")
    lines.append("")

    # Distribution Parameters
    p_info = result.get("parameters", {})
    scale = p_info.get("scale", 1.0)
    se_scale = p_info.get("se_scale", 0.0)
    ci_scale = p_info.get("ci_scale", (scale, scale))

    lines.append("Distribution Parameters")
    hdr_param = f"{'Parameter':<16}  {'Estimate':>10}  {'SE':>10}  {f'{conf_pct}% CI':^22}"
    lines.append(hdr_param)
    lines.append("-" * len(hdr_param))
    ci_s_str = f"({ci_scale[0]:.4f}, {ci_scale[1]:.4f})"
    lines.append(f"{'Scale (sigma)':<16}  {scale:>10.4f}  {se_scale:>10.4f}  {ci_s_str:^22}")

    shape = p_info.get("shape")
    if shape is not None:
        se_shape = p_info.get("se_shape", 0.0)
        ci_shape = p_info.get("ci_shape", (shape, shape))
        ci_sh_str = f"({ci_shape[0]:.4f}, {ci_shape[1]:.4f})"
        lines.append(f"{'Shape (Weibull)':<16}  {shape:>10.4f}  {se_shape:>10.4f}  {ci_sh_str:^22}")
    lines.append("")

    lines.append(f"Log-Likelihood = {result.get('log_likelihood', 0.0):.3f}")
    lines.append("")

    # Table of Percentiles
    lines.append(f"Table of Percentiles (at Mean Values of Predictors)")
    hdr_pct = f"{'Percent':>8}  {'Estimate':>12}  {'SE':>10}  {f'{conf_pct}% CI':^24}"
    lines.append(hdr_pct)
    lines.append("-" * len(hdr_pct))

    for pt in result.get("percentiles", []):
        pct = pt.get("percent", 0.0)
        est = pt.get("estimate", 0.0)
        se = pt.get("se", 0.0)
        ci_l = pt.get("ci_lower", 0.0)
        ci_u = pt.get("ci_upper", 0.0)
        ci_str = f"({ci_l:.4f}, {ci_u:.4f})"
        lines.append(f"{pct:>7.1f}%  {est:>12.4f}  {se:>10.4f}  {ci_str:^24}")
    lines.append("")

    return "\n".join(lines)
