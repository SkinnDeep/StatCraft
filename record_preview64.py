"""Update manifest and release records for Preview 64: Rare Event Control Charts (G Chart & T Chart)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview64.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview64.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview64"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-64-rare-event-control-charts'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview64.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Rare Event Control Charts (Stat > Control Charts > Rare Event Charts > G..., T...): native StatCraft PE resource fidelity (0750-GCHARTDATASOURCE.MDF, 0751-GCHARTPARAMETERS.MDF, 0752-GCHARTTESTS.MDF, 1136-TCHARTDATASOURCE.MDF, 1137-TCHARTPARAMETERS.MDF, 1138-TCHARTTESTS.MDF), geometric distribution for opportunities between events, continuous median center line, exact probability control limits, Nelson/Kaminsky normalizing power transformation y = t^(1/(beta*3.6)) for Weibull/exponential intervals, Benneyan special cause cluster tests for rare events, session window text reports, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['rare_event_control_charts_packaged_verification'] = {
    'preview': 64,
    'feature': "Rare Event Control Charts Native Parity (G Chart, T Chart)",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0750-GCHARTDATASOURCE.MDF',
        '0751-GCHARTPARAMETERS.MDF',
        '0752-GCHARTTESTS.MDF',
        '1136-TCHARTDATASOURCE.MDF',
        '1137-TCHARTPARAMETERS.MDF',
        '1138-TCHARTTESTS.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview64.")
