"""Formatted session report for One-Sample Variance test."""


def format_one_variance_report(result):
    lines = []
    name = result.get("name", "Sample")
    is_var = result.get("is_variance_test", False)
    null_sd = result.get("null_stdev", 1.0)
    null_var = result.get("null_variance", 1.0)
    conf = result.get("confidence_level", 95.0)
    alt = result.get("alternative", "not_equal")
    has_raw = result.get("has_raw_data", False)
    perform_test = result.get("perform_test", True)

    lines.append(f"Test and CI for One Variance: {name}")
    lines.append("")

    # Method
    lines.append("Method")
    target_sym = "σ²" if is_var else "σ"
    null_val = null_var if is_var else null_sd

    if alt == "less":
        alt_sym = "<"
    elif alt == "greater":
        alt_sym = ">"
    else:
        alt_sym = "≠"

    if perform_test:
        lines.append(f"Null hypothesis         H₀: {target_sym} = {null_val:g}")
        lines.append(f"Alternative hypothesis  H₁: {target_sym} {alt_sym} {null_val:g}")
    else:
        lines.append(f"Confidence level        {conf:g}%")

    lines.append("")
    if has_raw:
        lines.append("The Bonett method is valid for any continuous distribution.")
        lines.append("The Chi-Square method is valid only for the normal distribution.")
        lines.append("")

    # Descriptive Statistics
    lines.append("Descriptive Statistics")
    n = result.get("n", 0)
    sd = result.get("stdev", 0.0)
    var = result.get("variance", 0.0)

    chi2_info = result.get("chi2", {})
    bonett_info = result.get("bonett")

    ci_key = "ci_variance" if is_var else "ci_stdev"
    c_chi = chi2_info.get(ci_key, (0.0, 0.0))

    def _ci_str(ci):
        if ci is None:
            return ""
        low, high = ci
        l_str = f"{low:.3f}" if low > -1e10 else "-∞"
        h_str = f"{high:.3f}" if high < 1e10 else "∞"
        return f"({l_str}, {h_str})"

    if has_raw and bonett_info:
        c_bon = bonett_info.get(ci_key, (0.0, 0.0))
        lines.append(f"{'':26}{conf:g}% CI for {target_sym}   {conf:g}% CI for {target_sym}")
        lines.append(f"{'Variable':<10}{'N':>6}{'StDev':>10}{'Variance':>12}   {'Bonett':<16} {'Chi-Square':<16}")
        lines.append(f"{name:<10}{n:>6}{sd:>10.3f}{var:>12.3f}   {_ci_str(c_bon):<16} {_ci_str(c_chi):<16}")
    else:
        lines.append(f"{'':28}{conf:g}% CI for {target_sym}")
        lines.append(f"{'Variable':<10}{'N':>6}{'StDev':>10}{'Variance':>12}   {'Chi-Square':<16}")
        lines.append(f"{name:<10}{n:>6}{sd:>10.3f}{var:>12.3f}   {_ci_str(c_chi):<16}")

    lines.append("")

    # Test section
    if perform_test:
        lines.append("Test")
        if has_raw and bonett_info and bonett_info.get("p_value") is not None:
            lines.append(f"{'Test':<14}")
            lines.append(f"{'Method':<14}{'Statistic':>10}{'DF':>6}{'P-Value':>10}")
            b_stat = bonett_info.get("statistic", 0.0)
            b_df = bonett_info.get("df", 1)
            b_p = bonett_info.get("p_value", 1.0)
            lines.append(f"{'Bonett':<14}{b_stat:>10.2f}{b_df:>6}{b_p:>10.3f}")

            c_stat = chi2_info.get("statistic", 0.0)
            c_df = chi2_info.get("df", 0)
            c_p = chi2_info.get("p_value", 1.0)
            lines.append(f"{'Chi-Square':<14}{c_stat:>10.2f}{c_df:>6}{c_p:>10.3f}")
        else:
            lines.append(f"{'Test':<14}")
            lines.append(f"{'Method':<14}{'Statistic':>10}{'DF':>6}{'P-Value':>10}")
            c_stat = chi2_info.get("statistic", 0.0)
            c_df = chi2_info.get("df", 0)
            c_p = chi2_info.get("p_value", 1.0)
            lines.append(f"{'Chi-Square':<14}{c_stat:>10.2f}{c_df:>6}{c_p:>10.3f}")

    return "\n".join(lines)
