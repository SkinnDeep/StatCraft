"""Publish current preview73 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview73.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['shewhart_extended_limits_warning_bands_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-73-shewhart-extended-limits',
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
    'Shewhart Extended Limits and Warning Bands (StatCraft.6): Multi-sigma limits (K values such as [1, 2, 3] or [2, 3]), '
    'dashed amber warning limits (UWL, LWL) at 2 sigma, zone boundary bands (Zones A, B, C), QCHARTSLIMITS Tab 3 dialog fidelity, '
    'Xbar-R, Xbar-S, and I-MR session text reports, interactive Qt chart callouts, and full MPX project persistence and replay.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview73_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview73-contract.md',
    'changes': 'StatCraft-preview-73-changes.md',
    'review': 'StatCraft-Gemini-review-2026-10-23.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
