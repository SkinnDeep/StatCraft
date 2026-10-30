"""Publish current preview70 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview70.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['capability_between_within_dialog_reports_plot_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-70-between-within-capability',
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
    'Between/Within Capability Analysis: subgroup mean moving range variance decomposition, '
    'StDev(Between/Within), StDev(Between), StDev(Within), and StDev(Overall), potential and overall '
    'capability indices (Cp, Cpk, Pp, Ppk, Cpm), confidence intervals, parts-per-million and percent performance '
    'tables, dual-curve overlay plot (Between/Within solid, Overall dashed), native dialog validation, and MPX rerun.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview70_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview70-contract.md',
    'changes': 'StatCraft-preview-70-changes.md',
    'review': 'StatCraft-Gemini-review-2026-10-23.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
