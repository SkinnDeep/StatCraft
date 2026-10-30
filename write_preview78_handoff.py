import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview78-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview78 — 24 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview78.exe**.

Reviewed and retained Gemini's preview70–77 work. This pass repairs actual chart display/report/export routing for seven newer analysis families, named MSA selection and saved column identity, paired lifetime/censor inputs, calculated reliability uncertainty and goodness of fit, actual automated-capability winner selection, all-trial agreement integrity and degenerate linearity inference. Unsupported plot editing controls are disabled rather than accepting changes their painters ignore.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates passed, {len(proof['mpx_fixtures'])} fresh MPX fixture checks passed**. Startup maximization/splash/project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match current source; {proof['frozen_application_source']['application_modules_checked']} packaged application modules match compiled current source. Bundled Qt/PySide/Shiboken imports/exports were checked. Original quiz1.mpx bytes remain unchanged.

- [Gemini changes review and next priorities](StatCraft-Gemini-review-2026-10-24.md)
- [Scope, statistical methods and remaining boundaries](StatCraft-preview78-contract.md)
- [Current REA evidence metadata](StatCraft-preview78-rea-evidence.json)
- [Release verification](StatCraft-preview78-verification.json)
- [Advanced-quality demonstration MPX](StatCraft-advanced-quality-demo.mpx)

Reliability confidence intervals are asymptotic observed-information/delta-method estimates. Censored AD, calibrated automated goodness-of-fit p-values, and verified Fleiss SE/Z/P are unavailable. Full native form geometry, chart object editing, numerical equivalence and native MPX result compatibility remain incomplete. Some old reliability results need their censor inputs selected again before rerun. A product-wide completion percentage has not been established.

'''
(out/'StatCraft-preview-78-changes.md').write_text(text,encoding='utf-8')
for name in ['StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md']:
 p=out/name;old=p.read_text(encoding='utf-8-sig') if p.exists() else ''
 if not old.startswith('# StatCraft preview78'):
  p.write_text(text+'---\n\nHistorical notes follow; the preview78 review above is the current handoff and work queue. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview78 handoff, backlog, audit and changelog updated.')
