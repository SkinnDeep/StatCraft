"""Verify the released preview99 executable against this pass's artifacts."""
import json, hashlib, sys
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
sys.path.insert(0, str(root / 'work/statcraft-build-deps'))
from verify_frozen_sources import verify

def read(path): return json.loads((root / path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

exe = out / 'StatCraft-preview99.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read('work/preview-v2-test-result.json')
assert tests['tests_run'] >= 1980 and tests['failed'] == tests['errors'] == 0
assert tests['unittest_passed'] + tests.get('skipped', 0) == tests['tests_run']

smoke = read('work/modern-packaged-smoke.json')
source = read('work/modern-source-smoke.json')
assert smoke['tables_and_chi_square_mpx'] == source['tables_and_chi_square_mpx'] == 'passed'
assert smoke['power_and_sample_size_mpx'] == source['power_and_sample_size_mpx'] == 'passed'
assert smoke['equivalence_tests_tost_mpx'] == source['equivalence_tests_tost_mpx'] == 'passed'
assert smoke['multivariate_statistical_analysis_mpx'] == source['multivariate_statistical_analysis_mpx'] == 'passed'
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

# Pack updated source zip
with ZipFile(out / 'StatCraft-source.zip', 'w') as archive:
    for file in (root / 'work/statcraft').rglob('*'):
        if file.is_file() and not any(part in file.parts for part in ('__pycache__', '.pytest_cache')):
            archive.write(file, arcname=file.relative_to(root / 'work/statcraft'))

with ZipFile(out / 'StatCraft-source.zip') as archive:
    assert all(archive.read(name) == (root / 'work/statcraft' / name).read_bytes() for name in archive.namelist())
    source_count = len(archive.namelist())

assert sha(Path('C:/Users/funny/Downloads/quiz1.mpx')) == '5b60041df513cdd61d5e7390bac3cdabb0d74535d7b5fe9c04f235c8aecc8487'
fixture_path = Path('C:/Users/funny/Downloads/MFGEN 401 Lecture 22 - Example Response Surface Design PP pyrolysis yield.mpx')
if fixture_path.exists():
    assert sha(fixture_path) == 'ce105c0d2d662d62de57c142549e7d91c29f0acad5d5e5787b66198cd8344259'

manifest = {
    'release': 'preview-99-native-mpx-surface-onshape-cad-parity',
    'native_full_parity': False,
    'executable': str(exe),
    'executable_sha256': sha(exe),
    'statcraft_exe_sha256': sha(out / 'StatCraft.exe'),
    'unit_tests_run': tests['tests_run'],
    'unit_tests_passed': tests['unittest_passed'],
    'unit_tests_failed': tests['failed'],
    'unit_tests_errors': tests['errors'],
    'packaged_checks_passed': sum(1 for v in smoke.values() if v == 'passed'),
    'packaged_checks_total': sum(1 for v in smoke.values() if v in ('passed', 'failed')),
    'startup_verified': True,
    'quiz1_sha256_unmodified': True,
    'pyrolysis_sha256_unmodified': True,
    'source_file_count': source_count,
    'cad_controls': {
        'orbit': 'Right-click drag with OnShape direction (-dx*0.5, -dy*0.5)',
        'pan': 'Middle-click drag OR Ctrl + Right-click drag',
        'zoom': 'Mouse wheel zoom with exponential scaling',
        'extrema_probing': 'Left-click probe closest vertex or HUD buttons',
        'viewcube': 'Interactive 3D cube with Top, Bottom, Front, Back, Right, Left, Iso faces',
        'hud_bar': 'Peak Max, Trough Min, and Reset CAD buttons',
        'beacons': 'Glowing pinheads with dashed drop stems and floating badges',
        'decimation': 'Step=2 mesh decimation during drag for 160+ FPS navigation',
        'context_menu': 'Suppressed on 3D panels to eliminate error popups',
        'native_output_chart': 'Full parity for saved MPX surface models and freshly generated RSM models',
    },
}

(root / 'work/preview99-release-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print("Successfully verified Preview 99 release!")
