"""StatCraft session window report formatting for Tables and Chi-Square tests."""

from typing import Any, Dict


def format_cross_tabulation_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Tabulated Statistics: Cross Tabulation and Chi-Square report."""
    r_name = result["row_name"]
    c_name = result["col_name"]
    r_labels = result["row_labels"]
    c_labels = result["col_labels"]
    obs = result["observed"]
    exp = result["expected"]
    row_pcts = result["row_percents"]
    col_pcts = result["col_percents"]
    tot_pcts = result["total_percents"]
    contribs = result["cell_contributions"]
    r_totals = result["row_totals"]
    c_totals = result["col_totals"]
    grand_tot = result["grand_total"]

    inc_exp = result.get("include_expected", True)
    inc_row_p = result.get("include_row_percents", True)
    inc_col_p = result.get("include_col_percents", True)
    inc_tot_p = result.get("include_total_percents", False)

    col_width = 14
    header_col = f"{r_name} \\ {c_name}"

    lines = [
        f"Tabulated statistics: {r_name}, {c_name}",
        "",
        "Rows: " + r_name + "   Columns: " + c_name,
        "",
    ]

    # Header line
    hdr = f"  {header_col:<18}"
    for cl in c_labels:
        hdr += f"{cl:>{col_width}}"
    hdr += f"{'All':>{col_width}}"
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for i, rl in enumerate(r_labels):
        # Count line
        row_str = f"  {rl:<18}"
        for j in range(len(c_labels)):
            row_str += f"{obs[i][j]:>{col_width}.0f}"
        row_str += f"{r_totals[i]:>{col_width}.0f}"
        lines.append(row_str)

        # Expected count
        if inc_exp:
            exp_str = f"  {' ':18}"
            for j in range(len(c_labels)):
                exp_str += f"{exp[i][j]:>{col_width}.2f}"
            exp_str += f"{r_totals[i]:>{col_width}.2f}"
            lines.append(exp_str)

        # Row %
        if inc_row_p:
            rp_str = f"  {' ':18}"
            for j in range(len(c_labels)):
                rp_str += f"{row_pcts[i][j]:>{col_width}.2f}%"
            rp_str += f"{100.0:>{col_width}.2f}%"
            lines.append(rp_str)

        # Col %
        if inc_col_p:
            cp_str = f"  {' ':18}"
            for j in range(len(c_labels)):
                cp_str += f"{col_pcts[i][j]:>{col_width}.2f}%"
            lines.append(cp_str)

        # Total %
        if inc_tot_p:
            tp_str = f"  {' ':18}"
            for j in range(len(c_labels)):
                tp_str += f"{tot_pcts[i][j]:>{col_width}.2f}%"
            tp_str += f"{(r_totals[i]/grand_tot*100.0):>{col_width}.2f}%"
            lines.append(tp_str)

        lines.append("")

    # All (Totals) row
    all_str = f"  {'All':<18}"
    for j in range(len(c_labels)):
        all_str += f"{c_totals[j]:>{col_width}.0f}"
    all_str += f"{grand_tot:>{col_width}.0f}"
    lines.append(all_str)

    if inc_exp:
        all_exp = f"  {' ':18}"
        for j in range(len(c_labels)):
            all_exp += f"{c_totals[j]:>{col_width}.2f}"
        all_exp += f"{grand_tot:>{col_width}.2f}"
        lines.append(all_exp)

    lines.append("")

    # Legend / Cell Contents
    lines.append("Cell Contents")
    lines.append("  Count")
    if inc_exp:
        lines.append("  Expected count")
    if inc_row_p:
        lines.append("  % of Row")
    if inc_col_p:
        lines.append("  % of Column")
    if inc_tot_p:
        lines.append("  % of Total")
    lines.append("")

    # Chi-Square Test Table
    if result.get("include_chi_square", True):
        lines.append("Chi-Square Test")
        lines.append(f"  {'Test':30}{'Chi-Square':>12}{'DF':>6}{'P-Value':>10}")
        lines.append("-" * 58)
        lines.append(f"  {'Pearson':30}{result['pearson_chi_square']:>12.3f}{result['df']:>6}{result['pearson_p_value']:>10.4f}")
        lines.append(f"  {'Likelihood Ratio':30}{result['likelihood_ratio_chi_square']:>12.3f}{result['df']:>6}{result['likelihood_ratio_p_value']:>10.4f}")
        lines.append("")
        if result["cells_expected_less_than_5"] > 0:
            lines.append(f"  * NOTE * {result['cells_expected_less_than_5']} cells with expected counts less than 5 ({result['pct_cells_expected_less_than_5']:.1f}%).")
            lines.append("           Chi-Square approximation may be invalid.")
            lines.append("")

    return "\n".join(lines)


def format_chi_square_goodness_of_fit_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Chi-Square Goodness-of-Fit Test report."""
    v_name = result["var_name"]
    lines = [
        f"Chi-Square Goodness-of-Fit Test for Observed Counts: {v_name}",
        "",
        "Method",
        f"  Total observations: {result['n_obs']:.0f}",
        f"  Number of categories: {len(result['categories'])}",
        "",
        "Observed and Expected Counts",
        f"  {'Category':15}{'Observed':>10}{'Test Prop':>12}{'Expected':>12}{'Contribution':>14}",
        "-" * 63,
    ]
    for r in result["rows"]:
        cat = r["category"]
        obs = r["observed"]
        tp = r["test_proportion"]
        exp = r["expected"]
        cnt = r["contribution"]
        lines.append(f"  {cat:15}{obs:>10.0f}{tp:>12.4f}{exp:>12.2f}{cnt:>14.3f}")

    lines.append("")
    lines.append("Chi-Square Test")
    lines.append(f"  {'N':>8}{'DF':>6}{'Chi-Sq':>12}{'P-Value':>10}")
    lines.append("-" * 36)
    lines.append(f"  {result['n_obs']:>8.0f}{result['df']:>6}{result['chi_square']:>12.3f}{result['p_value']:>10.4f}")
    lines.append("")

    if result["cells_expected_less_than_5"] > 0:
        lines.append(f"  * NOTE * {result['cells_expected_less_than_5']} cells with expected counts less than 5 ({result['pct_cells_expected_less_than_5']:.1f}%).")
        lines.append("")

    return "\n".join(lines)


