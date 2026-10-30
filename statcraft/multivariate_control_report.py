"""Report generator for Multivariate Control Charts (T-Squared, Generalized Variance, MEWMA).

Generates plain-text session window reports matching StatCraft output formatting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None:
        return "*"
    return f"{val:.{dec}f}"


def generate_multivariate_report(result: Dict[str, Any]) -> str:
    """Generate session text report for T-Squared, GenVar, or MEWMA chart."""
    chart_type = str(result.get("chart_type", "TSQUARED")).upper()
    var_names = result.get("variable_names", [])
    vars_str = ", ".join(var_names) if var_names else "Variables"
    lines: List[str] = []

    if chart_type == "TSQUARED":
        title = f"T² Control Chart of {vars_str}"
    elif chart_type == "GENVAR":
        title = f"Generalized Variance Chart of {vars_str}"
    elif chart_type == "MEWMA":
        title = f"Multivariate EWMA Chart of {vars_str}"
    else:
        title = f"Multivariate Control Chart of {vars_str}"

    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Process Information
    lines.append("Process Information")
    lines.append("-" * 35)
    lines.append(f"  Variables:           {vars_str}")
    lines.append(f"  Number of Variables: {result.get('p_variables', len(var_names))}")
    lines.append(f"  Subgroups:           {result.get('k_subgroups', 0)}")

    sizes = result.get("subgroup_sizes", [])
    if sizes:
        if len(set(sizes)) == 1:
            lines.append(f"  Subgroup Size:       {sizes[0]}")
        else:
            lines.append(f"  Subgroup Size:       Variable (Avg: {sum(sizes)/len(sizes):.1f})")

    if chart_type == "TSQUARED":
        lines.append(f"  Alpha (Significance):{_fmt(result.get('alpha'), 4)}")
        lines.append(f"  Center Line (CL):    {_fmt(result.get('center_line'), 2)}")
        lines.append(f"  UCL:                 {_fmt(result.get('ucl_val'), 4)}")
    elif chart_type == "GENVAR":
        lines.append(f"  Center Line (|S|):   {_fmt(result.get('center_line'), 6)}")
        lines.append(f"  UCL:                 {_fmt(result.get('ucl_val'), 6)}")
        lines.append(f"  LCL:                 {_fmt(result.get('lcl_val'), 6)}")
        if "b1" in result:
            lines.append(f"  Unbiasing b1:        {_fmt(result.get('b1'), 5)}")
            lines.append(f"  Unbiasing b2:        {_fmt(result.get('b2'), 5)}")
    elif chart_type == "MEWMA":
        lines.append(f"  Weight (r):          {_fmt(result.get('weight'), 4)}")
        lines.append(f"  Target ARL:          {_fmt(result.get('arl'), 1)}")
        lines.append(f"  Center Line (CL):    {_fmt(result.get('center_line'), 2)}")
        lines.append(f"  UCL (H):             {_fmt(result.get('ucl_val'), 4)}")

    omits = result.get("omit_subgroups", [])
    if omits:
        lines.append(f"  Omitted Subgroups:   {omits}")

    lines.append("")

    # Mean Vector
    mean_vec = result.get("mean_vector")
    if mean_vec is not None and var_names:
        lines.append("Mean Vector")
        lines.append("-" * 35)
        for name, val in zip(var_names, mean_vec):
            lines.append(f"  {name:<18} : {_fmt(val, 4)}")
        lines.append("")

    # Covariance Matrix
    cov_mat = result.get("covariance_matrix") or result.get("pooled_covariance")
    if cov_mat is not None and var_names:
        lines.append("Covariance Matrix")
        lines.append("-" * 35)
        header = " " * 12 + "".join(f"{name:>12}" for name in var_names)
        lines.append(header)
        for i, row in enumerate(cov_mat):
            r_str = f"  {var_names[i]:<10}" + "".join(f"{_fmt(c, 4):>12}" for c in row)
            lines.append(r_str)
        lines.append("")

    # Test Results
    signals = result.get("signals", [])
    lines.append("Test Results for Special Causes")
    lines.append("-" * 45)
    if not signals:
        lines.append("  Test 1: One point beyond control limits.")
        lines.append("  * NOTE * No points were found to be out of control.")
    else:
        lines.append("  Test 1: One point beyond control limits.")
        lines.append("    Failed at Subgroup(s): " + ", ".join(str(s) for s in sorted(signals)))

        decomps = result.get("decompositions", {})
        if decomps:
            lines.append("")
            lines.append("  Individual Variable Contributions (Univariate T) for Signaled Subgroups:")
            for sig, contribs in decomps.items():
                items = [f"{k}: {_fmt(v, 2)}" for k, v in contribs.items()]
                lines.append(f"    Subgroup {sig}: " + ", ".join(items))

    lines.append("")
    return "\n".join(lines)
