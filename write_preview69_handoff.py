"""Refresh human-facing handoff after release verification succeeds."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview69-verification.json').read_text(encoding='utf-8'))
tests=proof['source_tests'];gates=proof['packaged_workflow_gates']
text=f'''# StatCraft preview69 — 23 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview69.exe**.

This pass preserves Gemini's preview43–68 additions and adds Binomial/Poisson Capability Analysis. It also fixes newer analysis inputs after column moves/renames/deletions, missing Pareto/multivariate dependencies, earlier basic-statistics nested index remapping, actual output-window routing for newer chart families, renderer minimum heights, and zero-variation Type 1 Gage handling. The new capability Report tab uses labeled statistics and intervals rather than internal data fields.

Verification: **{tests['unittest_passed']} source tests passed, {tests.get('skipped',0)} environment-limited hard-link test skipped, {gates} packaged workflow gates passed, {len(proof['mpx_fixtures'])} MPX fixtures opened without modifying originals**. Startup maximization/splash/project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match the working source; {proof['frozen_application_source']['application_modules_checked']} packaged application modules match compiled current source. Bundled Qt/PySide/Shiboken imports/exports were checked. New capability DOCX/PPTX exports parse successfully and contain the actual graph PNGs.

- [Gemini changes review and prioritized remaining work](StatCraft-Gemini-review-2026-10-23.md)
- [Reconstruction boundaries and primary references](StatCraft-preview69-contract.md)
- [REA evidence metadata](StatCraft-preview69-rea-evidence.json)
- [Machine-readable release verification](StatCraft-preview69-verification.json)
- [Demo project](StatCraft-attribute-capability-demo.mpx)

Older name-only saved results without a matching complete source fingerprint set require selecting the input columns again before rerun. Retained snapshots can still be viewed. Native stored result rendering/recomputation and full native MPX compatibility remain incomplete. Binomial/Poisson capability uses original diagnostics and bounded options; full native form geometry, option coverage and numerical equivalence remain unverified. No full-product completion percentage is established.

'''
(out/'StatCraft-preview-69-changes.md').write_text(text,encoding='utf-8')
for name in ['StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md']:
 p=out/name
 old=p.read_text(encoding='utf-8-sig') if p.exists() else ''
 if not old.startswith('# StatCraft preview69'):
  p.write_text(text+'---\n\nThe following sections are historical and have not been re-certified as current parity claims. Use the review above for the current work queue.\n\n'+old,encoding='utf-8')
print('Current handoff, feature audit, backlog and preview69 changelog updated.')
