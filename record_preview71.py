"""Publish current preview71 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview71.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['acceptance_control_chart_dialog_reports_plot_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-71-acceptance-control-charts',
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
    'Acceptance Control Charts (ACC, StatCraft.6): specification-based acceptance limits (UACL, LACL), '
    'acceptable process levels (APLU, APLL), producer risk alpha and allowable fraction nonconforming delta, '
    'process capability Cp excess verification, sigma estimation (pooled, Rbar, Sbar, historical), '
    'out-of-acceptance signal flag 1, native dialogs, session reports, interactive Qt chart, and MPX project rerun.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview71_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview71-contract.md',
    'changes': 'StatCraft-preview-71-changes.md',
    'review': 'StatCraft-Gemini-review-2026-10-23.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
