"""StatCraft session window report formatting for Power and Sample Size."""

from typing import Any, Dict


def format_one_sample_z_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 1-Sample Z Power and Sample Size report."""
    sigma = result["sigma"]
    alpha = result["alpha"]
    alt = result["alternative"]

    lines = [
        "Power and Sample Size",
        "1-Sample Z Test",
        "",
        "Testing mean = null (versus not = null)" if alt == "Two-sided" else "Testing mean = null (versus > or < null)",
        f"Calculating power for mean = null + difference",
        f"  Assumed standard deviation = {sigma:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Difference':>12}{'Sample Size':>14}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 58,
    ]
    for r in result["rows"]:
        diff = r["difference"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {diff:>12.4f}{n:>14}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    return "\n".join(lines)


def format_one_sample_t_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 1-Sample t Power and Sample Size report."""
    sigma = result["sigma"]
    alpha = result["alpha"]
    alt = result["alternative"]

    lines = [
        "Power and Sample Size",
        "1-Sample t Test",
        "",
        "Testing mean = null (versus not = null)" if alt == "Two-sided" else "Testing mean = null (versus > or < null)",
        f"Calculating power for mean = null + difference",
        f"  Assumed standard deviation = {sigma:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Difference':>12}{'Sample Size':>14}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 58,
    ]
    for r in result["rows"]:
        diff = r["difference"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {diff:>12.4f}{n:>14}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    return "\n".join(lines)


def format_two_sample_t_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 2-Sample t Power and Sample Size report."""
    sigma = result["sigma"]
    alpha = result["alpha"]
    alt = result["alternative"]

    lines = [
        "Power and Sample Size",
        "2-Sample t Test",
        "",
        "Testing mean 1 = mean 2 (versus not =)" if alt == "Two-sided" else "Testing mean 1 = mean 2 (versus > or <)",
        f"Calculating power for mean 1 = mean 2 + difference",
        f"  Assumed standard deviation = {sigma:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Difference':>12}{'Sample Size':>14}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 58,
    ]
    for r in result["rows"]:
        diff = r["difference"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {diff:>12.4f}{n:>14}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    lines.append("The sample size is for each group.")
    lines.append("")
    return "\n".join(lines)


def format_paired_t_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Paired t Power and Sample Size report."""
    stdev = result.get("stdev_diff", result.get("sigma", 1.0))
    alpha = result["alpha"]
    alt = result["alternative"]

    lines = [
        "Power and Sample Size",
        "Paired t Test",
        "",
        "Testing mean paired difference = 0 (versus not = 0)" if alt == "Two-sided" else "Testing mean paired difference = 0 (versus > or < 0)",
        f"Calculating power for mean paired difference",
        f"  Assumed standard deviation of paired differences = {stdev:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Difference':>12}{'Number of Pairs':>18}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 62,
    ]
    for r in result["rows"]:
        diff = r["difference"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {diff:>12.4f}{n:>18}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    return "\n".join(lines)


def format_one_proportion_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 1 Proportion Power and Sample Size report."""
    p0 = result["baseline_p0"]
    alpha = result["alpha"]
    alt = result["alternative"]

    lines = [
        "Power and Sample Size",
        "1 Proportion Test",
        "",
        f"Testing proportion = {p0:.4f} (versus not = {p0:.4f})" if alt == "Two-sided" else f"Testing proportion = {p0:.4f} (versus > or < {p0:.4f})",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Comparison p':>14}{'Sample Size':>14}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 60,
    ]
    for r in result["rows"]:
        comp_p = r["comparison_p"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {comp_p:>14.4f}{n:>14}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    return "\n".join(lines)


def format_two_proportions_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 2 Proportions Power and Sample Size report."""
    p2 = result["p2"]
    alpha = result["alpha"]
    alt = result["alternative"]

    lines = [
        "Power and Sample Size",
        "2 Proportions Test",
        "",
        f"Testing proportion 1 = proportion 2 (versus not =)" if alt == "Two-sided" else "Testing proportion 1 = proportion 2 (versus > or <)",
        f"  Comparison proportion 2 = {p2:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Proportion 1':>14}{'Sample Size':>14}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 60,
    ]
    for r in result["rows"]:
        p1 = r["p1"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {p1:>14.4f}{n:>14}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    lines.append("The sample size is for each group.")
    lines.append("")
    return "\n".join(lines)


def format_oneway_anova_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft One-Way ANOVA Power and Sample Size report."""
    levels = result["levels"]
    sigma = result["sigma"]
    alpha = result["alpha"]

    lines = [
        "Power and Sample Size",
        "One-Way ANOVA",
        "",
        f"  Number of levels = {levels}",
        f"  Assumed standard deviation = {sigma:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Max Difference':>16}{'Sample Size':>14}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 62,
    ]
    for r in result["rows"]:
        max_d = r["max_difference"]
        n = r["sample_size"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {max_d:>16.4f}{n:>14}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    lines.append("The sample size is for each group.")
    lines.append("")
    return "\n".join(lines)


def format_factorial_power_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft 2-Level Factorial Power and Sample Size report."""
    factors = result["factors"]
    corners = result["corner_points"]
    centers = result["center_points"]
    sigma = result["sigma"]
    alpha = result["alpha"]

    lines = [
        "Power and Sample Size",
        "2-Level Factorial Design",
        "",
        f"  Number of factors = {factors}",
        f"  Number of corner points = {corners}",
        f"  Number of center points = {centers}",
        f"  Assumed standard deviation = {sigma:.4f}",
        f"  Significance level = {alpha:.4f}",
        "",
        "Results",
        f"  {'Effect':>12}{'Replicates':>12}{'Total Runs':>12}{'Target Power':>14}{'Actual Power':>14}",
        "-" * 68,
    ]
    for r in result["rows"]:
        eff = r["effect"]
        reps = r["replicates"]
        tot = r["total_runs"]
        tp_str = f"{r['target_power']:.4f}" if r["target_power"] is not None else "--"
        act_p = r["actual_power"]
        lines.append(f"  {eff:>12.4f}{reps:>12}{tot:>12}{tp_str:>14}{act_p:>14.4f}")
    lines.append("")
    return "\n".join(lines)
