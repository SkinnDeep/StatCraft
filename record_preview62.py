"""Update manifest and release records for Preview 62: Laney P' and Laney U' Control Charts."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview62.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview62.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview62"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-62-laney-control-charts'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview62.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Laney P' and Laney U' Control Charts (Stat > Control Charts > Attributes Charts > Laney P'..., Laney U'...): native StatCraft PE resource fidelity (0959-PPRIMECHARTDATASOURCE.MDF, 1161-UPRIMECHARTDATASOURCE.MDF, 1000-QCHARTATTRIBUTEPARAMETERS.MDF, 1014-QCHARTTESTS4.MDF), overdispersion and underdispersion Sigma Z adjustment based on moving range of standardized z-scores, stepped and straight adjusted limits, historical proportion and mean parameters, subgroup omission, Nelson special-cause tests 1, 2, 3, 4, high-contrast chart rendering, session window text reports with Sigma Z display, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['laney_control_charts_packaged_verification'] = {
    'preview': 62,
    'feature': "Laney P' and Laney U' Control Charts Native Parity",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0959-PPRIMECHARTDATASOURCE.MDF',
        '1161-UPRIMECHARTDATASOURCE.MDF',
        '1000-QCHARTATTRIBUTEPARAMETERS.MDF',
        '1014-QCHARTTESTS4.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview62.")
