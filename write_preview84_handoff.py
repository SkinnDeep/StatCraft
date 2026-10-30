import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview84-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview84 — 28 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview84.exe**.

Added Multiple Response Optimizer under Stat > DOE > Mixture. Two to eight fitted responses share one constrained mixture. Named model selectors, min/max/target goals, lower/target/upper limits, weight/importance, shared/tightened/fixed component bounds, search controls and optional starts produce individual/composite desirabilities and conditional uncertainty. Searches do not claim general nonlinear global optimality or prove infeasibility when no positive solution is found.

Added actual clickable mixture profiles. Each column transfers amount between a named pair while preserving the fixed total and bounds. Clicks create separately saved selected-setting results; Re-optimize searches again from that setting. Native-style composite/response rows, current-setting lines, annotations and Office snapshots work. Source-bound recipes retain every fitted response through column moves/renames, MPX save/reopen/rerun and source deletion/Undo. Exact feasible amounts are preserved to avoid one-ULP perturbations of desirability boundaries. Better starting settings remain candidates even when a local solve converges elsewhere.

Five retained REA native dialog payloads were reauthenticated for response/goal/option labels. This is static evidence reuse, not a fresh native runtime capture or proof of native numerical equivalence.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization, splash dismissal and project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match current files; {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled current source. Original quiz1.mpx remains unchanged. The independent 1200-cell Excel comparison remains historical preview80 evidence.

- [Scope, methods and remaining limits](StatCraft-preview84-contract.md)
- [Authenticated retained REA evidence](StatCraft-preview84-rea-evidence.json)
- [Release verification](StatCraft-preview84-verification.json)
- [Working multi-response mixture MPX](StatCraft-mixture-multi-demo.mpx)
- [Actual optimization profiles](StatCraft-preview84-optimizer.png)
- [Actual selected-setting profiles](StatCraft-preview84-selected.png)
- [Actual response goals dialog](StatCraft-preview84-dialog.png)

Next priorities: mixture process/block/covariate models, richer profile/contour/storage workflows and component-order alignment; remaining Taguchi reference/interactions/noise-factor/stacked-input workflows; broader native options, worksheet/graph fidelity and numerical oracle comparisons. Complete native numerical/UI parity and a product-wide completion percentage remain unverified.
'''
(out/'StatCraft-preview-84-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 p=out/name;old=p.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview84'):
  p.write_text(text+'\n---\n\nHistorical notes follow; preview84 above is current. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview84 changes, handoff and backlog updated.')

