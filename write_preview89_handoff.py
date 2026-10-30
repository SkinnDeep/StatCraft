import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
p=json.loads((out/'StatCraft-preview89-verification.json').read_text(encoding='utf-8'));t=p['source_tests']
text=f'''# StatCraft preview89 — 28 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview89.exe**.

StatCraft Preview 89 delivers joint constrained response optimization of mixture compositions with continuous process variables, interactive multi-panel prediction profiles, and declarative recovery and appearance editing of saved native MPX response-surface models.

Joint Mixture and Process Optimizer:
- Combines continuous process variables and component mixture constraints in a single optimization workflow under Stat > DOE > Mixture > Joint Mixture and Process Optimizer…
- Multi-start deterministic SLSQP algorithm explores interior and boundary vertices, ranking feasible solutions against the specified goal (Maximize, Minimize, or Target) while maintaining exact mixture closure.
- Prediction profiles display response changes while varying individual process variables or transferring mass between paired components.
- Uncertainty intervals (SE Fit, Confidence Intervals, and Prediction Intervals) are evaluated directly from the complete fitted response-surface model.
- Saved recipes maintain source column bindings across column moves, renames, deletions, and MPX project save/reopen cycles.

Native Model Recovery and Graph Editing:
- Declaratively reads saved native response-surface model objects from native MPX project streams without invoking native StatCraft executables or macros.
- Fresh StatCraft fits independently reproduce saved native regression coefficients within machine precision (< 10⁻¹³).
- In-place appearance editing for saved native MPX graphs: contour palette overrides, symbol shapes/colors, bar fills, and 3D surface camera controls.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview89-contract.md)
- [Authenticated native resources](StatCraft-preview89-rea-evidence.json)
- [Release verification](StatCraft-preview89-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; reconstructing imported native models for fresh analyses; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''
(out/'StatCraft-preview-89-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 path=out/name;old=path.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview89'):path.write_text(text+'\n---\n\nHistorical notes follow; preview89 above overrides older completed-feature gaps.\n\n'+old,encoding='utf-8')
print('Preview89 handoff and priority list updated')
