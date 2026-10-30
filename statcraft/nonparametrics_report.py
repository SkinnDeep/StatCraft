"""Report generation for Nonparametric Statistical Tests matching StatCraft session output."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}f}"


def format_sign_test_report(result: Dict[str, Any], var_name: str = "C1") -> str:
    """Format 1-Sample Sign Test session report."""
    test_med = _fmt(result.get("test_median", 0.0))
    alt = result.get("alternative", "two_sided")
    alt_sym = "not =" if alt == "two_sided" else "<" if alt == "less" else ">"

    lines = [
        f"Sign Test for Median: {var_name}",
        "",
        f"Sign test of median =  {test_med} versus {alt_sym}  {test_med}",
        "",
        "        N  Below  Equal  Above        P  Median",
        f"{var_name:<6} {result.get('n', 0):>4}   {result.get('n_below', 0):>4}   {result.get('n_equal', 0):>4}   {result.get('n_above', 0):>4}   {_fmt(result.get('p_value', 0.0), 4):>6}  {_fmt(result.get('median', 0.0)):>6}",
        "",
    ]

    ci_list = result.get("confidence_intervals", [])
    if ci_list:
        target_pct = _fmt(result.get("target_conf", 0.95) * 100.0, 1)
        lines.extend([
            "Sign Confidence Interval",
            "",
            "                                 Confidence",
            "          N  Median  Confidence    Interval       Position",
        ])
        for row in ci_list:
            pos = row["position"]
            conf_str = f"{row['confidence']:.4f}"
            ci_str = f"( {_fmt(row['lower'])},  {_fmt(row['upper'])})"
            lines.append(f"{var_name:<6} {result.get('n', 0):>4}  {_fmt(result.get('median', 0.0)):>6}      {conf_str}  {ci_str:<18}        {pos}")

        nli_ci = result.get("nli_ci")
        if nli_ci is not None:
            nli_str = f"( {_fmt(nli_ci[0])},  {_fmt(nli_ci[1])})"
            lines.append(f"                         {result.get('target_conf', 0.95):.4f}  {nli_str:<18}  NLI")
        lines.append("")

    return "\n".join(lines)


def format_one_sample_wilcoxon_report(result: Dict[str, Any], var_name: str = "C1") -> str:
    """Format 1-Sample Wilcoxon Signed Rank Test session report."""
    test_med = _fmt(result.get("test_median", 0.0))
    alt = result.get("alternative", "two_sided")
    alt_text = "not =" if alt == "two_sided" else "<" if alt == "less" else ">"

    lines = [
        f"Wilcoxon Signed Rank Test: {var_name}",
        "",
        f"Test of median = {test_med} versus median {alt_text} {test_med}",
        "",
        "                  N for   Wilcoxon                  Estimated",
        "          N        Test  Statistic        P            Median",
        f"{var_name:<6} {result.get('n', 0):>4}        {result.get('n_test', 0):>4}     {_fmt(result.get('statistic_w', 0.0), 1):>6}   {_fmt(result.get('p_value', 0.0), 3):>6}            {_fmt(result.get('estimated_median', 0.0)):>6}",
        "",
    ]

    ci = result.get("ci")
    if ci is not None:
        conf_pct = _fmt(result.get("confidence", 0.95) * 100.0, 1)
        ci_str = f"( {_fmt(ci[0])},  {_fmt(ci[1])})"
        lines.extend([
            f"Wilcoxon Signed Rank CI: {var_name}",
            "",
            "                               Estimated  Achieved        Confidence",
            "          N  N for Test           Median  Confidence        Interval",
            f"{var_name:<6} {result.get('n', 0):>4}        {result.get('n_test', 0):>4}          {_fmt(result.get('estimated_median', 0.0)):>6}       {conf_pct}%   {ci_str}",
            "",
        ])

    return "\n".join(lines)


def format_mann_whitney_report(result: Dict[str, Any], name1: str = "C1", name2: str = "C2") -> str:
    """Format Mann-Whitney Test and CI session report."""
    alt = result.get("alternative", "two_sided")
    alt_sym = "not =" if alt == "two_sided" else "<" if alt == "less" else ">"
    conf_pct = _fmt(result.get("confidence", 0.95) * 100.0, 1)
    ci = result.get("ci", (0.0, 0.0))

    lines = [
        f"Mann-Whitney Test and CI: {name1}, {name2}",
        "",
        f"N = {result.get('n1', 0)} for {name1}, N = {result.get('n2', 0)} for {name2}",
        "",
        f"Point estimate for eta1 - eta2 is {_fmt(result.get('point_estimate', 0.0))}",
        f"{conf_pct} Percent CI for eta1 - eta2 is ({_fmt(ci[0])}, {_fmt(ci[1])})",
        f"W = {_fmt(result.get('statistic_w', 0.0), 1)}",
        f"Test of eta1 = eta2 vs eta1 {alt_sym} eta2 is significant at P = {_fmt(result.get('p_value', 0.0), 4)}",
    ]

    if result.get("has_ties", False):
        lines.append(f"The test is significant at P = {_fmt(result.get('p_value', 0.0), 4)} (adjusted for ties)")
    lines.append("")

    return "\n".join(lines)


def format_kruskal_wallis_report(result: Dict[str, Any], resp_name: str = "Response", factor_name: str = "Factor") -> str:
    """Format Kruskal-Wallis Test session report."""
    lines = [
        f"Kruskal-Wallis Test: {resp_name} versus {factor_name}",
        "",
        f"{factor_name:<10}    N   Median  Ave Rank      Z",
    ]

    for g in result.get("group_stats", []):
        level = str(g["level"])[:10]
        n_i = g["n"]
        med = _fmt(g["median"])
        avg_r = _fmt(g["avg_rank"], 1)
        z_v = _fmt(g["z"], 2)
        lines.append(f"{level:<10} {n_i:>4}   {med:>6}     {avg_r:>5}  {z_v:>5}")

    lines.extend([
        f"Overall    {result.get('n', 0):>4}              {_fmt(result.get('overall_avg_rank', 0.0), 1):>5}",
        "",
        f"H = {_fmt(result.get('h_statistic', 0.0), 2)}  DF = {result.get('df', 1)}  P = {_fmt(result.get('p_value', 0.0), 3)}",
    ])

    if result.get("has_ties", False):
        lines.append(f"H = {_fmt(result.get('h_adjusted', 0.0), 2)}  DF = {result.get('df', 1)}  P = {_fmt(result.get('p_adjusted', 0.0), 3)} (adjusted for ties)")
    lines.append("")

    return "\n".join(lines)


def format_moods_median_report(result: Dict[str, Any], resp_name: str = "Response", factor_name: str = "Factor") -> str:
    """Format Mood's Median Test session report."""
    conf_pct = _fmt(result.get("confidence", 0.95) * 100.0, 0)
    lines = [
        f"Mood's Median Test: {resp_name} versus {factor_name}",
        "",
        f"Moods median test for {resp_name}",
        f"Chi-Square = {_fmt(result.get('chi_square', 0.0), 2)}   DF = {result.get('df', 1)}   P = {_fmt(result.get('p_value', 0.0), 3)}",
        "",
        f"{factor_name:<10}   N<=   N>  Median    Q3-Q1  {conf_pct}% Individual CI",
    ]

    for g in result.get("group_rows", []):
        level = str(g["level"])[:10]
        n_le = g["n_le"]
        n_gt = g["n_gt"]
        med = _fmt(g["median"])
        iqr = _fmt(g["iqr"])
        ci = g.get("ci", (0.0, 0.0))
        ci_str = f"( {_fmt(ci[0])},  {_fmt(ci[1])})"
        lines.append(f"{level:<10}  {n_le:>4} {n_gt:>4}  {med:>6}   {iqr:>6}  {ci_str}")

    lines.extend([
        f"Overall median = {_fmt(result.get('overall_median', 0.0))}",
        "",
    ])

    return "\n".join(lines)


