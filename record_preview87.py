"""Publish current preview87 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview87.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
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
    release='preview-87-native-mpx-saved-output-and-doe-dialogs',
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

feature = ('Native MPX stored report and graph decoding, saved contour/surface meshes, multi-graph galleries, native-style response-surface availability and design settings, and flexible custom run-budget verification. Native models remain immutable snapshots and full native parity is unverified.')
manifest['supported']=[item.replace('Dynamic Taguchi and full native equivalence remain incomplete.', 'Further Taguchi workflows and full native equivalence remain incomplete.') for item in manifest['supported']]
manifest['supported']=[item.replace('Extended-model contours/optimization, random blocks, custom terms and native equivalence remain incomplete.', 'Conditional contours/optimization added in preview87; random blocks, custom terms and native equivalence remain incomplete.') for item in manifest['supported']]
if feature not in manifest['supported']:
    manifest['supported'].append(feature)

manifest['remaining']=[item.replace('Stored native output rendering/recomputation,', 'Broader native output format coverage, native model recomputation and graph editing,') for item in manifest.get('remaining',[])]

manifest['preview87_verification'] = {
    'native_full_parity': False,
    'contract': 'StatCraft-preview87-contract.md',
    'changes': 'StatCraft-preview-87-changes.md',
    'review': 'StatCraft-preview-87-changes.md',
}

for path in [out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json']:
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

print(json.dumps({'release': manifest['release'], 'sha256': manifest['sha256'], 'tests': tests}, indent=2))

