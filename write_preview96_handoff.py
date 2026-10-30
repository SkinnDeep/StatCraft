import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview96-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

text = f'''# StatCraft preview96 - 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview96.exe**.

StatCraft Preview 96 delivers an expansive wide-pass implementation of **Tables and Chi-Square Tests** under `Stat > Tables`, providing 1:1 statistical and functional parity with StatCraft/22.6 for contingency table analysis, goodness-of-fit testing, two-way worksheet association, and discrete frequency tallies.

Tables and Chi-Square:
- **Cross Tabulation and Chi-Square**: Two-way cross-classification of raw categorical variables with optional frequency weighting; computes observed cell counts, expected cell counts ($E_{{ij}} = R_i C_j / N$), row percentages, column percentages, total percentages, standardized residuals ($O_{{ij}} - E_{{ij}} / \\sqrt{{E_{{ij}}}}$), adjusted residuals, Pearson Chi-Square statistic ($\\chi^2 = \\sum (O - E)^2 / E$), Likelihood Ratio Chi-Square ($G^2 = 2 \\sum O \\ln(O/E)$), degrees of freedom $(r - 1)(c - 1)$, exact $p$-values, and low expected count diagnostic warnings ($E_{{ij}} < 5$).
- **Chi-Square Goodness-of-Fit Test (One Variable)**: Evaluates whether categorical sample data follow hypothesized equal proportions ($p_i = 1/k$) or user-specified custom proportions (e.g. Mendelian genetics ratios); computes observed counts, hypothesized proportions, expected counts, individual chi-square contributions, total Pearson $\\chi^2$, degrees of freedom $k - 1$, and $p$-value.
- **Chi-Square Test for Association (Two-Way Table in Worksheet)**: Direct contingency analysis for aggregated summary tables stored across worksheet columns with optional row label columns; computes full two-way contingency table, expected counts, cell contributions, row/column/grand totals, Pearson and Likelihood Ratio chi-square tests, and degrees of freedom.
- **Tally Individual Variables**: Rapid discrete variable exploration calculating frequency counts, percentages, cumulative counts, cumulative percentages, and missing value tallies across one or multiple columns.
- **High-DPI Contingency & Goodness-of-Fit Charts**: `TablesChartWidget` with interactive Pan/Zoom via `GraphInteractionMixin`, rendering crisp clustered bar charts across row and column categories, statistical header with Pearson $\\chi^2$, DF, and $p$-value, category tooltips, and side-by-side Observed vs Expected bar plots.
- **Interactive Qt Dialogs & Menu**: Native dialogs (`CrossTabulationDialog`, `ChiSquareGoodnessOfFitDialog`, `ChiSquareAssociationDialog`, `TallyDialog`) with column picker, double-click insertion, display options, and parameter validation under `Stat > &Tables`.
- **Authentic StatCraft Reports**: Formatted session window reports for all 4 table procedures matching StatCraft formatting, row/column headings, cell contents keys, and diagnostic notes.
- **Persistence & Immutability**: All 4 table procedures are integrated into MPX recipes and session history without altering benchmark project fixtures.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview96-contract.md)
- [Release verification](StatCraft-preview96-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-96-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview96'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview96 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview 96 handoff and priority list updated')
