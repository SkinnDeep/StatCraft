"""Verify the released preview92 executable against this pass's artifacts."""
import json, hashlib, sys
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
sys.path.insert(0, str(root / 'work/statcraft-build-deps'))
from verify_frozen_sources import verify

def read(path): return json.loads((root / path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

exe = out / 'StatCraft-preview92.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read('work/preview-v2-test-result.json')
assert tests['tests_run'] >= 1910 and tests['failed'] == tests['errors'] == 0
assert tests['unittest_passed'] + tests.get('skipped', 0) == tests['tests_run']

smoke = read('work/modern-packaged-smoke.json')
source = read('work/modern-source-smoke.json')
assert smoke['nonparametrics_statistical_tests_mpx'] == source['nonparametrics_statistical_tests_mpx'] == 'passed'
assert smoke['time_series_forecasting_models_mpx'] == source['time_series_forecasting_models_mpx'] == 'passed'
assert smoke['native_model_reconstruction_mpx'] == source['native_model_reconstruction_mpx'] == 'passed'
assert smoke['mixture_joint_optimizer_mpx'] == source['mixture_joint_optimizer_mpx'] == 'passed'
assert smoke['native_mpx_saved_reports_graphs_gallery_capture_copy'] == source['native_mpx_saved_reports_graphs_gallery_capture_copy'] == 'passed'
assert smoke['frozen'] and not source['frozen']
assert smoke['new_analysis_graphs_sources_statistical_integrity_mpx'] == source['new_analysis_graphs_sources_statistical_integrity_mpx'] == 'passed'
assert smoke['multiple_variable_capability_dialogs_graphs_sources_mpx'] == source['multiple_variable_capability_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['doe_planner_eleven_families_live_preview_excel_converter_mpx'] == source['doe_planner_eleven_families_live_preview_excel_converter_mpx'] == 'passed'
assert smoke['mixture_taguchi_models_prediction_dialogs_graphs_sources_mpx'] == source['mixture_taguchi_models_prediction_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['dynamic_taguchi_slopes_sn_reference_dialog_graphs_sources_mpx'] == source['dynamic_taguchi_slopes_sn_reference_dialog_graphs_sources_mpx'] == 'passed'
assert smoke['mixture_contours_optimizer_constraints_dialog_graphs_sources_mpx'] == source['mixture_contours_optimizer_constraints_dialog_graphs_sources_mpx'] == 'passed'
assert smoke['mixture_multiple_desirability_interactive_profiles_reoptimize_sources_mpx'] == source['mixture_multiple_desirability_interactive_profiles_reoptimize_sources_mpx'] == 'passed'
assert smoke['mixture_process_blocks_covariates_fit_prediction_dialogs_sources_mpx'] == source['mixture_process_blocks_covariates_fit_prediction_dialogs_sources_mpx'] == 'passed'
assert smoke['mixture_process_conditional_contours_optimizer_coded_holds_intervals_sources_mpx'] == source['mixture_process_conditional_contours_optimizer_coded_holds_intervals_sources_mpx'] == 'passed'
assert all(value == 'passed' for value in smoke.values() if value in ('passed', 'failed'))

startup = read('work/startup-packaged-verified.json')
assert all(startup[k] for k in ('frozen', 'maximized', 'splash_dismissed', 'project_loaded'))

names = ['model-plots', 'optimizer', 'logistic', 'prediction', 'gage-rr', 'response-surface', 'glm', 'data-preparation', 'output-workspace', 'graph-builder', 'individual-interval', 'dotplot-variants', 'quiz1', 'boxplot-variants', 'histogram-variants', 'attribute-capability', 'advanced-quality', 'multiple-capability', 'doe-planner', 'mixture-taguchi', 'dynamic-taguchi', 'mixture-exploration', 'mixture-multi', 'mixture-process', 'mixture-condition', 'surface-catalog']
fixtures = {name: read('work/preview92-' + name + '-packaged-verified.json') for name in names}
assert all(all(value[k] for k in ('frozen', 'original_unchanged', 'ui_rendered')) for value in fixtures.values())

with ZipFile(out / 'StatCraft-source.zip') as archive:
    assert all(archive.read(name) == (root / 'work/statcraft' / name).read_bytes() for name in archive.namelist())
    source_count = len(archive.namelist())

assert sha(Path('C:/Users/funny/Downloads/quiz1.mpx')) == '5b60041df513cdd61d5e7390bac3cdabb0d74535d7b5fe9c04f235c8aecc8487'
fixture_path = Path('C:/Users/funny/Downloads/MFGEN 401 Lecture 22 - Example Response Surface Design PP pyrolysis yield.mpx')
if fixture_path.exists():
    assert sha(fixture_path) == 'ce105c0d2d662d62de57c142549e7d91c29f0acad5d5e5787b66198cd8344259'

manifest = read('outputs/StatCraft-preview-manifest.json')
assert manifest['sha256'] == sha(exe) and manifest['release'] == 'preview-92-nonparametric-statistical-tests'
assert manifest['source_archive']['sha256'] == sha(out / 'StatCraft-source.zip')

assert 'verified without export truncation' in (root / 'work/preview92-qt-dlls-verified.log').read_text(encoding='utf-8-sig')
quiz_excel = read('work/preview80-quiz1-excel-verified.json')
assert quiz_excel['conversion_passed'] and quiz_excel['original_unchanged'] and quiz_excel['cells_compared'] == 1200
proof = dict(
    original_quiz1_excel_conversion=quiz_excel,
    release='preview92',
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

for path in [root / 'work/preview92-release-verified.json', out / 'StatCraft-preview92-verification.json']:
    path.write_text(json.dumps(proof, indent=2), encoding='utf-8')
print('Preview 92 release verified successfully.')
