"""Publish current preview80 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview80.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['new_analysis_graphs_sources_statistical_integrity_mpx'] == 'passed'
assert smoke['multiple_variable_capability_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['doe_planner_eleven_families_live_preview_excel_converter_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-80-doe-planner-excel',
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

feature = (
    'Unified DOE planner with eleven design families, isolated live previews, typed factor levels, '
    'mixture bounds and D/I candidate exchange with forbidden combinations; existing regression '
    'tools retained; native XLSX project/worksheet export and independent MPX/MWX-to-Excel conversion. '
    'Dedicated mixture fitting and Taguchi robustness analysis remain incomplete.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview80_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview80-contract.md',
    'changes': 'StatCraft-preview-80-changes.md',
    'review': 'StatCraft-preview-80-changes.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
