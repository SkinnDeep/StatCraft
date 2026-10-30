"""Formatted session text report for Process Capability Analysis (Normal Distribution)."""

from typing import Any, Dict


def format_capability_report(res: Dict[str, Any]) -> str:
    """Formats full StatCraft Process Capability Report."""
    lines = []
    is_bw = (res.get("analysis_mode") == "between_within")
    default_title = (
        f"Between/Within Capability Report for {res.get('variable_name', 'Data')}"
        if is_bw
        else f"Process Capability Report for {res.get('variable_name', 'Data')}"
    )
    title = res.get("title", default_title)
    lines.append(title)
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
    if is_bw:
        lines.append(f"StDev(Between/Within) {res.get('stdev_between_within', 0.0):.5g}")
        lines.append(f"StDev(Between)        {res.get('stdev_between', 0.0):.5g}")
        lines.append(f"StDev(Within)         {res['stdev_within']:.5g}")
    else:
        lines.append(f"StDev(Within) {res['stdev_within']:.5g}")
    lines.append(f"StDev(Overall){res['stdev_overall']:.5g}")
    lines.append("")

    stats_type = res.get("stats_type", "capability")
    include_ci = res.get("include_ci", False)
    conf_level = res.get("confidence_level", 95.0)

    def _ci_str(ci_tuple):
        if not ci_tuple or ci_tuple[0] is None and ci_tuple[1] is None:
            return ""
        low, high = ci_tuple
        l_str = f"{low:.2f}" if low is not None else "*"
        h_str = f"{high:.2f}" if high is not None else "*"
        return f"({l_str}, {h_str})"

    if stats_type == "zbench":
        # Benchmark Z's
        lines.append("Benchmark Z's")
        lines.append(f"{'':12} {'Within':>10} {'Overall':>10}")
        w_perf = res.get("within_perf", {})
        o_perf = res.get("overall_perf", {})
        if res.get("lsl") is not None:
            zw = f"{w_perf.get('z_lsl', 0.0):.2f}" if w_perf.get("z_lsl") is not None else "*"
            zo = f"{o_perf.get('z_lsl', 0.0):.2f}" if o_perf.get("z_lsl") is not None else "*"
            lines.append(f"{'Z.LSL':12} {zw:>10} {zo:>10}")
        if res.get("usl") is not None:
            zw = f"{w_perf.get('z_usl', 0.0):.2f}" if w_perf.get("z_usl") is not None else "*"
            zo = f"{o_perf.get('z_usl', 0.0):.2f}" if o_perf.get("z_usl") is not None else "*"
            lines.append(f"{'Z.USL':12} {zw:>10} {zo:>10}")
        zw_b = f"{w_perf.get('z_bench', 0.0):.2f}" if w_perf.get("z_bench") is not None else "*"
        zo_b = f"{o_perf.get('z_bench', 0.0):.2f}" if o_perf.get("z_bench") is not None else "*"
        lines.append(f"{'Z.Bench':12} {zw_b:>10} {zo_b:>10}")
        lines.append("")
    else:
        # Potential Capability / Machine Capability / Between-Within
        is_machine = (res.get("study_type") == "machine")
        is_aiag_vda = (res.get("naming_convention") == "aiag_vda")

        if is_machine:
            pot_title = "Machine Capability"
            p_name, pl_name, pu_name, pk_name = "Cm", "CmL", "CmU", "Cmk"
        elif is_bw and is_aiag_vda:
            pot_title = "Between/Within Capability (AIAG/VDA)"
            p_name, pl_name, pu_name, pk_name = "Cbw", "CbwL", "CbwU", "Cbwk"
        elif is_bw:
            pot_title = "Potential (Between/Within) Capability"
            p_name, pl_name, pu_name, pk_name = "Cp", "CPL", "CPU", "Cpk"
        else:
            pot_title = "Potential (Within) Capability"
            p_name, pl_name, pu_name, pk_name = "Cp", "CPL", "CPU", "Cpk"

        lines.append(pot_title)
        if include_ci:
            ci_header = f"{conf_level:g}% CI"
            lines.append(f"{'':8} {'':>8} {ci_header:>16}")
        if res.get("cp") is not None:
            val_str = f"{res['cp']:.2f}"
            ci_str = f"{_ci_str(res.get('ci_cp')):>16}" if include_ci else ""
            lines.append(f"{p_name:8} {val_str:>8} {ci_str}")
        if res.get("cpl") is not None:
            lines.append(f"{pl_name:8} {res['cpl']:>8.2f}")
        if res.get("cpu") is not None:
            lines.append(f"{pu_name:8} {res['cpu']:>8.2f}")
        if res.get("cpk") is not None:
            val_str = f"{res['cpk']:.2f}"
            ci_str = f"{_ci_str(res.get('ci_cpk')):>16}" if include_ci else ""
            lines.append(f"{pk_name:8} {val_str:>8} {ci_str}")
        if res.get("ccpk") is not None:
            cc_name = "CCmk" if is_machine else "CCbwk" if (is_bw and is_aiag_vda) else "CCpk"
            lines.append(f"{cc_name:8} {res['ccpk']:>8.2f}")
        if res.get("cpm") is not None:
            lines.append(f"{'Cpm':8} {res['cpm']:>8.2f}")
        lines.append("")

        # Overall Capability
        lines.append("Overall Capability")
        if include_ci:
            ci_header = f"{conf_level:g}% CI"
            lines.append(f"{'':8} {'':>8} {ci_header:>16}")
        if res.get("pp") is not None:
            val_str = f"{res['pp']:.2f}"
            ci_str = f"{_ci_str(res.get('ci_pp')):>16}" if include_ci else ""
            lines.append(f"{'Pp':8} {val_str:>8} {ci_str}")
        if res.get("ppl") is not None:
            lines.append(f"{'PPL':8} {res['ppl']:>8.2f}")
        if res.get("ppu") is not None:
            lines.append(f"{'PPU':8} {res['ppu']:>8.2f}")
        if res.get("ppk") is not None:
            val_str = f"{res['ppk']:.2f}"
            ci_str = f"{_ci_str(res.get('ci_ppk')):>16}" if include_ci else ""
            lines.append(f"{'Ppk':8} {val_str:>8} {ci_str}")
        lines.append("")

    # Performance
    unit_label = "percent" if res.get("display_unit", "ppm").lower() == "percent" else "parts per million"
    unit_prefix = "%" if res.get("display_unit", "ppm").lower() == "percent" else "PPM"
    exp_col = "Exp. \"Between/Within\"" if is_bw else "Exp. \"Within\""
    lines.append(f"Performance ({unit_label})")
    lines.append(f"{'':15} {'Observed':>12} {exp_col:>20} {'Exp. \"Overall\"':>15}")

    obs = res.get("observed_perf", {})
    w_perf = res.get("within_perf", {})
    o_perf = res.get("overall_perf", {})

    if res.get("lsl") is not None:
        lines.append(
            f"{unit_prefix + ' < LSL':15} "
            f"{obs.get('below', 0.0):12.2f} "
            f"{w_perf.get('expected_below', 0.0):15.2f} "
            f"{o_perf.get('expected_below', 0.0):15.2f}"
        )
    if res.get("usl") is not None:
        lines.append(
            f"{unit_prefix + ' > USL':15} "
            f"{obs.get('above', 0.0):12.2f} "
            f"{w_perf.get('expected_above', 0.0):15.2f} "
            f"{o_perf.get('expected_above', 0.0):15.2f}"
        )
    lines.append(
        f"{unit_prefix + ' Total':15} "
        f"{obs.get('total', 0.0):12.2f} "
        f"{w_perf.get('expected_total', 0.0):15.2f} "
        f"{o_perf.get('expected_total', 0.0):15.2f}"
    )

    return "\n".join(lines)
