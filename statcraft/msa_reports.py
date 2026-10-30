"""Session output report formatters for Advanced MSA (Nested Gage R&R, Gage Linearity & Bias, Attribute Agreement)."""
from __future__ import annotations

from typing import Any, Dict, List


def _fmt(val: Any, decimals: int = 4) -> str:
    if val is None:
        return "*"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def format_nested_gage_rr_report(res: Dict[str, Any]) -> str:
    """Format StatCraft session text report for Nested Gage R&R."""
    lines = []
    lines.append("Gage R&R Study (Nested)")
    lines.append("=" * 60)
    lines.append(f"Design: Balanced Nested Random-Effects ANOVA")
    lines.append(f"Operators: {res.get('operators_count')}   Parts per Operator: {res.get('parts_per_operator')}   Replicates: {res.get('replicates_per_part')}")
    lines.append(f"Total Observations: {res.get('n_total')}")
    lines.append("")

    # ANOVA Table
    lines.append("Analysis of Variance for Nested Design")
    lines.append("-" * 65)
    lines.append(f"{'Source':<20} {'DF':>5} {'SS':>12} {'MS':>12} {'F':>8} {'P':>6}")
    lines.append("-" * 65)
    for row in res.get("anova", []):
        f_str = f"{row['f']:.3f}" if row.get("f") is not None else ""
        p_str = f"{row['p_value']:.4f}" if row.get("p_value") is not None else ""
        ms_str = f"{row['ms']:.4f}" if row.get("ms") is not None else ""
        lines.append(f"{row['source']:<20} {row['df']:>5} {row['ss']:>12.4f} {ms_str:>12} {f_str:>8} {p_str:>6}")
    lines.append("")

    # Variance Components
    lines.append("Gage R&R Variance Components")
    lines.append("-" * 55)
    lines.append(f"{'Source':<25} {'VarComp':>12} {'%Contribution':>15}")
    lines.append("-" * 55)
    for row in res.get("variance_components", []):
        lines.append(f"{row['source']:<25} {row['variance']:>12.5f} {row['percent_contribution']:>14.2f}%")
    lines.append("")

    # Gage Evaluation
    mult = res.get("study_multiplier", 6.0)
    lines.append(f"Gage Evaluation (Study Variation = {mult:.1f} * SD)")
    lines.append("-" * 75)
    has_tol = any(r.get("percent_tolerance") is not None for r in res.get("variance_components", []))
    header = f"{'Source':<25} {'StdDev (SD)':>12} {'Study Var':>12} {'%Study Var':>12}"
    if has_tol:
        header += f" {'%Tolerance':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for row in res.get("variance_components", []):
        line = f"{row['source']:<25} {row['sd']:>12.5f} {row['study_variation']:>12.4f} {row['percent_study_variation']:>11.2f}%"
        if has_tol:
            tol_str = f"{row['percent_tolerance']:>11.2f}%" if row.get("percent_tolerance") is not None else "*"
            line += f" {tol_str:>12}"
        lines.append(line)
    lines.append("")

    ndc = res.get("ndc")
    lines.append(f"Number of Distinct Categories = {ndc if ndc is not None else '*'}")
    lines.append("=" * 60)
    return "\n".join(lines)


