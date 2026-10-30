"""Standard statistical report formatting for Two-Way Analysis of Variance."""
from __future__ import annotations


def format_twoway_anova_report(result: dict) -> str:
    """Format standard StatCraft Two-Way ANOVA output."""
    resp = result.get("response_name", "Response")
    fa = result.get("factor_a_name", "Factor A")
    fb = result.get("factor_b_name", "Factor B")

    lines = []
    lines.append(f"Two-Way Analysis of Variance: {resp} versus {fa}, {fb}")
    lines.append("")
    lines.append(f"Analysis of Variance for {resp}")

    # Standard StatCraft ANOVA Table
    # Source          DF         SS         MS         F         P
    header = "Source".ljust(16) + "DF".rjust(6) + "Adj SS".rjust(12) + "Adj MS".rjust(12) + "F-Value".rjust(10) + "P-Value".rjust(10)
    lines.append(header)

    def _fmt(val, width=12, decimals=4):
        if val is None:
            return "*".rjust(width)
        return f"{val:.{decimals}f}".rjust(width)

    # Factor A
    row_a = (
        fa[:15].ljust(16) +
        str(result["df_a"]).rjust(6) +
        _fmt(result["ss_a"]) +
        _fmt(result["ms_a"]) +
        _fmt(result["f_a"], width=10, decimals=2) +
        _fmt(result["p_a"], width=10, decimals=3)
    )
    lines.append(row_a)

    # Factor B
    row_b = (
        fb[:15].ljust(16) +
        str(result["df_b"]).rjust(6) +
        _fmt(result["ss_b"]) +
        _fmt(result["ms_b"]) +
        _fmt(result["f_b"], width=10, decimals=2) +
        _fmt(result["p_b"], width=10, decimals=3)
    )
    lines.append(row_b)

    # Interaction
    if result.get("fit_interaction") and result.get("df_ab", 0) > 0:
        row_ab = (
            f"{fa[:7]}*{fb[:7]}".ljust(16) +
            str(result["df_ab"]).rjust(6) +
            _fmt(result["ss_ab"]) +
            _fmt(result["ms_ab"]) +
            _fmt(result["f_ab"], width=10, decimals=2) +
            _fmt(result["p_ab"], width=10, decimals=3)
        )
        lines.append(row_ab)

    # Error
    row_err = (
        "Error".ljust(16) +
        str(result["df_error"]).rjust(6) +
        _fmt(result["ss_error"]) +
        _fmt(result["ms_error"])
    )
    lines.append(row_err)

    # Total
    row_tot = (
        "Total".ljust(16) +
        str(result["df_total"]).rjust(6) +
        _fmt(result["ss_total"])
    )
    lines.append(row_tot)

    # Model Summary
    lines.append("")
    lines.append("Model Summary")
    s_val = result.get("s", 0.0)
    r_sq = result.get("r_squared", 0.0) * 100.0
    r_sq_adj = result.get("adjusted_r_squared", 0.0) * 100.0
    sum_header = "S".rjust(10) + "R-sq".rjust(12) + "R-sq(adj)".rjust(14)
    lines.append(sum_header)
    sum_row = f"{s_val:.4f}".rjust(10) + f"{r_sq:.2f}%".rjust(12) + f"{r_sq_adj:.2f}%".rjust(14)
    lines.append(sum_row)

    # Means
    if result.get("display_means", True):
        lines.append("")
        lines.append("Means")
        lines.append("")
        m_head_a = fa[:15].ljust(16) + "N".rjust(6) + "Mean".rjust(12) + "StDev".rjust(12)
        lines.append(m_head_a)
        for stat in result.get("factor_a_stats", []):
            lvl = str(stat["level"])[:15].ljust(16)
            cnt = str(stat["count"]).rjust(6)
            m = _fmt(stat["mean"])
            s = _fmt(stat["stdev"])
            lines.append(lvl + cnt + m + s)

        lines.append("")
        m_head_b = fb[:15].ljust(16) + "N".rjust(6) + "Mean".rjust(12) + "StDev".rjust(12)
        lines.append(m_head_b)
        for stat in result.get("factor_b_stats", []):
            lvl = str(stat["level"])[:15].ljust(16)
            cnt = str(stat["count"]).rjust(6)
            m = _fmt(stat["mean"])
            s = _fmt(stat["stdev"])
            lines.append(lvl + cnt + m + s)

    return "\n".join(lines)
