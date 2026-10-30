"""StatCraft session window report formatting for Equivalence Tests."""

import math
from typing import Any, Dict


def format_one_sample_equivalence_report(result: Dict[str, Any], var_name: str = "C1") -> str:
    """Format authentic StatCraft 1-Sample Equivalence Test report."""
    var_name = result.get("sample_name") or var_name
    is_ratio = result.get("hypothesis_type") == "ratio"
    target = result["target"]
    lo_m = result["lower_margin"]
    up_m = result["upper_margin"]
    alpha = result["alpha"]
    clevel = result["conf_level"]

    if is_ratio:
        scale_label = f"Ratio: Mean({var_name}) / Target"
        tost_h1 = f"Ratio <= {lo_m:.4f}"
        tost_h2 = f"Ratio >= {up_m:.4f}"
    else:
        scale_label = f"Difference: Mean({var_name}) - Target"
        tost_h1 = f"Difference <= {lo_m:.4f}"
        tost_h2 = f"Difference >= {up_m:.4f}"

    lines = [
        f"1-Sample Equivalence Test: {var_name}",
        "",
        "Method",
        f"  Target:                {target:.4f}",
        f"  Equivalence criteria:  {lo_m:.4f} to {up_m:.4f}",
        f"  Significance level:    {alpha:.3f}",
        "",
        "Descriptive Statistics",
        f"  {'Sample':15}{'N':>8}{'Mean':>12}{'StDev':>12}{'SE Mean':>12}",
        "-" * 59,
        f"  {var_name:15}{result['n']:>8}{result['mean']:>12.4f}{result['stdev']:>12.4f}{result['se_mean']:>12.4f}",
        "",
        f"{clevel:.1f}% Confidence Interval for {scale_label}",
        f"  {'Estimate':>12}{'Lower Limit':>14}{'Upper Limit':>14}",
        "-" * 40,
        f"  {result['point_estimate']:>12.4f}{result['ci_lower']:>14.4f}{result['ci_upper']:>14.4f}",
        "",
        "Two One-Sided Tests (TOST)",
        f"  {'Null Hypothesis':30}{'DF':>6}{'t-Value':>10}{'P-Value':>10}",
        "-" * 56,
        f"  {tost_h1:30}{result['df']:>6}{result['t1']:>10.3f}{result['p1']:>10.4f}",
        f"  {tost_h2:30}{result['df']:>6}{result['t2']:>10.3f}{result['p2']:>10.4f}",
        "",
    ]

    if result["is_equivalent"]:
        verdict = f"Equivalence can be claimed because the {clevel:.1f}% confidence interval is within the equivalence limits ({lo_m:.4f}, {up_m:.4f})."
    else:
        verdict = f"Equivalence cannot be claimed because the {clevel:.1f}% confidence interval extends outside the equivalence limits ({lo_m:.4f}, {up_m:.4f})."

    lines.append(verdict)
    lines.append("")
    return "\n".join(lines)


