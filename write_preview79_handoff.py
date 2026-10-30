import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview79-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview79 — 26 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview79.exe**.

Added working Multiple Variables Normal and Nonnormal capability analyses, replacing both placeholders. Named source selectors support independent columns or a response split by By groups, individual specifications/targets, subgroup sizes or ID columns, working normal estimation and confidence options, comparison reports and actual charts. DOCX/PPTX exports include the composed plots; source-aware MPX recipes follow column edits and block deleted inputs until Undo.

Fixed large-sample unbiasing overflow, unstable benchmark-Z inversion, one-sided confidence chart crashes, incorrect benchmark-Z plot tables, clipped normal specification labels and missing numeric axes, and the Box-Cox density overlay on the original scale.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Maximized startup, splash dismissal and project loading passed. {proof['source_archive_entries_byte_equal']} archive entries match current source; {proof['frozen_application_source']['application_modules_checked']} packaged application modules match compiled current source. Original quiz1.mpx is unchanged.

- [Scope and remaining options](StatCraft-preview79-contract.md)
- [REA evidence](StatCraft-preview79-rea-evidence.json)
- [Release verification](StatCraft-preview79-verification.json)
- [Demonstration project](StatCraft-multiple-capability-demo.mpx)
- [Actual capability plots](StatCraft-preview79-capability.png)

Next priorities, from broad user-facing gaps to narrower options: audit remaining statistical menus and child options for partial workflows; verify worksheet editing and graph interactions against native behavior; extend DOE/reliability/quality procedures with tested options; implement remaining capability options and native numerical oracle comparisons; close visual/layout details. The earlier Gemini review remains useful context, but this release is the current handoff.

Full native numerical and visual parity remain unverified. Multiple-variable spec-source columns, boundaries, storage, additional distributions, transformations, probability alternatives and independent native graph windows remain incomplete. A product-wide completion percentage has not been established.

'''
(out/'StatCraft-preview-79-changes.md').write_text(text,encoding='utf-8')
for name in ['StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md']:
 p=out/name;old=p.read_text(encoding='utf-8-sig') if p.exists() else ''
 if not old.startswith('# StatCraft preview79'):
  p.write_text(text+'---\n\nHistorical notes follow; preview79 above is the current handoff. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview79 handoff, backlog, audit and changelog updated.')
