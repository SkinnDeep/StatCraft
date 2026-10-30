"""Formatted session report for Two-Sample Variances test."""


def format_two_variances_report(result):
    lines = []
    s1 = result.get("sample1", {})
    s2 = result.get("sample2", {})
    name1 = s1.get("name", "Sample 1")
    name2 = s2.get("name", "Sample 2")
    is_var = result.get("is_variance_ratio", False)
    null_ratio_sd = result.get("null_ratio_sd", 1.0)
    null_ratio_var = result.get("null_ratio_variance", 1.0)
    conf = result.get("confidence_level", 95.0)
    alt = result.get("alternative", "not_equal")
    has_raw = result.get("has_raw_data", False)
    use_normal = result.get("use_normal_distribution", True)

    lines.append(f"Test and CI for Two Variances: {name1}, {name2}")
    lines.append("")

    # Method
    lines.append("Method")
    target_str = "σ₁² / σ₂²" if is_var else "σ₁ / σ₂"
    ratio_type_str = "Ratio of Variances" if is_var else "Ratio of Standard Deviations"
    null_val = null_ratio_var if is_var else null_ratio_sd

    if alt == "less":
        alt_sym = "<"
    elif alt == "greater":
        alt_sym = ">"
    else:
        alt_sym = "≠"

    lines.append(f"Null hypothesis         H₀: {target_str} = {null_val:g}")
    lines.append(f"Alternative hypothesis  H₁: {target_str} {alt_sym} {null_val:g}")
    lines.append(f"Significance level      α = {1.0 - conf/100.0:g}")
    lines.append("")

    # Descriptive Statistics
    lines.append("Descriptive Statistics")
    lines.append(f"{'':34}{conf:g}% CI for σ")
    lines.append(f"{'Sample':<12}{'N':>6}{'StDev':>10}{'Variance':>12}   {'Chi-Square':<16}")

    def _ci_str(ci):
        if ci is None:
            return ""
        low, high = ci
        l_str = f"{low:.3f}" if low > -1e10 else "-∞"
        h_str = f"{high:.3f}" if high < 1e10 else "∞"
        return f"({l_str}, {h_str})"

    lines.append(f"{name1:<12}{s1.get('n', 0):>6}{s1.get('stdev', 0.0):>10.3f}{s1.get('variance', 0.0):>12.3f}   {_ci_str(s1.get('ci_stdev')):<16}")
    lines.append(f"{name2:<12}{s2.get('n', 0):>6}{s2.get('stdev', 0.0):>10.3f}{s2.get('variance', 0.0):>12.3f}   {_ci_str(s2.get('ci_stdev')):<16}")
    lines.append("")

    # Ratio
    lines.append(ratio_type_str)
    est_ratio = result.get("ratio_variance" if is_var else "ratio_sd", 1.0)
    lines.append(f"Estimated ratio: {est_ratio:.3f}")

    f_test = result.get("f_test", {})
    f_ci = f_test.get("ci_variance" if is_var else "ci_sd")
    lines.append(f"{conf:g}% CI for ratio using F: {_ci_str(f_ci)}")

    bonett_info = result.get("bonett")
    if has_raw and not use_normal and bonett_info:
        b_ci = bonett_info.get("ci_var" if is_var else "ci_sd")
        lines.append(f"{conf:g}% CI for ratio using Bonett: {_ci_str(b_ci)}")

    lines.append("")

    # Test
    lines.append("Test")
    if has_raw and not use_normal:
        lines.append(f"{'Method':<14}{'DF1':>6}{'DF2':>6}{'Statistic':>12}{'P-Value':>10}")
        if bonett_info:
            lines.append(f"{'Bonett':<14}{bonett_info.get('df', 1):>6}{'--':>6}{bonett_info.get('statistic', 0.0):>12.2f}{bonett_info.get('p_value', 1.0):>10.3f}")
        levene_info = result.get("levene")
        if levene_info:
            lines.append(f"{'Levene':<14}{levene_info.get('df1', 1):>6}{levene_info.get('df2', 0):>6}{levene_info.get('statistic', 0.0):>12.2f}{levene_info.get('p_value', 1.0):>10.3f}")
    else:
        lines.append(f"{'Method':<14}{'DF1':>6}{'DF2':>6}{'Statistic':>12}{'P-Value':>10}")
        lines.append(f"{'F Test':<14}{f_test.get('df1', 0):>6}{f_test.get('df2', 0):>6}{f_test.get('statistic', 0.0):>12.3f}{f_test.get('p_value', 1.0):>10.3f}")

    return "\n".join(lines)
