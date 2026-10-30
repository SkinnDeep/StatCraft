import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview81-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview81 — 27 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview81.exe**.

Added Analyze Mixture Design and Predict under Stat > DOE > Mixture. Fits original linear/quadratic/special-cubic Scheffe models with fixed totals, no independent intercept, uncertainty/ANOVA when estimable, pure-error/lack-of-fit decomposition, residual plots and constrained mean/individual-response predictions. Model bounds are saved with the recipe and retain meaning through column edits.

Added Analyze Taguchi Design under Stat > DOE > Taguchi for static repeated-response data. Larger/smaller/classic nominal S/N, sample SD/ln(SD), response tables with deltas/tied ranks, marginal S/N settings, actual main-effects plots and optional estimable fixed-factor GLM models are implemented. Unavailable variation and saturated/aliased models receive explanations instead of fabricated inference.

Both forms use named positional source selectors. Reports, chart editing/capture, MPX save/reopen/rerun and source insert/move/rename/delete/undo are covered. Existing Excel conversion and all eleven DOE planning families remain covered by regression checks.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization/splash/project loading passed. {proof['source_archive_entries_byte_equal']} archived entries match current source; {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled current source. Original quiz1.mpx remains unchanged. The independent 1200-cell Excel comparison is retained preview80 evidence, not claimed as a newly repeated test.

- [Scope, statistical methods and remaining limits](StatCraft-preview81-contract.md)
- [Verified native REA dialog evidence](StatCraft-preview81-rea-evidence.json)
- [Release verification](StatCraft-preview81-verification.json)
- [Working mixture/Taguchi project](StatCraft-mixture-taguchi-demo.mpx)
- [Actual mixture residual plots](StatCraft-preview81-mixture.png)
- [Actual Taguchi main effects](StatCraft-preview81-taguchi.png)

Remaining major DOE work: dynamic Taguchi/noise-factor workflows and interactions; mixture process/block/covariate models, contour/ternary displays and optimization; further native options/storage and direct numerical oracle comparisons. Full native numerical/UI parity and a product-wide completion percentage remain unverified.

'''
(out/'StatCraft-preview-81-changes.md').write_text(text,encoding='utf-8')
for name in ['StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md']:
 p=out/name;old=p.read_text(encoding='utf-8-sig') if p.exists() else ''
 if not old.startswith('# StatCraft preview81'):
  p.write_text(text+'---\n\nHistorical notes follow; preview81 above is the current handoff. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview81 handoff, backlog, audit and changelog updated.')
