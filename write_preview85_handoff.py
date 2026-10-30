import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview85-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview85 — 28 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview85.exe**.

Added Analyze Mixture with Process Variables and Predict with Process Variables under Stat > DOE > Mixture. Scheffe mixture terms are crossed with linear/quadratic coded process terms; fixed block effects and additive coded covariates are supported. Named role selectors, optional process coding, actual residual graphs, coefficient/overall ANOVA and estimable pure-error/lack-of-fit reports, and complete-role predictions with CI/PI work together.

Recipes snapshot bounds and process/covariate coding and preserve all physical source columns through moves/renames, MPX save/reopen/rerun and deletion/Undo. Joint incomplete rows retain their original worksheet identities. Rank-confounded/saturated models and unseen prediction block levels fail explicitly. The extended model uses a distinct schema so component-only optimizers/contours cannot silently discard additional roles.

Seven retained REA native resource payloads were authenticated. Native covariate semantics for mixture models remain unobserved; additive covariates are an authored extension. Static forms do not establish runtime/default/numerical equivalence.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization, splash dismissal and project loading passed. {proof['source_archive_entries_byte_equal']} archived source entries match current files; {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled current source. Original quiz1.mpx remains unchanged. The independent 1200-cell Excel comparison remains historical preview80 evidence.

- [Scope, methods and remaining limits](StatCraft-preview85-contract.md)
- [Authenticated retained REA evidence](StatCraft-preview85-rea-evidence.json)
- [Release verification](StatCraft-preview85-verification.json)
- [Working mixture/process MPX](StatCraft-mixture-process-demo.mpx)
- [Actual residual diagnostics](StatCraft-preview85-residuals.png)
- [Actual model dialog](StatCraft-preview85-dialog.png)
- [Actual prediction dialog](StatCraft-preview85-prediction-dialog.png)

Next priorities: extended-model contours/optimization at explicit process settings; crossed mixture/process design creation and native custom-term/storage options; remaining Taguchi reference/interactions/noise-factor workflows; worksheet/graph fidelity, including residual-axis formatting; native numerical oracle comparisons. Complete native numerical/UI parity and a product-wide completion percentage remain unverified.
'''
(out/'StatCraft-preview-85-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 p=out/name;old=p.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview85'):
  p.write_text(text+'\n---\n\nHistorical notes follow; preview85 above is current. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview85 changes, handoff and backlog updated.')
