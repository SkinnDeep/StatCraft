"""Formatted session text report for Process Capability Sixpack (Normal, Between/Within, Nonnormal)."""

from typing import Any, Dict


def format_sixpack_report(res: Dict[str, Any]) -> str:
    """Formats full StatCraft Process Capability Sixpack Report."""
    lines = []
    col_name = res.get("column_name", "Data")
    analysis = res.get("analysis", "capability_sixpack_normal")
    is_bw = (analysis == "capability_sixpack_between_within" or res.get("analysis_mode") == "between_within")
    is_nonnormal = (analysis == "capability_sixpack_nonnormal")

    if is_bw:
        sub_title = "(Between/Within)"
    elif is_nonnormal:
        sub_title = f"({res.get('distribution', 'Nonnormal').capitalize()})"
    else:
        sub_title = "(Normal Distribution)"

    lines.append(f"Process Capability Sixpack Report for {col_name} {sub_title}")
    lines.append("")

    # Process Data
    lines.append("Process Data")
    if res.get("lsl") is not None:
        lines.append(f"LSL           {res['lsl']:g}")
    if res.get("target") is not None:
        lines.append(f"Target        {res['target']:g}")
    if res.get("usl") is not None:
        lines.append(f"USL           {res['usl']:g}")
    lines.append(f"Sample Mean   {res['mean']:.5g}")
    lines.append(f"Sample N      {res['sample_n']}")
    lines.append(f"Subgroups     {res.get('subgroup_count', 0)}")
    lines.append(f"Subgroup Size {res.get('subgroup_avg_size', 1):.4g}")

    if not is_nonnormal:
        if res.get("sigma_within") is not None:
            lines.append(f"StDev(Within) {res['sigma_within']:.5g}")
        if is_bw and res.get("stdev_between_within") is not None:
            lines.append(f"StDev(B/W)    {res['stdev_between_within']:.5g}")
    if res.get("sigma_overall") is not None:
        lines.append(f"StDev(Overall){res['sigma_overall']:.5g}")
    lines.append("")

    # Control Chart Evaluation
    lines.append("Control Chart Diagnostics")
    px = res.get("panel_xbar", {})
    pd = res.get("panel_disp", {})
    x_fails = px.get("test1_failures", [])
    d_fails = pd.get("test1_failures", [])

    lines.append(f"{px.get('title', 'Xbar Chart')}: Center={px.get('center', 0.0):.4f}, UCL={px.get('ucl_val', 0.0):.4f}, LCL={px.get('lcl_val', 0.0):.4f}")
    if x_fails:
        lines.append(f"  * Test 1 (Beyond 3.00 sigma): Failed at subgroup(s) {', '.join(map(str, x_fails))}")
    else:
        lines.append("  * Test 1: No test failures observed.")

    lines.append(f"{pd.get('title', 'R Chart')}: Center={pd.get('center', 0.0):.4f}, UCL={pd.get('ucl_val', 0.0):.4f}, LCL={pd.get('lcl_val', 0.0):.4f}")
    if d_fails:
        lines.append(f"  * Test 1 (Beyond 3.00 sigma): Failed at subgroup(s) {', '.join(map(str, d_fails))}")
    else:
        lines.append("  * Test 1: No test failures observed.")
    lines.append("")

    # Goodness-of-Fit / Normality Test
    pnorm = res.get("panel_norm", {})
    assessment_title = "Distribution Assessment" if is_nonnormal else "Normality Assessment"
    lines.append(assessment_title)
    ad_val = pnorm.get("ad_stat")
    p_val = pnorm.get("p_value")
    ad_str = f"{ad_val:.3f}" if ad_val is not None else "*"
    p_str = f"{p_val:.3f}" if p_val is not None else ("< 0.005" if ad_val and ad_val > 1.5 else "> 0.100")
    lines.append(f"Anderson-Darling Statistic: {ad_str}")
    lines.append(f"P-Value:                   {p_str}")
    lines.append("")

    psum = res.get("panel_summary", {})
    if not is_nonnormal:
        # Potential (Within) Capability
        within_label = "Between/Within Capability" if is_bw else "Potential (Within) Capability"
        lines.append(within_label)
        cp_val = psum.get("cp_bw") if is_bw and psum.get("cp_bw") is not None else psum.get("cp")
        cpk_val = psum.get("cpk_bw") if is_bw and psum.get("cpk_bw") is not None else psum.get("cpk")
        if cp_val is not None:
            lines.append(f"Cp            {cp_val:.2f}")
        if psum.get("cpl") is not None:
            lines.append(f"CPL           {psum['cpl']:.2f}")
        if psum.get("cpu") is not None:
            lines.append(f"CPU           {psum['cpu']:.2f}")
        if cpk_val is not None:
            lines.append(f"Cpk           {cpk_val:.2f}")
        if psum.get("ccpk") is not None:
            lines.append(f"CCpk          {psum['ccpk']:.2f}")
        if psum.get("cpm") is not None:
            lines.append(f"Cpm           {psum['cpm']:.2f}")
        lines.append("")

    # Overall Capability
    lines.append("Overall Capability")
    if psum.get("pp") is not None:
        lines.append(f"Pp            {psum['pp']:.2f}")
    if psum.get("ppl") is not None:
        lines.append(f"PPL           {psum['ppl']:.2f}")
    if psum.get("ppu") is not None:
        lines.append(f"PPU           {psum['ppu']:.2f}")
    if psum.get("ppk") is not None:
        lines.append(f"Ppk           {psum['ppk']:.2f}")
    if psum.get("z_bench") is not None:
        lines.append(f"Z.Bench       {psum['z_bench']:.2f}")
    lines.append("")

    # Performance
    lines.append("Performance (parts per million)")
    lines.append(f"Observed PPM:           {psum.get('ppm_observed', 0.0):.2f}")
    if not is_nonnormal:
        lines.append(f"Expected Within PPM:    {psum.get('ppm_exp_within', 0.0):.2f}")
        lines.append(f"Expected Overall PPM:   {psum.get('ppm_exp_overall', 0.0):.2f}")
    else:
        lines.append(f"Expected PPM:           {psum.get('ppm_expected', 0.0):.2f}")

    return "\n".join(lines)
