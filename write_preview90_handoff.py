import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
p=json.loads((out/'StatCraft-preview90-verification.json').read_text(encoding='utf-8'));t=p['source_tests']
text=f'''# StatCraft preview90 — 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview90.exe**.

StatCraft Preview 90 delivers seamless end-to-end reconstruction and execution of saved native MPX response-surface models across all core downstream analysis dialogs: Predict, Factorial Plots, Contour Plot, 3D Surface Plot, and Response Optimizer.

Native Model Downstream Reconstruction:
- Automatically discovers recovered native response-surface model setups upon opening native projects (e.g. `MFGEN 401 Lecture 22 - Example Response Surface Design PP pyrolysis yield.mpx`).
- Preserves native variable bindings via native UUIDs (`imported_variable_metadata`), surviving worksheet edits, column moves, and renames.
- Dynamically filters models by source worksheet: Worksheet "With 2 blocks" discovers its blocked models; Worksheet "With blocks removed" discovers its unblocked model.
- Predict: Computes point predictions, SE Fit, Confidence Intervals, and Prediction Intervals with individual manual inputs or worksheet column inputs.
- Factorial Plots: Computes and renders main effects and interaction plots across continuous covariates and discrete factors.
- Contour Plot: Computes 2D response contour surfaces across continuous variable pairs with customized hold values and contour palettes.
- 3D Surface Plot: Computes and renders 3D interactive response surfaces with rotatable camera controls and surface/wireframe display modes.
- Response Optimizer: Discovers recovered models to formulate single- or multi-response optimization goals (Maximize, Minimize, Target) and solves multi-variable desirability functions.
- Immutability: Original native streams, reports, and graphs remain 100% immutable; newly generated downstream analyses are saved into StatCraft session records (`origin: 'statcraft'`), supporting full MPX save/reopen cycles.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview90-contract.md)
- [Release verification](StatCraft-preview90-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''
(out/'StatCraft-preview-90-changes.md').write_text(text,encoding='utf-8')
for name in ('StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md'):
 path=out/name;old=path.read_text(encoding='utf-8-sig')
 if not old.startswith('# StatCraft preview90'):path.write_text(text+'\n---\n\nHistorical notes follow; preview90 above overrides older completed-feature gaps.\n\n'+old,encoding='utf-8')
print('Preview90 handoff and priority list updated')
