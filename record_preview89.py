"""Publish current preview89 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview89.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['mixture_joint_optimizer_mpx'] == 'passed'
assert smoke['response_surface_58_catalog_matrix_blocks_prediction_graphs_mpx']=='passed'
assert smoke['chart_hover_histograms_points_saved_native_layout_capture']=='passed'
assert smoke['native_mpx_saved_reports_graphs_gallery_capture_copy']=='passed'
assert smoke['frozen'] and smoke['new_analysis_graphs_sources_statistical_integrity_mpx'] == 'passed'
assert smoke['multiple_variable_capability_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['doe_planner_eleven_families_live_preview_excel_converter_mpx'] == 'passed'
assert smoke['mixture_taguchi_models_prediction_dialogs_graphs_sources_mpx'] == 'passed'
assert smoke['dynamic_taguchi_slopes_sn_reference_dialog_graphs_sources_mpx'] == 'passed'
assert smoke['mixture_contours_optimizer_constraints_dialog_graphs_sources_mpx'] == 'passed'
assert smoke['mixture_multiple_desirability_interactive_profiles_reoptimize_sources_mpx'] == 'passed'
assert smoke['mixture_process_blocks_covariates_fit_prediction_dialogs_sources_mpx'] == 'passed'
assert smoke['mixture_process_conditional_contours_optimizer_coded_holds_intervals_sources_mpx'] == 'passed'

manifest = read(out / 'StatCraft-preview-manifest.json')
manifest.update(
    release='preview-89-joint-mixture-process-optimizer-and-native-models',
    built_at=datetime.now(timezone.utc).isoformat(),
    executable=exe.name,
    bytes=exe.stat().st_size,
    sha256=sha(exe),
    canonical_executable_matches=True,
    reverse_engineering_complete=False,
    full_parity_verified=False,
    source_tests=tests,
    packaged_smoke_test=smoke,
)
manifest['source_archive'] = {
    'file': 'StatCraft-source.zip',
    'bytes': (out / 'StatCraft-source.zip').stat().st_size,
    'sha256': sha(out / 'StatCraft-source.zip'),
}

feature = ('Joint mixture and continuous process response optimization with interactive multi-panel prediction profiles, deterministic multi-start SLSQP search, model-based CI/PI uncertainty, and declarative recovery of saved native MPX response-surface models and graph appearance editing. Global optimality and full native equivalence remain unverified.')
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['remaining']=['Broader native MPX output/model reconstruction and imported text/date/type/worksheet structural writes','Remaining specialty capability/control/MSA hover coverage, and broader axis/UI fidelity','Further DOE options and coupled multiresponse optimization workflows','Macros and additional integrations','Independent comprehensive native numerical and UI comparisons']

manifest['preview89_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview89-contract.md',
    'changes': 'StatCraft-preview-89-changes.md',
    'review': 'StatCraft-preview-89-changes.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))