def format_two_sample_equivalence_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 2-Sample Equivalence Test report."""
    n1_str = result.get("name1", "Test")
    n2_str = result.get("name2", "Reference")
    is_ratio = result.get("hypothesis_type") == "ratio"
    lo_m = result["lower_margin"]
    up_m = result["upper_margin"]
    alpha = result["alpha"]
    clevel = result["conf_level"]

    if is_ratio:
        scale_label = f"Ratio: Mean({n1_str}) / Mean({n2_str})"
        tost_h1 = f"Ratio <= {lo_m:.4f}"
        tost_h2 = f"Ratio >= {up_m:.4f}"
    else:
        scale_label = f"Difference: Mean({n1_str}) - Mean({n2_str})"
        tost_h1 = f"Difference <= {lo_m:.4f}"
        tost_h2 = f"Difference >= {up_m:.4f}"

    lines = [
        f"2-Sample Equivalence Test: {n1_str}, {n2_str}",
        "",
        "Method",
        f"  Equivalence criteria:  {lo_m:.4f} to {up_m:.4f}",
        f"  Significance level:    {alpha:.3f}",
        f"  Equal variances:       {'Assumed' if result['equal_variances'] else 'Not assumed'}",
        "",
        "Descriptive Statistics",
        f"  {'Sample':15}{'N':>8}{'Mean':>12}{'StDev':>12}{'SE Mean':>12}",
        "-" * 59,
        f"  {n1_str:15}{result['n1']:>8}{result['mean1']:>12.4f}{result['stdev1']:>12.4f}{result['se_mean1']:>12.4f}",
        f"  {n2_str:15}{result['n2']:>8}{result['mean2']:>12.4f}{result['stdev2']:>12.4f}{result['se_mean2']:>12.4f}",
        "",
        f"{clevel:.1f}% Confidence Interval for {scale_label}",
        f"  {'Estimate':>12}{'Lower Limit':>14}{'Upper Limit':>14}",
        "-" * 40,
        f"  {result['point_estimate']:>12.4f}{result['ci_lower']:>14.4f}{result['ci_upper']:>14.4f}",
        "",
        "Two One-Sided Tests (TOST)",
        f"  {'Null Hypothesis':30}{'DF':>8}{'t-Value':>10}{'P-Value':>10}",
        "-" * 58,
        f"  {tost_h1:30}{result['df']:>8.1f}{result['t1']:>10.3f}{result['p1']:>10.4f}",
        f"  {tost_h2:30}{result['df']:>8.1f}{result['t2']:>10.3f}{result['p2']:>10.4f}",
        "",
    ]

    if result["is_equivalent"]:
        verdict = f"Equivalence can be claimed because the {clevel:.1f}% confidence interval is within the equivalence limits ({lo_m:.4f}, {up_m:.4f})."
    else:
        verdict = f"Equivalence cannot be claimed because the {clevel:.1f}% confidence interval extends outside the equivalence limits ({lo_m:.4f}, {up_m:.4f})."

    lines.append(verdict)
    lines.append("")
    return "\n".join(lines)


def format_paired_equivalence_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Paired Equivalence Test report."""
    n1_str = result.get("name1", "Test")
    n2_str = result.get("name2", "Reference")
    is_ratio = result.get("hypothesis_type") == "ratio"
    lo_m = result["lower_margin"]
    up_m = result["upper_margin"]
    alpha = result["alpha"]
    clevel = result["conf_level"]

    if is_ratio:
        scale_label = f"Ratio: Mean({n1_str}) / Mean({n2_str})"
        tost_h1 = f"Ratio <= {lo_m:.4f}"
        tost_h2 = f"Ratio >= {up_m:.4f}"
    else:
        scale_label = f"Difference: Mean({n1_str} - {n2_str})"
        tost_h1 = f"Difference <= {lo_m:.4f}"
        tost_h2 = f"Difference >= {up_m:.4f}"

    lines = [
        f"Paired Equivalence Test: {n1_str}, {n2_str}",
        "",
        "Method",
        f"  Equivalence criteria:  {lo_m:.4f} to {up_m:.4f}",
        f"  Significance level:    {alpha:.3f}",
        "",
        "Descriptive Statistics",
        f"  {'Sample':15}{'N':>8}{'Mean':>12}{'StDev':>12}{'SE Mean':>12}",
        "-" * 59,
        f"  {n1_str:15}{result['n']:>8}{result['mean1']:>12.4f}{result['stdev1']:>12.4f}{result['stdev1']/math.sqrt(result['n']):>12.4f}",
        f"  {n2_str:15}{result['n']:>8}{result['mean2']:>12.4f}{result['stdev2']:>12.4f}{result['stdev2']/math.sqrt(result['n']):>12.4f}",
        f"  {'Difference':15}{result['n']:>8}{result['mean_diff']:>12.4f}{result['stdev_diff']:>12.4f}{result['se_diff']:>12.4f}",
        "",
        f"{clevel:.1f}% Confidence Interval for {scale_label}",
        f"  {'Estimate':>12}{'Lower Limit':>14}{'Upper Limit':>14}",
        "-" * 40,
        f"  {result['point_estimate']:>12.4f}{result['ci_lower']:>14.4f}{result['ci_upper']:>14.4f}",
        "",
        "Two One-Sided Tests (TOST)",
        f"  {'Null Hypothesis':30}{'DF':>6}{'t-Value':>10}{'P-Value':>10}",
        "-" * 56,
        f"  {tost_h1:30}{result['df']:>6}{result['t1']:>10.3f}{result['p1']:>10.4f}",
        f"  {tost_h2:30}{result['df']:>6}{result['t2']:>10.3f}{result['p2']:>10.4f}",
        "",
    ]

    if result["is_equivalent"]:
        verdict = f"Equivalence can be claimed because the {clevel:.1f}% confidence interval is within the equivalence limits ({lo_m:.4f}, {up_m:.4f})."
    else:
        verdict = f"Equivalence cannot be claimed because the {clevel:.1f}% confidence interval extends outside the equivalence limits ({lo_m:.4f}, {up_m:.4f})."

    lines.append(verdict)
    lines.append("")
    return "\n".join(lines)


