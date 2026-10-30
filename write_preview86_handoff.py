import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview86-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview86 — 28 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview86.exe**.

Added Contour with Process Variables and Optimize with Process Variables under Stat > DOE > Mixture. Explicit process/covariate/block settings produce constrained mixture contours and optimization with full fitted-model uncertainty. The process table defaults to documented native coded units, offers reversible worksheet-unit display and shows actual-value previews. Actual holding settings remain visible in graphs/reports and are saved in source-bound recipes through column edits and MPX persistence.

Conditional means/SE/CI/PI match full-model predictions through an exact basis/covariance transformation. Additional roles are held explicitly, not silently dropped or jointly optimized. Unknown blocks, missing holds and invalid saved covariance are rejected. The shared optimizer now retains evaluated starting settings after convergence. Residual diagnostics gained readable ticks, whole-number frequencies and nonnegative automatic order axes while preserving manual limits; contour holding headers have dedicated spacing.

Six retained REA resource payloads were authenticated, and official native documentation confirms coded process holding units. Static evidence does not establish native runtime/default/numerical equivalence.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization, splash dismissal and project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match current files; {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled current source. Original quiz1.mpx remains unchanged. The independent 1200-cell Excel comparison remains historical preview80 evidence.

- [Scope, methods and remaining limits](StatCraft-preview86-contract.md)
- [Authenticated retained REA evidence](StatCraft-preview86-rea-evidence.json)
- [Release verification](StatCraft-preview86-verification.json)
- [Working conditional mixture MPX](StatCraft-mixture-condition-demo.mpx)
- [Actual conditional contour](StatCraft-preview86-contour.png)
- [Actual conditional optimizer](StatCraft-preview86-optimizer.png)
- [Improved residual diagnostics](StatCraft-preview86-residuals.png)
- [Actual coded holding dialog](StatCraft-preview86-contour-dialog.png)

Next priorities: joint process/composition and extended-model multi-response optimization; crossed mixture/process design creation; native custom-term/storage and richer contour/surface workflows; remaining Taguchi procedures; broader worksheet/graph fidelity and numerical oracle comparisons. Complete native numerical/UI parity and a product-wide completion percentage remain unverified.
'''
(out/'StatCraft-preview-86-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 p=out/name;old=p.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview86'):
  p.write_text(text+'\n---\n\nHistorical notes follow; preview86 above is current. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview86 changes, handoff and backlog updated.')