def format_gage_linearity_report(res: Dict[str, Any]) -> str:
    """Format estimates while preserving unavailable inferential statistics."""
    reg = res.get('regression', {})
    rsq = reg.get('r_squared')
    lines = ['Gage Linearity and Bias Study', '=' * 60,
        'Process Variation: ' + _fmt(res.get('process_variation')),
        'Regression Equation: ' + str(reg.get('equation', '')),
        'S = ' + _fmt(reg.get('s')) + '   R-Sq = ' + _percent(None if rsq is None else rsq * 100), '',
        'Gage Linearity', '-' * 45,
        'Linearity: ' + _fmt(res.get('linearity'), 5),
        '%Linearity: ' + _percent(res.get('pct_linearity'))]
    for name, key in [('Slope', 'slope'), ('Intercept', 'intercept')]:
        lines.append(name + ': ' + _fmt(reg.get(key), 5) + ' (SE: ' + _fmt(reg.get(key + '_se'), 5)
                     + ', T: ' + _fmt(reg.get(key + '_t'), 3) + ', P: ' + _fmt(reg.get(key + '_p'), 4) + ')')
    lines += ['', 'Gage Bias Table by Reference Value', '-' * 75,
              f"{'Reference':>10} {'N':>5} {'Avg Bias':>12} {'%Bias':>10} {'SE':>10} {'T':>8} {'P':>8}", '-' * 75]
    for row in res.get('bias_table', []):
        lines.append(f"{_fmt(row.get('reference')):>10} {_fmt(row.get('count')):>5} {_fmt(row.get('average_bias'), 5):>12} "
                     f"{_percent(row.get('pct_bias')):>10} {_fmt(row.get('std_error'), 5):>10} {_fmt(row.get('t_statistic'), 3):>8} {_fmt(row.get('p_value')):>8}")
    bias = res.get('overall_bias', {})
    lines += ['', 'Overall Gage Bias', '-' * 45,
              'Average Bias: ' + _fmt(bias.get('average_bias'), 5) + '   %Bias: ' + _percent(bias.get('pct_bias')),
              'T = ' + _fmt(bias.get('t_statistic'), 3) + '   P-Value = ' + _fmt(bias.get('p_value')) + '   SE = ' + _fmt(bias.get('std_error'), 5)]
    lines.extend(str(note) for note in res.get('notes', []))
    lines.append('=' * 60)
    return '\n'.join(lines)


def _percent(value):
    return '*' if value is None else _fmt(value, 2) + '%'


def format_attribute_agreement_report(res: Dict[str, Any]) -> str:
    """Report actual denominators, confidence level and unavailable coefficients."""
    confidence = res.get('confidence_level', .95)
    ci_label = f'{confidence * 100:g}% CI'
    lines = ['Attribute Agreement Analysis', '=' * 65,
             f"Number of Samples: {res.get('n_samples')}   Number of Appraisers: {res.get('n_appraisers')}", '']

    def interval(row):
        if row.get('ci_lower') is None or row.get('ci_upper') is None:
            return '*'
        return f"({_fmt(row['ci_lower'], 1)}%, {_fmt(row['ci_upper'], 1)}%)"

    def table(title, rows):
        lines.extend([title, '-' * 82,
            f"{'Appraiser':<15} {'Inspected':>9} {'Matched':>8} {'Percent':>9} {ci_label:>20} {'Kappa':>8} {'P':>8}", '-' * 82])
        for row in rows:
            lines.append(f"{row['appraiser']:<15} {row['inspected']:>9} {row['matched']:>8} "
                         f"{_percent(row.get('percent')):>9} {interval(row):>20} {_fmt(row.get('kappa')):>8} {_fmt(row.get('p_value')):>8}")
            if row.get('excluded_samples'):
                lines.append(f"  Excluded incomplete/unavailable samples: {row['excluded_samples']}")
            if row.get('note'):
                lines.append('  ' + row['note'])
        lines.append('')

    table('Within Appraiser Agreement', res.get('within_appraiser', []))
    if res.get('has_standard') and res.get('appraiser_vs_standard'):
        table('Each Appraiser vs Standard', res['appraiser_vs_standard'])
    for title, key in [('Between Appraisers Agreement', 'between_appraisers'), ('All Appraisers vs Standard', 'all_appraisers_vs_standard')]:
        row = res.get(key)
        if row is None:
            continue
        lines += [title, '-' * 65,
                  f"Inspected: {row.get('inspected')}   Matched: {row.get('matched')}   Percent: {_percent(row.get('percent'))}   {ci_label}: {interval(row)}"]
        if 'kappa' in row:
            lines.append("Fleiss' Kappa = " + _fmt(row.get('kappa')) + ' (SE: ' + _fmt(row.get('se'))
                         + ', Z: ' + _fmt(row.get('z'), 3) + ', P: ' + _fmt(row.get('p_value')) + ')')
        if row.get('note'):
            lines.append(row['note'])
        if row.get('excluded_samples'):
            lines.append('Excluded incomplete/unavailable samples: ' + str(row['excluded_samples']))
        lines.append('')
    lines.extend(res.get('notes', []))
    lines.append('* = Not estimable or not implemented; see notes.')
    lines.append('=' * 65)
    return '\n'.join(lines)
