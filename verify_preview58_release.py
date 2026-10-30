"""Final preview58 EXE, source and project verification."""
import json, hashlib, sys
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
sys.path.insert(0, str(root / 'work/statcraft-build-deps'))
from verify_frozen_sources import verify

def read(p): return json.loads((root / p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

exe = out / 'StatCraft-preview58.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')

tests = read('work/preview-v2-test-result.json')
assert tests['tests_run'] == 1089 and tests['failed'] == tests['errors'] == 0

smoke = read('work/modern-packaged-smoke.json')
assert smoke['frozen'] and smoke['capability_analysis_normal_dialogs_reports_plot_mpx'] == 'passed'

startup = read('work/startup-packaged-verified.json')
assert all(startup[k] for k in ('frozen', 'maximized', 'splash_dismissed', 'project_loaded'))

names = [
    'model-plots', 'optimizer', 'logistic', 'prediction', 'gage-rr', 'response-surface',
    'glm', 'data-preparation', 'output-workspace', 'graph-builder', 'individual-interval',
    'dotplot-variants', 'quiz1', 'boxplot-variants', 'histogram-variants',
]
fixtures = {name: read('work/' + name + '-packaged-verified.json') for name in names}
assert all(all(f[k] for k in ('frozen', 'original_unchanged', 'ui_rendered')) for f in fixtures.values())

with ZipFile(out / 'StatCraft-source.zip') as z:
    assert all(z.read(name) == (root / 'work/statcraft' / name).read_bytes() for name in z.namelist())
    source_count = len(z.namelist())

assert sha(Path('C:/Users/funny/Downloads/quiz1.mpx')) == '5b60041df513cdd61d5e7390bac3cdabb0d74535d7b5fe9c04f235c8aecc8487'

manifest = read('outputs/StatCraft-preview-manifest.json')
assert manifest['sha256'] == sha(exe) and manifest['release'] == 'preview-58-capability-analysis-normal' and manifest['canonical_executable_matches']

proof = dict(
    release='preview58',
    bytes=exe.stat().st_size,
    sha256=sha(exe),
    canonical_executable_matches=True,
    source_tests=tests,
    packaged_workflow_gates=sum(v == 'passed' for v in smoke.values()),
    startup=startup,
    mpx_fixtures=fixtures,
    source_archive_entries_byte_equal=source_count,
    frozen_application_source=verify(exe),
    original_quiz1_unchanged=True,
    full_native_parity=False,
)

(root / 'work/preview58-release-verified.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
(out / 'StatCraft-preview58-verification.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in proof.items() if k != 'mpx_fixtures'}, indent=2))
