"""Publish current preview69 verification metadata from fresh results."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[2];out=root/'outputs'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
exe=out/'StatCraft-preview69.exe'
assert sha(exe)==sha(out/'StatCraft.exe')
tests=read(root/'work/preview-v2-test-result.json')
assert tests['failed']==tests['errors']==0
smoke=read(root/'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['attribute_capability_dialog_graph_mpx_bindings']=='passed'
manifest=read(out/'StatCraft-preview-manifest.json')
manifest.update(release='preview-69-attribute-capability-source-bindings',built_at=datetime.now(timezone.utc).isoformat(),executable=exe.name,bytes=exe.stat().st_size,sha256=sha(exe),canonical_executable_matches=True,reverse_engineering_complete=False,full_parity_verified=False,source_tests=tests,packaged_smoke_test=smoke)
manifest['source_archive']={'file':'StatCraft-source.zip','bytes':(out/'StatCraft-source.zip').stat().st_size,'sha256':sha(out/'StatCraft-source.zip')}
for feature in [
 'Binomial and Poisson Capability Analysis: named count/sample-size inputs, aligned missing rows, pooled rates, exact confidence intervals, P/U stability diagnostics, cumulative and sample-size charts, readable reports and MPX reruns. Full native option/geometry parity unverified.',
 'Source-column identity for newer capability, control-chart, Pareto and tolerance procedures across moves, renames, deletion/undo and MPX reopen. Legacy results require verified fingerprints before migration.',
 'Actual output-window routing for newer dedicated charts and preserved renderer minimum heights; Type 1 Gage rejects zero measurement variation.'
]:
 if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['preview69_verification']={'native_full_parity':False,'rea_evidence':'StatCraft-preview69-rea-evidence.json','contract':'StatCraft-preview69-contract.md','review':'StatCraft-Gemini-review-2026-10-23.md'}
for path in [out/'StatCraft-preview-manifest.json',root/'work/StatCraft-preview-manifest.json']:
 path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'release':manifest['release'],'sha256':manifest['sha256'],'tests':tests},indent=2))
