"""Update manifest and release records for Preview 66: Pareto Chart (Stat > Quality Tools > Pareto Chart)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview66.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview66.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview66"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-66-pareto-chart'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview66.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Pareto Chart (Stat > Quality Tools > Pareto Chart…): native StatCraft PE resource fidelity (0372-AMPARETOCHART.MDF, MenuID 41210), raw observation mode and summarized table frequency mode, descending defect ranking, cumulative percentage curve, configurable combining threshold ('Other' category for defects beyond 95% cumulative), dual count and percentage Y-axes, embedded bottom category-count-percent-cum% data table, session window text reports, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['pareto_chart_packaged_verification'] = {
    'preview': 66,
    'feature': "Pareto Chart Native Parity",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0372-AMPARETOCHART.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview66.")
