"""Update manifest and release records for Preview 68: Tolerance Intervals (Stat > Quality Tools > Tolerance Intervals)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview68.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview68.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview68"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-68-tolerance-intervals'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview68.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Tolerance Intervals (Normal Distribution) (Stat > Quality Tools > Tolerance Intervals…): native StatCraft PE resource fidelity (1140-TOLERANCEINTERVALS.MDF, MenuID 41198, HelpID 88690; 1144-TOLERINTERVALOPTIONS.MDF, HelpID 88692; 1142-TOLERINTERVALGRAPHS.MDF, HelpID 88691), parametric normal tolerance intervals via exact noncentral-t (one-sided) and Howe's method (two-sided), distribution-free nonparametric tolerance intervals via order statistics with exact binomial coverage probability, raw data and summarized data modes (sample size, mean, standard deviation), two-sided, lower-bound, and upper-bound options, interactive comparison plot with raw observation jitter, sample mean marker, normal and nonparametric interval whisker bars, right-hand summary statistics card, and session window text reports"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['tolerance_intervals_packaged_verification'] = {
    'preview': 68,
    'feature': "Tolerance Intervals Native Parity",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '1140-TOLERANCEINTERVALS.MDF',
        '1144-TOLERINTERVALOPTIONS.MDF',
        '1142-TOLERINTERVALGRAPHS.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview68.")
