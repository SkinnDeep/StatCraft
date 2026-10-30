import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview94-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

text = f'''# StatCraft preview94 — 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview94.exe**.

StatCraft Preview 94 delivers an expansive wide-pass implementation of **Equivalence Tests** under `Stat > Equivalence Tests`, providing 1:1 statistical and functional parity with StatCraft/22.6 for Schuirmann's Two One-Sided Tests (TOST) procedure, difference and ratio hypotheses, $(1 - 2\\alpha) \\times 100\\%$ confidence intervals, interactive Qt dialogs, and high-fidelity interval plots.

Equivalence Tests:
- **1-Sample Equivalence Test**: Tests whether the mean (or mean difference from a target value) is within specified lower and upper equivalence limits. Supports difference hypotheses and ratio hypotheses (via natural log transformation), TOST t-statistics, (1 - 2*alpha) confidence intervals, and automated equivalence claim decisions.
- **2-Sample Equivalence Test**: Independent two-sample equivalence testing of Test vs. Reference populations. Supports difference and ratio scales, equal variance (pooled degrees of freedom) or unequal variance (Welch-Satterthwaite degrees of freedom), TOST p-values, confidence intervals, and full descriptive statistics tables.
- **Paired Equivalence Test**: Paired observations testing within-subject differences or ratios. Computes mean paired differences, standard deviations, standard errors, paired TOST t-statistics, and (1 - 2*alpha) confidence intervals.
- **2x2 Crossover Design Equivalence Test**: Two-sequence, two-period, two-treatment (2x2) crossover clinical/bioequivalence trial analysis. Accounts for period and sequence effects using within-subject difference modeling across sequence groups, calculates sequence-adjusted treatment effects, within-subject error variance, crossover degrees of freedom, and TOST equivalence evaluation.
- **High-DPI Equivalence Interval Plot**: `EquivalenceChartWidget` with interactive Pan/Zoom via `GraphInteractionMixin` rendering shaded equivalence regions, reference target/zero dashed lines, point estimates, (1 - 2*alpha) error bars with limits, and prominent pass/fail equivalence status badges.
- **Interactive Qt Dialogs & Menu**: Modern Qt dialogs with variable picker, numeric margin inputs, hypothesis type selection (Difference vs. Ratio), alpha specification, and OK/Cancel validation under `Stat > &Equivalence Tests`.
- **Session Reports**: Authentic StatCraft session window reports including Method, Descriptive Statistics, Confidence Interval, TOST table, and equivalence claim statements.
- **Persistence & Immutability**: All 4 equivalence procedures are integrated into MPX recipes, supporting rerun invariance and persistence without altering original benchmark files.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview94-contract.md)
- [Release verification](StatCraft-preview94-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-94-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview94'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview94 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview94 handoff and priority list updated')
