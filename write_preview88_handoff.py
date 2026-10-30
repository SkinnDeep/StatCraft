import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
p=json.loads((out/'StatCraft-preview88-verification.json').read_text(encoding='utf-8'));t=p['source_tests']
text=f'''# StatCraft preview88 — 28 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview88.exe**.

The response-surface availability matrix now selects real designs. Every numbered cell applies factor count, family, fraction, blocks and defaults. Designs exposes all58 supported configurations, including full/half/quarter/eighth CCD and larger Box–Behnken designs through10 factors. Center splits, alpha, replication and block-on-replicates affect generated rows, with live run/block/alpha previews. Every preset passes advertised run count, quadratic-plus-block rank and default block-orthogonality checks.

Blocked response-surface OLS now includes the selected fixed block factor in actual inference, ANOVA and diagnostics. Prediction, block-conditioned contour/surface plots, source-column movements/deletions/undo and MPX saved recipes retain the block. An independent least-squares calculation confirms the fits. Continuous models support ten factors and65 polynomial terms. Created block roles are selected automatically by the analysis dialog.

Graph hover readouts show real bin boundaries, plotted measure, raw frequency and rows where retained. Covered renderers include standard/grouped/native histograms, scatter/residual/bubble/3Dpoints, dot/box/individual/interval plots, bars, heatmaps, pie slices, native contour bands and saved surface cells. Layout child hover works without enabling object edits. Resize, gallery switches and export clear stale tips.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} environment-limited hard-link skip, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview88-contract.md)
- [Authenticated native resources](StatCraft-preview88-rea-evidence.json)
- [Release verification](StatCraft-preview88-verification.json)
- [Functional design matrix](StatCraft-preview88-design-catalog.png)
- [Design settings](StatCraft-preview88-design-settings.png)
- [Actual histogram hover](StatCraft-preview88-histogram-hover.png)
- [Working blocked-design MPX](StatCraft-surface-catalog-demo.mpx)
- [Blocked-model surface](StatCraft-preview88-blocked-surface.png)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity (including histogram automatic scales); reconstructing imported native models for fresh analyses; native graph object editing; joint process/composition and multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified. Larger Box–Behnken layouts are independently constructed valid designs. A product-wide completion percentage is not established.
'''
text=text.replace('all58','all 58').replace('through10','through 10').replace('and65','and 65')
(out/'StatCraft-preview-88-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 path=out/name;old=path.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview88'):path.write_text(text+'\n---\n\nHistorical notes follow; preview88 above overrides older completed-feature gaps.\n\n'+old,encoding='utf-8')
print('Preview88 handoff and priority list updated')