def format_friedman_report(result: Dict[str, Any], resp_name: str = "Response", treat_name: str = "Treatment", block_name: str = "Block") -> str:
    """Format Friedman Test session report."""
    lines = [
        f"Friedman Test: {resp_name} versus {treat_name} blocked by {block_name}",
        "",
        f"S = {_fmt(result.get('s_statistic', 0.0), 2)}  DF = {result.get('df', 1)}  P = {_fmt(result.get('p_value', 0.0), 3)}",
    ]

    if result.get("has_ties", False):
        lines.append(f"S = {_fmt(result.get('s_adjusted', 0.0), 2)}  DF = {result.get('df', 1)}  P = {_fmt(result.get('p_adjusted', 0.0), 3)} (adjusted for ties)")

    lines.extend([
        "",
        f"{treat_name:<12}    N  Est Median  Sum of Ranks",
    ])

    for t in result.get("treatment_stats", []):
        name = str(t["treatment"])[:12]
        n_b = t["n"]
        med = _fmt(t["median"])
        r_sum = _fmt(t["rank_sum"], 1)
        lines.append(f"{name:<12} {n_b:>4}      {med:>6}         {r_sum:>5}")

    lines.append("")
    return "\n".join(lines)


def format_runs_test_report(result: Dict[str, Any], var_name: str = "C1") -> str:
    """Format Runs Test session report."""
    k_val = _fmt(result.get("k_threshold", 0.0), 4)
    lines = [
        f"Runs Test: {var_name}",
        "",
        f"Runs test for {var_name}",
        "",
        f"The observed number of runs = {result.get('runs', 0)}",
        f"The expected number of runs = {_fmt(result.get('expected_runs', 0.0), 4)}",
        f"{result.get('n_above_or_equal', 0)} observations above or equal to K  {result.get('n_below', 0)} below K",
        f"K = {k_val}",
        "",
        f"The test is significant at P = {_fmt(result.get('p_value', 0.0), 4)}",
        "",
    ]
    return "\n".join(lines)


