"""Update manifest and release records for Preview 67: Type 1 Gage Study (Stat > Quality Tools > Gage Study > Type 1 Gage Study)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview67.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview67.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview67"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-67-type1-gage-study'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview67.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Type 1 Gage Study (Stat > Quality Tools > Gage Study > Type 1 Gage Study…): native StatCraft PE resource fidelity (1158-TYPE1GAGESTUDY.MDF, MenuID 41127, HelpID 88670; 1157-TYPE1GAGEOPTIONS.MDF, HelpID 88669; 1156-TYPE1GAGEINFO.MDF, HelpID 88668), single standard part repeated measurement capability analysis, Cg (repeatability capability index), Cgk (centering and bias capability index), %Var (Repeatability) and %Var (Repeatability and Bias), one-sample t-test for bias, Gage Info tracking (gage name, date, reported by, misc), specification limit options (tolerance, LSL only, USL only), interactive run chart with reference, mean, and +/-0.10*Tol tolerance boundary lines, right-hand summary statistics card, and session window text reports"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

manifest['type1_gage_packaged_verification'] = {
    'preview': 67,
    'feature': "Type 1 Gage Study Native Parity",
    'native_full_parity': False,
    'mdf_resources_verified': [
        '1158-TYPE1GAGESTUDY.MDF',
        '1157-TYPE1GAGEOPTIONS.MDF',
        '1156-TYPE1GAGEINFO.MDF',
    ],
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
(root / 'work/StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Manifest updated successfully for preview67.")
