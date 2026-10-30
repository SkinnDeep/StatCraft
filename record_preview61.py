"""Update manifest and release records for Preview 61: Attributes Control Charts (P, NP, C, U)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview61.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview61.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview61"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-61-attributes-control-charts'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview61.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Attributes Control Charts (Stat > Control Charts > Attributes Charts > P, NP, C, U): native StatCraft PE resource fidelity (0922-PCHARTDATASOURCE.MDF, 0876-NPCHARTDATASOURCE.MDF, 0472-CCHARTDATASOURCE.MDF, 1159-UCHARTDATASOURCE.MDF, 1000-QCHARTATTRIBUTEPARAMETERS.MDF, 1014-QCHARTTESTS4.MDF), proportions of defectives (P Chart) with constant or variable subgroup sizes, defect counts (NP Chart), defects per unit (C Chart), and variable exposure defect rates (U Chart), stepped and straight control limits, historical proportion and mean parameters, subgroup omission, Nelson special-cause tests 1, 2, 3, 4 with test violation numbering, high-contrast chart rendering, session window text reports, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['attribute_control_charts_packaged_verification'] = {
    'preview': 61,
    'feature': 'Attributes Control Charts (P, NP, C, U) Native Parity',
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0922-PCHARTDATASOURCE.MDF',
        '0876-NPCHARTDATASOURCE.MDF',
        '0472-CCHARTDATASOURCE.MDF',
        '1159-UCHARTDATASOURCE.MDF',
        '1000-QCHARTATTRIBUTEPARAMETERS.MDF',
        '1014-QCHARTTESTS4.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview61.")
