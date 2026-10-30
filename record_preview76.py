"""Publish current preview76 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview76.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['capability_nonparametric_and_automated_tournament_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-76-capability-automated',
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
    'Nonparametric and Automated Capability Analysis (StatCraft.6): Distribution-free capability analysis '
    'using empirical percentiles (ISO 21747 Pp, Ppk, AIAG/VDA Cnp, Cnpk), automated multi-distribution '
    'goodness-of-fit tournament (Anderson-Darling test across Normal, Box-Cox, Weibull, Lognormal, Exponential, '
    'Gamma) with automated model selection, PE MDF dialogs, interactive Qt comparison chart with specification '
    'limits and empirical percentiles, session text reports, and MPX replay.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview76_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview76-contract.md',
    'changes': 'StatCraft-preview-76-changes.md',
    'review': 'StatCraft-Gemini-review-2026-10-24.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
