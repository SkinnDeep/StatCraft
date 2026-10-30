"""Standard statistical text report for Multi-Vari Chart."""
from __future__ import annotations


def _fmt(val, dec=4):
    if val is None:
        return "*"
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


def format_multivari_report(result: dict) -> str:
    resp = result.get('response_name', 'Response')
    factors = result.get('factor_names', [])
    grand_mean = result.get('grand_mean', 0.0)
    n_tot = result.get('n_total', 0)

    lines = [
        f"Multi-Vari Chart for {resp}",
        "=" * 50,
        f"Factors: {', '.join(factors)}",
        f"Number of observations: {n_tot}",
        f"Overall Mean: {_fmt(grand_mean, 4)}",
        "",
        "Factor Level Means:",
        "-" * 50,
    ]

    flm = result.get('factor_level_means', {})
    for fn, levels in flm.items():
        lines.append(f"Factor: {fn}")
        lines.append(f"  {'Level':<15} {'N':<8} {'Mean':<12}")
        for lvl, data in levels.items():
            lines.append(f"  {lvl:<15} {data['n']:<8} {_fmt(data['mean'], 4):<12}")
        lines.append("")

    lines.append("Cell Combinations:")
    lines.append("-" * 50)
    hdr_factors = "  ".join(f"{fn:<12}" for fn in factors)
    lines.append(f"  {hdr_factors}  {'N':<6} {'Mean':<10} {'Min':<10} {'Max':<10}")
    
    for c in result.get('cells', []):
        f_str = "  ".join(f"{str(v):<12}" for v in c['factors'])
        lines.append(f"  {f_str}  {c['n']:<6} {_fmt(c['mean'], 4):<10} {_fmt(c['min'], 4):<10} {_fmt(c['max'], 4):<10}")

    return "\n".join(lines)
