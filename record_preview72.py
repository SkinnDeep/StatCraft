"""Publish current preview72 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview72.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['capability_aiag_vda_machine_dialog_reports_plot_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-72-aiag-vda-capability',
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
    'AIAG/VDA Capability Framework (StatCraft.6): Unified AIAG/VDA standardized nomenclature '
    '(Cm, Cmk, Cbw, Cbwk, Pp, Ppk), Machine Capability study (Cm/Cmk) using within-sample variation '
    'under stable single-machine conditions, Between/Within AIAG/VDA capability (Cbw/Cbwk), two-sided '
    'and one-sided confidence intervals, PE dialog nomenclature toggle, session report sections, '
    'interactive Qt chart labels, and MPX replay.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview72_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview72-contract.md',
    'changes': 'StatCraft-preview-72-changes.md',
    'review': 'StatCraft-Gemini-review-2026-10-23.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
