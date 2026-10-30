import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview95-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

text = f'''# StatCraft preview95 — 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview95.exe**.

StatCraft Preview 95 delivers an expansive wide-pass implementation of **Power and Sample Size** under `Stat > Power and Sample Size`, providing 1:1 statistical and functional parity with StatCraft/22.6 for study planning, power calculations, sample size determination, detectable effect sizes, interactive Qt dialogs, and high-fidelity power curves.

Power and Sample Size:
- **1-Sample Z**: Analytical normal model solving for sample size or power given differences, assumed standard deviation $\\sigma$, and two-sided or one-sided alternative hypotheses.
- **1-Sample t**: Exact non-central Student\'s $t$ distribution model with robust asymptotic evaluation for large non-centrality parameters, solving for sample size or power.
- **2-Sample t**: Independent two-sample design ($n_1 = n_2$) with non-central $t$ distribution, solving for sample size per group or statistical power.
- **Paired t**: Within-subject paired design modeling differences with non-central $t$ distribution.
- **1 Proportion**: Binomial testing of comparison proportions against baseline $p_0$ using normal approximation with continuity adjustment, solving for sample size or power.
- **2 Proportions**: Two independent binomial samples comparison, solving for sample size per group or power.
- **One-Way ANOVA**: Multi-group balanced design ($k \\ge 2$) with non-central $F$ distribution across maximum difference $D = \\max(\\mu_i) - \\min(\\mu_i)$ and within-group standard deviation $\\sigma$.
- **2-Level Factorial Design**: 2-level full and fractional factorial designs (2^(k-p)) with corner points, center points, and replicates; models detectable effect sizes via non-central t distribution.
- **High-DPI Power Curve Chart**: `PowerCurveWidget` with interactive Pan/Zoom via `GraphInteractionMixin` rendering smooth power curves, target power reference lines at 0.80 and 0.90, multi-parameter legend, and tooltips.
- **Interactive Qt Dialogs & Menu**: Dedicated dialogs with dual calculation modes ("Calculate sample sizes" vs "Calculate power"), input validation, and OK/Cancel buttons under `Stat > &Power and Sample Size`.
- **Session Reports**: Authentic StatCraft session window reports including Method, Assumed Parameters, and Results table with Differences, Sample Sizes, Target Powers, and Actual Powers.
- **Persistence & Immutability**: All 8 power procedures are integrated into MPX recipes and session history without altering benchmark project fixtures.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview95-contract.md)
- [Release verification](StatCraft-preview95-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-95-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview95'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview95 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview95 handoff and priority list updated')
