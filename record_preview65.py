"""Update manifest and release records for Preview 65: Multivariate Control Charts (T-Squared, Generalized Variance, MEWMA)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview65.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview65.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview65"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-65-multivariate-control-charts'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview65.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Multivariate Control Charts (Stat > Control Charts > Multivariate Charts > T²..., Generalized Variance..., Multivariate EWMA...): native StatCraft PE resource fidelity (1154-TSQUAREDDATASOURCE.MDF, 0753-GENVARDATASOURCE.MDF, 0856-MEWMADATASOURCE.MDF, 1007-QCHARTMULTIPARAMETERS.MDF), Hotelling's T² distance statistic with exact Beta (individual observations) and F (subgroup) distribution upper control limits, univariate component decomposition for out-of-control signals, Generalized Variance |S| chart with b1/b2 unbiasing factors, Multivariate EWMA (MEWMA) chart with dynamic covariance matrices and Prabhu-Runger calibrated ARL control limits, interactive Qt chart rendering, session window reports, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['multivariate_control_charts_packaged_verification'] = {
    'preview': 65,
    'feature': "Multivariate Control Charts Native Parity (T², Generalized Variance, MEWMA)",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '1154-TSQUAREDDATASOURCE.MDF',
        '0753-GENVARDATASOURCE.MDF',
        '0856-MEWMADATASOURCE.MDF',
        '1007-QCHARTMULTIPARAMETERS.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview65.")