def format_crossover_equivalence_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 2x2 Crossover Equivalence Test report."""
    test_trt = result["test_treatment"]
    ref_trt = result["ref_treatment"]
    is_ratio = result.get("hypothesis_type") == "ratio"
    lo_m = result["lower_margin"]
    up_m = result["upper_margin"]
    alpha = result["alpha"]
    clevel = result["conf_level"]

    if is_ratio:
        scale_label = f"Ratio: Treatment({test_trt}) / Treatment({ref_trt})"
        tost_h1 = f"Ratio <= {lo_m:.4f}"
        tost_h2 = f"Ratio >= {up_m:.4f}"
    else:
        scale_label = f"Difference: Treatment({test_trt}) - Treatment({ref_trt})"
        tost_h1 = f"Difference <= {lo_m:.4f}"
        tost_h2 = f"Difference >= {up_m:.4f}"

    lines = [
        f"2x2 Crossover Equivalence Test: {test_trt} vs {ref_trt}",
        "",
        "Method",
        f"  Test Treatment:        {test_trt}",
        f"  Reference Treatment:   {ref_trt}",
        f"  Equivalence criteria:  {lo_m:.4f} to {up_m:.4f}",
        f"  Significance level:    {alpha:.3f}",
        f"  Total observations:    {result['n_obs']}",
        f"  Number of subjects:    {result['n_subjects']}",
        "",
        f"{clevel:.1f}% Confidence Interval for {scale_label}",
        f"  {'Estimate':>12}{'Lower Limit':>14}{'Upper Limit':>14}",
        "-" * 40,
        f"  {result['point_estimate']:>12.4f}{result['ci_lower']:>14.4f}{result['ci_upper']:>14.4f}",
        "",
        "Two One-Sided Tests (TOST)",
        f"  {'Null Hypothesis':30}{'DF':>6}{'t-Value':>10}{'P-Value':>10}",
        "-" * 56,
        f"  {tost_h1:30}{result['df']:>6}{result['t1']:>10.3f}{result['p1']:>10.4f}",
        f"  {tost_h2:30}{result['df']:>6}{result['t2']:>10.3f}{result['p2']:>10.4f}",
        "",
    ]

    if result["is_equivalent"]:
        verdict = f"Equivalence can be claimed because the {clevel:.1f}% confidence interval is within the equivalence limits ({lo_m:.4f}, {up_m:.4f})."
    else:
        verdict = f"Equivalence cannot be claimed because the {clevel:.1f}% confidence interval extends outside the equivalence limits ({lo_m:.4f}, {up_m:.4f})."

    lines.append(verdict)
    lines.append("")
    return "\n".join(lines)
