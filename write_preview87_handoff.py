import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview87-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview87 — 28 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview87.exe**.

The supplied pyrolysis MPX now opens all seven saved native output groups under their original worksheets. All sixteen saved graphs display, including contour regions, a rotatable 3D response surface, main effects, interactions, Pareto effects and residual plots. Multi-graph analyses have a chart selector. Coefficients, ANOVA, model summaries and regression equations read saved values instead of executing commands or silently refitting models. Read-only checks preserve their input bytes; save-copy retains native members without duplicating native outputs into the StatCraft session.

Response-surface creation gained the supplied available-design matrix and working center-point, alpha and replicate controls. Larger and arbitrary custom DOE run budgets were verified, including 17, 19, 24, 27, 32 and replicated 38-run designs. No blanket sixteen-run cap exists. Catalog restrictions that define mathematical design families still apply.

Limits: native analyses remain immutable snapshots, native model reruns and native graph editing are unavailable. Normal-probability plotting positions are reconstructed from saved residuals with an explicit warning; the saved distribution parameters are retained. Blocked and fractional response-surface creation remain unavailable and identified in the dialog. These changes do not establish full StatCraft parity or a product-wide completion percentage.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} environment-limited hard-link skip, **{proof['packaged_workflow_gates']} frozen workflow gates**, **{len(proof['mpx_fixtures'])} prior MPX fixtures**, plus the initial supplied native MPX with seven groups and sixteen charts. The file acquired additional saved outputs during verification; its latest saved version also passes with **{proof['latest_saved_native_mpx_verification']['native_groups']} groups and {proof['latest_saved_native_mpx_verification']['saved_graphs']} charts**. Source/frozen decoded saved-value digests match. Startup maximization, splash dismissal and project loading pass. {proof['source_archive_entries_byte_equal']} archived files match current source, and {proof['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and remaining limits](StatCraft-preview87-contract.md)
- [Evidence and REA inventory limitation](StatCraft-preview87-rea-evidence.json)
- [Release verification](StatCraft-preview87-verification.json)
- [Response-surface available-designs matrix](StatCraft-preview87-design-catalog.png)
- [Response-surface design settings](StatCraft-preview87-design-settings.png)
- [Imported contour output](StatCraft-preview87-native-contour.png)
- [Imported surface output](StatCraft-preview87-native-surface.png)

Next priorities: real blocked/fractional response-surface design generation; source-bound reconstruction of imported fitted models for prediction and fresh analyses; native stored-output coverage across more project files; joint process/composition and multi-response optimization; further worksheet and chart fidelity. Historical notes below retain prior work; their older parity statements do not override this scope.
'''
(out/'StatCraft-preview-87-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 p=out/name;old=p.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview87'):p.write_text(text+'\n---\n\n'+old,encoding='utf-8')
for source,target in [('work/doe87-catalog.png','StatCraft-preview87-design-catalog.png'),('work/doe87-designs.png','StatCraft-preview87-design-settings.png'),('work/preview87-native-packaged-contour.png','StatCraft-preview87-native-contour.png'),('work/preview87-native-packaged-surface.png','StatCraft-preview87-native-surface.png')]:shutil.copyfile(root/source,out/target)
print('Preview87 changes and handoff updated.')