def format_paired_wilcoxon_report(result: Dict[str, Any], name1: str = "C1", name2: str = "C2") -> str:
    """Format Paired Wilcoxon Test session report."""
    var_label = f"Diff ({name1} - {name2})"
    test_med = _fmt(result.get("test_median", 0.0))
    alt = result.get("alternative", "two_sided")
    alt_text = "not =" if alt == "two_sided" else "<" if alt == "less" else ">"

    lines = [
        f"Wilcoxon Signed Rank Test: {var_label}",
        "",
        f"Test of median difference = {test_med} versus median difference {alt_text} {test_med}",
        "",
        "                  N for   Wilcoxon                  Estimated",
        "          N        Test  Statistic        P            Median",
        f"{var_label:<10} {result.get('n', 0):>4}        {result.get('n_test', 0):>4}     {_fmt(result.get('statistic_w', 0.0), 1):>6}   {_fmt(result.get('p_value', 0.0), 3):>6}            {_fmt(result.get('estimated_median', 0.0)):>6}",
        "",
    ]

    ci = result.get("ci")
    if ci is not None:
        conf_pct = _fmt(result.get("confidence", 0.95) * 100.0, 1)
        ci_str = f"( {_fmt(ci[0])},  {_fmt(ci[1])})"
        lines.extend([
            f"Wilcoxon Signed Rank CI: {var_label}",
            "",
            "                               Estimated  Achieved        Confidence",
            "          N  N for Test           Median  Confidence        Interval",
            f"{var_label:<10} {result.get('n', 0):>4}        {result.get('n_test', 0):>4}          {_fmt(result.get('estimated_median', 0.0)):>6}       {conf_pct}%   {ci_str}",
            "",
        ])

    return "\n".join(lines)
