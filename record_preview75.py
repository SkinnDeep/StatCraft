"""Publish current preview75 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview75.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['reliability_distribution_analysis_right_censoring_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-75-reliability-distribution',
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
    'Streamlined Reliability / Survival Distribution Analysis (StatCraft.6): Parametric distribution '
    'fitting (Weibull, Lognormal, Exponential, Normal), arbitrary right-censoring support, Maximum Likelihood '
    'Estimation (MLE), Kaplan-Meier nonparametric survival curve estimation, MTTF calculation, B1-B90 life '
    'percentiles with 95% confidence intervals, session text reports, interactive Qt survival and hazard plot widget, '
    'and MPX project persistence.'
)
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['preview75_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview75-contract.md',
    'changes': 'StatCraft-preview-75-changes.md',
    'review': 'StatCraft-Gemini-review-2026-10-24.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
