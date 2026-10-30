import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview82-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview82 — 27 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview82.exe**.

Added Analyze Dynamic Taguchi Design under Stat > DOE > Taguchi. Named response columns are explicitly paired with signal values; fitting supports a free intercept or fixed reference point, adjusted/unadjusted S/N, residual SD/ln(SD), response tables and optional estimable main-effects GLM inference. Actual main-effects plots and per-run measured response-versus-signal plots include editable symbols/lines and Office snapshots. Source-linked recipes preserve response/signal pairing through column edits, MPX save/reopen/rerun and source deletion/Undo.

REA authenticated nine native dialog payloads to guide labels/options. Static resources do not prove native runtime defaults or numerical parity. Independent algebra/NumPy comparisons and live source/frozen workflows cover the implemented statistics and UI.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization, splash dismissal and project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match current files; {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled current source. Original quiz1.mpx remains unchanged. The independent 1200-cell Excel comparison remains historical preview80 evidence.

- [Scope, statistical methods and remaining limits](StatCraft-preview82-contract.md)
- [Authenticated native REA evidence](StatCraft-preview82-rea-evidence.json)
- [Release verification](StatCraft-preview82-verification.json)
- [Working dynamic Taguchi MPX](StatCraft-dynamic-taguchi-demo.mpx)
- [Actual graph output](StatCraft-preview82-dynamic-taguchi.png)
- [Actual variable/signal dialog](StatCraft-preview82-dynamic-dialog.png)

Next priorities: mixture ternary/contour plots and optimization; mixture process/block/covariate models; remaining Taguchi reference/interactions/noise-factor/stacked-input/storage/optimum workflows; broader native options and numerical oracle comparisons. Signal plots show the first 24 complete runs explicitly. Full native numerical/UI parity and a product-wide completion percentage remain unverified.
'''
(out/'StatCraft-preview-82-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 p=out/name;old=p.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview82'):
  p.write_text(text+'\n---\n\nHistorical notes follow; preview82 above is current. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview82 changes, handoff and backlog updated.')
