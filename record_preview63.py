"""Update manifest and release records for Preview 63: Time-Weighted Control Charts (EWMA, Moving Average, CUSUM)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview63.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview63.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview63"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-63-time-weighted-control-charts'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview63.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Time-Weighted Control Charts (Stat > Control Charts > Time-Weighted Charts > EWMA..., Moving Average..., CUSUM...): native StatCraft PE resource fidelity (0716-EWMADATASOURCE.MDF, 0836-MACHARTDATASOURCE.MDF, 1026-RCUSUMDATASOURCE.MDF, 1027-RCUSUMPLANANDTYPE.MDF, 1008-QCHARTPARAMETERS.MDF), dynamic and expanding control limits, historical mean and sigma parameters, estimation methods (pooled standard deviation, Rbar, Sbar, moving range), subgroup omissions, Fast Initial Response (FIR) and reset options for Tabular CUSUM, high-contrast chart rendering, interactive tooltips with sample sizes and values, session window text reports, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['time_weighted_control_charts_packaged_verification'] = {
    'preview': 63,
    'feature': "Time-Weighted Control Charts Native Parity (EWMA, MA, CUSUM)",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0716-EWMADATASOURCE.MDF',
        '0836-MACHARTDATASOURCE.MDF',
        '1026-RCUSUMDATASOURCE.MDF',
        '1027-RCUSUMPLANANDTYPE.MDF',
        '1008-QCHARTPARAMETERS.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview63.")
