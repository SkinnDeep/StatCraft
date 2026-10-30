import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview83-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview83 — 27 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview83.exe**.

Added Contour Plot and Response Optimizer under Stat > DOE > Mixture. Three-component slices respect saved bounds and holding amounts for other components; actual filled bands/isolines, original-unit axes, legends and editable graph objects render from the fitted mesh. The optimizer supports min/max/target goals, tighter/fixed component bounds, search settings, optional starting amounts, fitted uncertainty and an actual composition plot. Linear extrema use constrained LP; nonlinear searches use multiple starts/boundary candidates and are explicitly not globally certified.

Both workflows use named source-bound fitted models, refit current data, and preserve component/hold identity through column moves/renames, MPX save/reopen/rerun and source deletion/Undo. Mesh seams and constant-surface legend handling were checked with actual captures. Inapplicable Cartesian controls are disabled; graph annotations, applicable styles and Office snapshots work.

REA authenticated seven native dialog payloads for axes, holding amounts, display, optimizer and goals. Static resources guide form controls; native runtime/default/numerical equivalence remains unverified.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization, splash dismissal and project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match current files; {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled current source. Original quiz1.mpx remains unchanged. The independent 1200-cell Excel comparison remains historical preview80 evidence.

- [Scope, methods and remaining limits](StatCraft-preview83-contract.md)
- [Authenticated native REA evidence](StatCraft-preview83-rea-evidence.json)
- [Release verification](StatCraft-preview83-verification.json)
- [Working mixture exploration MPX](StatCraft-mixture-exploration-demo.mpx)
- [Actual contour output](StatCraft-preview83-contour.png)
- [Actual optimizer output](StatCraft-preview83-optimizer.png)
- [Actual optimizer dialog](StatCraft-preview83-optimizer-dialog.png)

Next priorities: mixture process/block/covariate models and multiresponse optimization; native contour options/surface variants and interactive optimizer profiles; remaining Taguchi reference/interactions/noise-factor/stacked-input/storage workflows; broader native options, worksheet/graph fidelity and numerical oracle comparisons. Full native numerical/UI parity and a product-wide completion percentage remain unverified.
'''
(out/'StatCraft-preview-83-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 p=out/name;old=p.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview83'):
  p.write_text(text+'\n---\n\nHistorical notes follow; preview83 above is current. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview83 changes, handoff and backlog updated.')
