import json
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'outputs'
proof=json.loads((out/'StatCraft-preview80-verification.json').read_text(encoding='utf-8'))
t=proof['source_tests']
text=f'''# StatCraft preview80 — 27 October 2026

Current executable: **StatCraft.exe**, byte-identical to **StatCraft-preview80.exe**.

Added a unified DOE Planner inspired by Numiqo's guided workflow. Stat > DOE > DOE Planner now provides eleven families with isolated live run previews: full/fractional/general factorial, Plackett–Burman, CCD, Box–Behnken, Taguchi arrays, simplex centroid/lattice, constrained mixture vertices and custom D/I candidate-exchange designs. Supports typed factor levels, applicable replication/centers/blocks, generators/alpha/arrays, mixture bounds, model/run budgets and forbidden combinations. Create Worksheet preserves the current project and adds a uniquely named tab; plans persist in MPX. Existing response-surface fitting is verified on a planner-created design.

Added genuine XLSX export for a plan, current worksheet or all project worksheets. File > Convert MPX File to Excel independently converts MPX projects/supported MWX worksheets without replacing the open session or modifying source files. Numeric/text/date columns and missing cells are retained; formula-looking text remains literal. An independent Excel reader verified the exporter and all 1200 populated cells of quiz1.mpx.

Verification: **{t['unittest_passed']} tests passed, {t.get('skipped',0)} environment-limited hard-link skip, {proof['packaged_workflow_gates']} frozen workflow gates, {len(proof['mpx_fixtures'])} fresh MPX fixture checks**. Startup maximization/splash/project loading passed. {proof['source_archive_entries_byte_equal']} archived entries match current source; {proof['frozen_application_source']['application_modules_checked']} packaged application modules match compiled current source. Original quiz1.mpx remains unchanged.

- [Feature scope, scientific limits and references](StatCraft-preview80-contract.md)
- [REA website interaction evidence](StatCraft-preview80-rea-evidence.json)
- [Release verification](StatCraft-preview80-verification.json)
- [Eleven-family demonstration project](StatCraft-doe-planner-demo.mpx)
- [Actual planner UI](StatCraft-preview80-doe-planner.png)

This addition is useful for discoverability and planning, not a claim that the underlying design families are absent from StatCraft. Dedicated mixture response fitting, Taguchi signal-to-noise/noise-factor workflows and complete Numiqo analysis/optimization parity remain unfinished. Optimal selection is a bounded local exchange heuristic over a finite candidate set. Excel export includes worksheet data/current calculated values; native graphs, reports, constants, matrices and formulas are not converted.

Next priorities: use the new creation workflows as the basis for dedicated mixture and Taguchi analysis; add remaining DOE estimation and block options; verify existing worksheet/graph interactions against native behavior; continue numerical oracle comparisons. Full StatCraft parity and a product-wide completion percentage remain unverified.

'''
(out/'StatCraft-preview-80-changes.md').write_text(text,encoding='utf-8')
for name in ['StatCraft-handoff.md','StatCraft-parity-backlog.md','StatCraft-current-feature-audit.md']:
 p=out/name;old=p.read_text(encoding='utf-8-sig') if p.exists() else ''
 if not old.startswith('# StatCraft preview80'):
  p.write_text(text+'---\n\nHistorical notes follow; preview80 above is the current handoff. Older parity claims have not been re-certified.\n\n'+old,encoding='utf-8')
print('Preview80 handoff, backlog, audit and changelog updated.')
