import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview92-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

text = f'''# StatCraft preview92 — 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview92.exe**.

StatCraft Preview 92 delivers an expansive wide-pass implementation of **Nonparametric Statistical Tests** under `Stat > Nonparametrics`, providing 1:1 statistical and functional parity with StatCraft/22.6 for distribution-free median hypothesis testing, confidence intervals, two-sample comparisons, multi-group ANOVA alternatives, randomized block experiments, randomness testing, and paired designs.

Nonparametric Statistical Tests:
- **1-Sample Sign Test**: Exact binomial tests of median with upper, lower, and two-sided alternative hypotheses; exact binomial order statistic confidence intervals and non-linear interpolated confidence intervals.
- **1-Sample Wilcoxon**: Signed-rank test of median with exact and continuity-corrected normal approximations, mid-ranks for ties, variance tie correction, and pseudo-median Walsh averages with confidence bounds.
- **Mann-Whitney**: Two-sample rank-sum test of median difference with Hodges-Lehmann point estimator, exact/approximate confidence intervals, test statistic $W$, and tie-adjusted p-values.
- **Kruskal-Wallis**: Multi-group nonparametric median comparison with $H$-statistic, tie-adjustment factor $C$, degrees of freedom, asymptotic $\\chi^2$ p-values, and per-group average ranks and $Z$-scores.
- **Mood's Median Test**: Nonparametric test of group medians around overall median; $k \\times 2$ contingency table with Pearson $\\chi^2$ test of independence, group medians, interquartile ranges (IQR), and 95% individual median confidence intervals.
- **Friedman Test**: Nonparametric randomized complete block design with $S$-statistic, within-block tie corrections, treatment rank sums, and $\\chi^2$ test of treatment effects.
- **Runs Test**: Test of data sequence randomness around sample mean or specified cutoff $K$; computes observed runs $R$, expected runs $\\mu_R$, standard deviation $\\sigma_R$, $Z$-score, and two-sided p-value.
- **Paired Wilcoxon**: Nonparametric signed-rank test on pairwise differences between two numeric columns.
- **High-DPI Visualization**: `NonparametricChartWidget` rendering Group Comparison Plots (Mann-Whitney / Kruskal-Wallis), Mood's Median Confidence Interval Plots with overall median reference line, and Sequence Runs Charts with threshold lines and runs statistics.
- **Interactive Qt Dialogs & Menu**: Modern Qt dialogs with dual-list column selectors, variable role validation, and hypothesis settings under `Stat > &Nonparametrics`.
- **Persistence & Immutability**: All 8 nonparametric tests are fully integrated into MPX recipes, supporting rerun invariance and persistence without modifying original benchmark files.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview92-contract.md)
- [Release verification](StatCraft-preview92-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-92-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview92'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview92 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview92 handoff and priority list updated')
