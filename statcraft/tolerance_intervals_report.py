"""Text session report formatter for Tolerance Intervals (Normal Distribution)."""


def _fmt(val, dec=4):
    if val is None:
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}g}"


def generate_tolerance_intervals_report(result: dict) -> str:
    """Format tolerance intervals results into Standard statistical session report."""
    lines = []
    title = result.get('title') or "Tolerance Intervals (Normal Distribution)"
    var_name = result.get('variable_name', 'Sample')

    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {var_name}")
    lines.append("")

    # Descriptive Statistics table
    lines.append("Descriptive Statistics")
    lines.append(f"  {'Sample Size (N)':<32} {result['n']}")
    lines.append(f"  {'Mean':<32} {_fmt(result['mean'], 6)}")
    lines.append(f"  {'Standard Deviation (s)':<32} {_fmt(result['std'], 6)}")
    lines.append("")

    # Specifications
    conf = result.get('conf_level', 95.0)
    cov = result.get('min_percent', 95.0)
    itype = result.get('interval_type', 'two_sided')
    itype_desc = {
        'two_sided': 'Two-sided',
        'lower': 'Lower bound',
        'upper': 'Upper bound'
    }.get(itype, itype.capitalize())

    lines.append("Tolerance Intervals Parameters")
    lines.append(f"  {'Minimum percentage of population':<32} {cov:g}%")
    lines.append(f"  {'Specified confidence level':<32} {conf:g}%")
    lines.append(f"  {'Interval type':<32} {itype_desc}")
    lines.append("")

    # Normal Interval
    nl = result.get('normal_lower')
    nu = result.get('normal_upper')
    k = result.get('k')

    lines.append("Normal Method")
    lines.append(f"  {'Achieved Confidence Level':<32} {conf:g}%")
    if k is not None:
        lines.append(f"  {'Tolerance Factor (k)':<32} {k:.4f}")

    if itype == 'two_sided':
        lines.append(f"  {'Tolerance Interval':<32} ( {_fmt(nl, 5)}, {_fmt(nu, 5)} )")
    elif itype == 'lower':
        lines.append(f"  {'Lower Bound':<32} {_fmt(nl, 5)}")
    else:
        lines.append(f"  {'Upper Bound':<32} {_fmt(nu, 5)}")
    lines.append("")

    # Nonparametric Interval (if raw observations available)
    np_res = result.get('nonparametric')
    if np_res:
        lines.append("Nonparametric Method")
        achieved = np_res.get('achieved_confidence', 0.0)
        lines.append(f"  {'Achieved Confidence Level':<32} {achieved:.2f}%")
        npl = np_res.get('lower')
        npu = np_res.get('upper')
        if itype == 'two_sided':
            lines.append(f"  {'Tolerance Interval':<32} ( {_fmt(npl, 5)}, {_fmt(npu, 5)} )")
        elif itype == 'lower':
            lines.append(f"  {'Lower Bound':<32} {_fmt(npl, 5)}")
        else:
            lines.append(f"  {'Upper Bound':<32} {_fmt(npu, 5)}")
        lines.append("")
        if achieved < conf:
            lines.append(f"Note: The achieved confidence level for the nonparametric interval ({achieved:.1f}%) is less than the specified confidence level ({conf:g}%).")
            lines.append("      A larger sample size is required to achieve the target confidence level nonparametrically.")
    else:
        lines.append("Nonparametric interval not available for summarized data.")

    return "\n".join(lines)
