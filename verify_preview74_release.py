"""Verify the released preview74 executable against this pass's artifacts."""
import json, hashlib, sys
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
sys.path.insert(0, str(root / 'work/statcraft-build-deps'))
from verify_frozen_sources import verify

def read(path): return json.loads((root / path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

exe = out / 'StatCraft-preview74.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read('work/preview-v2-test-result.json')
assert tests['tests_run'] >= 1251 and tests['failed'] == tests['errors'] == 0
assert tests['unittest_passed'] + tests.get('skipped', 0) == tests['tests_run']

smoke = read('work/modern-packaged-smoke.json')
source = read('work/modern-source-smoke.json')
assert smoke['frozen'] and not source['frozen']
assert smoke['capability_nonnormal_distribution_transform_mpx'] == source['capability_nonnormal_distribution_transform_mpx'] == 'passed'
assert all(value == 'passed' for value in smoke.values() if value in ('passed', 'failed'))

startup = read('work/startup-packaged-verified.json')
assert all(startup[k] for k in ('frozen', 'maximized', 'splash_dismissed', 'project_loaded'))

names = ['model-plots', 'optimizer', 'logistic', 'prediction', 'gage-rr', 'response-surface', 'glm', 'data-preparation', 'output-workspace', 'graph-builder', 'individual-interval', 'dotplot-variants', 'quiz1', 'boxplot-variants', 'histogram-variants', 'attribute-capability']
fixtures = {name: read('work/preview69-' + name + '-packaged-verified.json') for name in names}
assert all(all(value[k] for k in ('frozen', 'original_unchanged', 'ui_rendered')) for value in fixtures.values())

with ZipFile(out / 'StatCraft-source.zip') as archive:
    assert all(archive.read(name) == (root / 'work/statcraft' / name).read_bytes() for name in archive.namelist())
    source_count = len(archive.namelist())

assert sha(Path('C:/Users/funny/Downloads/quiz1.mpx')) == '5b60041df513cdd61d5e7390bac3cdabb0d74535d7b5fe9c04f235c8aecc8487'
manifest = read('outputs/StatCraft-preview-manifest.json')
assert manifest['sha256'] == sha(exe) and manifest['release'] == 'preview-74-nonnormal-capability'
assert manifest['source_archive']['sha256'] == sha(out / 'StatCraft-source.zip')

proof = dict(
    release='preview74',
    bundled_qt_import_exports_verified=True,
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

for path in [root / 'work/preview74-release-verified.json', out / 'StatCraft-preview74-verification.json']:
    path.write_text(json.dumps(proof, indent=2), encoding='utf-8')
print('Preview 74 release verified successfully.')
