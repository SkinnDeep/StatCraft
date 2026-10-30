"""StatCraft Test for Equal Variances session output report generator."""


def format_equal_variances_report(entry):
    """Format textual session output matching StatCraft for Test for Equal Variances."""
    res = entry.get("result", {})
    cfg = res.get("options", {})
    results_opt = cfg.get("results", {})
    show_method = results_opt.get("method", True)
    show_ci = results_opt.get("confidence_intervals", True)
    show_tests = results_opt.get("tests", True)
    conf = res.get("confidence_level", 95.0)
    ind_conf = res.get("individual_confidence_level", 95.0)
    use_normal = res.get("use_normal_distribution", False)

    lines = []
    lines.append("Test for Equal Variances: " + str(res.get("response_name", "Response")))
    if res.get("factor_names"):
        lines[-1] += " versus " + ", ".join(res.get("factor_names"))
    lines.append("")

    if show_method:
        lines.append("Method")
        lines.append("  Null hypothesis         All variances are equal")
        lines.append("  Alternative hypothesis  At least one variance is different")
        lines.append(f"  Significance level      \u03b1 = {1.0 - conf / 100.0:g}")
        if use_normal:
            lines.append("  Bartlett's test is valid only for normal data.")
        else:
            lines.append("  Tests are valid for any continuous distribution.")
        lines.append("")

    groups = res.get("groups", [])
    if show_ci and groups:
        ci_label = "95% Bonferroni Confidence Intervals for Standard Deviations" if abs(conf - 95.0) < 1e-4 else f"{conf:g}% Bonferroni Confidence Intervals for Standard Deviations"
        lines.append(ci_label)
        lines.append(f"  {'Sample':<16} {'N':>5} {'StDev':>10} {'CI':>24}")
        for g in groups:
            lvl = str(g["level"])
            n_str = str(g["count"])
            sd_str = f"{g['stdev']:.4f}"
            ci_str = f"({g['bonf_lower']:.4f}, {g['bonf_upper']:.4f})"
            lines.append(f"  {lvl:<16} {n_str:>5} {sd_str:>10} {ci_str:>24}")
        lines.append(f"  Individual confidence level = {ind_conf:.4f}%")
        lines.append("")

    tests = res.get("tests", [])
    if show_tests and tests:
        lines.append("Tests")
        lines.append(f"  {'Method':<24} {'DF1':>5} {'DF2':>5} {'Test Statistic':>16} {'P-Value':>10}")
        for t in tests:
            m_name = t["method"]
            df1_str = str(t["df1"]) if t["df1"] is not None else ""
            df2_str = str(t["df2"]) if t["df2"] is not None else ""
            stat_str = f"{t['test_statistic']:.2f}" if t.get("test_statistic") is not None else ""
            p_val = t.get("p_value")
            p_str = f"{p_val:.3f}" if p_val is not None else ""
            lines.append(f"  {m_name:<24} {df1_str:>5} {df2_str:>5} {stat_str:>16} {p_str:>10}")
        lines.append("")

    if res.get("missing_rows"):
        m_count = len(res["missing_rows"])
        lines.append(f"* NOTE * {m_count} rows contained missing values and were omitted.")

    return "\n".join(lines).rstrip() + "\n"