def format_chi_square_association_table_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Chi-Square Test for Association (Two-Way Table) report."""
    r_names = result["row_names"]
    c_names = result["col_names"]
    obs = result["observed"]
    exp = result["expected"]
    contribs = result["cell_contributions"]
    r_totals = result["row_totals"]
    c_totals = result["col_totals"]
    grand_tot = result["grand_total"]

    col_width = 14
    lines = [
        "Chi-Square Test for Association: Two-Way Table in Worksheet",
        "",
        "Tabulated Statistics",
        "",
    ]

    hdr = f"  {'Rows':<16}"
    for cn in c_names:
        hdr += f"{cn:>{col_width}}"
    hdr += f"{'Total':>{col_width}}"
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for i, rn in enumerate(r_names):
        row_str = f"  {rn:<16}"
        for j in range(len(c_names)):
            row_str += f"{obs[i][j]:>{col_width}.0f}"
        row_str += f"{r_totals[i]:>{col_width}.0f}"
        lines.append(row_str)

        exp_str = f"  {' ':16}"
        for j in range(len(c_names)):
            exp_str += f"{exp[i][j]:>{col_width}.2f}"
        exp_str += f"{r_totals[i]:>{col_width}.2f}"
        lines.append(exp_str)

        cnt_str = f"  {' ':16}"
        for j in range(len(c_names)):
            cnt_str += f"{contribs[i][j]:>{col_width}.3f}"
        lines.append(cnt_str)
        lines.append("")

    all_str = f"  {'Total':<16}"
    for j in range(len(c_names)):
        all_str += f"{c_totals[j]:>{col_width}.0f}"
    all_str += f"{grand_tot:>{col_width}.0f}"
    lines.append(all_str)
    lines.append("")

    lines.append("Cell Contents:  Observed count / Expected count / Chi-Square contribution")
    lines.append("")

    lines.append("Chi-Square Test")
    lines.append(f"  {'Test':30}{'Chi-Square':>12}{'DF':>6}{'P-Value':>10}")
    lines.append("-" * 58)
    lines.append(f"  {'Pearson':30}{result['pearson_chi_square']:>12.3f}{result['df']:>6}{result['pearson_p_value']:>10.4f}")
    lines.append(f"  {'Likelihood Ratio':30}{result['likelihood_ratio_chi_square']:>12.3f}{result['df']:>6}{result['likelihood_ratio_p_value']:>10.4f}")
    lines.append("")

    if result["cells_expected_less_than_5"] > 0:
        lines.append(f"  * NOTE * {result['cells_expected_less_than_5']} cells with expected counts less than 5 ({result['pct_cells_expected_less_than_5']:.1f}%).")
        lines.append("")

    return "\n".join(lines)


def format_tally_variables_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Tally Individual Variables report."""
    v_name = result["var_name"]
    lines = [
        f"Tally for Discrete Variables: {v_name}",
        "",
        f"  {'Value':15}{'Count':>10}{'Percent':>12}{'Cum Count':>12}{'Cum Pct':>12}",
        "-" * 61,
    ]
    for r in result["rows"]:
        val = r["value"]
        cnt = r["count"]
        pct = r["percent"]
        ccnt = r["cumulative_count"]
        cpct = r["cumulative_percent"]
        lines.append(f"  {val:15}{cnt:>10}{pct:>12.2f}{ccnt:>12}{cpct:>12.2f}")

    lines.append("-" * 61)
    lines.append(f"  {'Total':15}{result['n_valid']:>10}")
    if result["n_missing"] > 0:
        lines.append(f"  {'Missing':15}{result['n_missing']:>10}")
    lines.append("")
    return "\n".join(lines)
