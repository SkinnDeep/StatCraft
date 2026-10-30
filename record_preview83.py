"""Publish current preview83 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview83.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['new_analysis_graphs_sources_statistical_integrity_mpx'] == 'passed'
assert smoke['multiple_variable_capability_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['doe_planner_eleven_families_live_preview_excel_converter_mpx'] == 'passed'
assert smoke['mixture_taguchi_models_prediction_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['dynamic_taguchi_slopes_sn_reference_dialog_graphs_sources_mpx'] == 'passed'
assert smoke['mixture_contours_optimizer_constraints_dialog_graphs_sources_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-83-mixture-exploration',
    built_at=datetime.now(timezone.utc).isoformat(),
    executable=exe.name,
    bytes=exe.stat().st_size,
    sha256=sha(exe),
    canonical_executable_matches=True,
    reverse_engineering_complete=False,
    full_parity_verified=False,
    source_tests=tests,
    packaged_smoke_test=smoke,
)
manifest['source_archive'] = {
    'file': 'StatCraft-source.zip',
    'bytes': (out / 'StatCraft-source.zip').stat().st_size,
    'sha256': sha(out / 'StatCraft-source.zip'),
}

feature = ('Mixture ternary contour slices with held components, exact clipped region and interpolated bands; '
           'constrained single-response min/max/target optimizer with uncertainty, tested dialogs and source-bound MPX reruns. '
           'Nonlinear global optimality, multiresponse desirability and native full equivalence unverified.')
manifest['supported']=[item.replace('Dynamic Taguchi and full native equivalence remain incomplete.', 'Further Taguchi workflows and full native equivalence remain incomplete.') for item in manifest['supported']]
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview83_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview83-contract.md',
    'changes': 'StatCraft-preview-83-changes.md',
    'review': 'StatCraft-preview-83-changes.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))

