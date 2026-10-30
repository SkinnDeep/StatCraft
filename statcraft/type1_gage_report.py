"""Text session report formatter for Type 1 Gage Study."""


def generate_type1_gage_report(result, measurement_name="Measurement"):
    """Format Type 1 Gage Study results into Standard statistical text report."""
    lines = []
    title = result.get('title') or f"Type 1 Gage Study for {measurement_name}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Gage info section if any provided
    gage_info = result.get('gage_info', {})
    info_items = [
        ("Gage name", gage_info.get('gage_name')),
        ("Date of study", gage_info.get('date_of_study')),
        ("Reported by", gage_info.get('reported_by')),
        ("Miscellaneous", gage_info.get('misc')),
    ]
    has_info = any(v for _, v in info_items)
    if has_info:
        lines.append("Gage Information:")
        for label, val in info_items:
            if val:
                lines.append(f"  {label:<18}: {val}")
        lines.append("")

    lines.append(f"Reference:  {result['reference']:.6g}")
    tol_type = result.get('tolerance_type', 'tolerance')
    if tol_type == 'lower':
        lines.append(f"Lower Spec Limit (LSL): {result['lsl']:.6g}")
        lines.append(f"Tolerance (2 * (Ref - LSL)): {result['tolerance']:.6g}")
    elif tol_type == 'upper':
        lines.append(f"Upper Spec Limit (USL): {result['usl']:.6g}")
        lines.append(f"Tolerance (2 * (USL - Ref)): {result['tolerance']:.6g}")
    else:
        lines.append(f"Tolerance:  {result['tolerance']:.6g}")

    if result.get('resolution') is not None:
        res_str = f"{result['resolution']:.6g}"
        pct_res = result.get('pct_resolution')
        if pct_res is not None:
            res_str += f" ({pct_res:.2f}% of tolerance)"
        lines.append(f"Resolution: {res_str}")
    lines.append("")

    # Descriptive Statistics table
    lines.append("Descriptive Statistics")
    lines.append(f"  {'Sample Size (N)':<32} {result['n']}")
    lines.append(f"  {'Mean':<32} {result['mean']:.6g}")
    lines.append(f"  {'Standard Deviation (s)':<32} {result['std']:.6g}")
    mult = result.get('study_multiplier', 6.0)
    lines.append(f"  {f'{mult:g} * StDev ({mult:g}*s)':<32} {result['study_variation']:.6g}")
    lines.append(f"  {'Tolerance':<32} {result['tolerance']:.6g}")
    lines.append("")

    # Bias Test
    if result.get('perform_bias_test'):
        lines.append("Bias Test (H0: Bias = 0 vs H1: Bias != 0)")
        lines.append(f"  {'Bias':<32} {result['bias']:.6g}")
        lines.append(f"  {'Standard Error of Mean':<32} {result['se_mean']:.6g}")
        t_stat = result.get('t_stat')
        if t_stat is not None:
            lines.append(f"  {'T-Statistic':<32} {t_stat:.4f}")
            lines.append(f"  {'Degrees of Freedom (DF)':<32} {result['df']}")
            lines.append(f"  {'P-Value':<32} {result['p_value']:.4f}")
        else:
            lines.append(f"  {'T-Statistic':<32} *")
            lines.append(f"  {'P-Value':<32} *")
        lines.append("")

    # Capability section
    lines.append(f"Gage Capability ({result.get('cg_percent', 20.0):g}% of Tolerance)")
    cg = result.get('cg', 0.0)
    cgk = result.get('cgk', 0.0)
    lines.append(f"  {'Cg (Repeatability)':<32} {cg:.4f}")
    lines.append(f"  {'Cgk (Repeatability and Bias)':<32} {cgk:.4f}")
    lines.append(f"  {'%Var (Repeatability)':<32} {result['pct_var_repeatability']:.2f}%")
    lines.append(f"  {'%Var (Repeatability and Bias)':<32} {result['pct_var_rep_and_bias']:.2f}%")
    lines.append("")

    if cg >= 1.33:
        lines.append("Note: Cg >= 1.33 indicates acceptable repeatability capability.")
    else:
        lines.append("Note: Cg < 1.33 indicates gage variation is wider than allowable tolerance.")

    if cgk >= 1.33:
        lines.append("Note: Cgk >= 1.33 indicates acceptable overall capability (repeatability + centering).")
    else:
        lines.append("Note: Cgk < 1.33 indicates gage repeatability or bias requires improvement.")

    return "\n".join(lines)
