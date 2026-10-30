"""Publish current preview92 verification metadata from fresh results."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

exe = out / 'StatCraft-preview92.exe'
assert sha(exe) == sha(out / 'StatCraft.exe')
tests = read(root / 'work/preview-v2-test-result.json')
assert tests['failed'] == tests['errors'] == 0
smoke = read(root / 'work/modern-packaged-smoke.json')
assert smoke['nonparametrics_statistical_tests_mpx'] == 'passed'
assert smoke['time_series_forecasting_models_mpx'] == 'passed'
assert smoke['native_model_reconstruction_mpx'] == 'passed'
assert smoke['mixture_joint_optimizer_mpx'] == 'passed'
assert smoke['response_surface_58_catalog_matrix_blocks_prediction_graphs_mpx'] == 'passed'
assert smoke['chart_hover_histograms_points_saved_native_layout_capture'] == 'passed'
assert smoke['native_mpx_saved_reports_graphs_gallery_capture_copy'] == 'passed'
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
    release='preview-92-nonparametric-statistical-tests',
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

features = [
    'Nonparametric 1-Sample Sign Test with exact binomial p-values and confidence intervals',
    'Nonparametric 1-Sample Wilcoxon Signed Rank Test with pseudo-median Walsh averages and confidence bounds',
    'Nonparametric Mann-Whitney Two-Sample Test with Hodges-Lehmann median difference and tie adjustments',
    'Nonparametric Kruskal-Wallis Test with H-statistic, tie correction, degrees of freedom, and per-group Z-scores',
    'Nonparametric Moods Median Test with contingency table, chi-square p-values, and 95% individual median CIs',
    'Nonparametric Friedman Test for randomized block designs with S-statistic, tie adjustments, and rank sums',
    'Nonparametric Runs Test for randomness around mean or custom cutoff with sequence metrics and Z-scores',
    'Nonparametric Paired Wilcoxon Signed Rank Test on paired differences',
    'High-DPI Nonparametric charts: Group Comparison Plots, Moods Median Plot with overall median reference, and Sequence Runs Charts',
    'Nonparametric Qt dialogs with dual-list column picker and variable validation under Stat > Nonparametrics',
    'Tracked Nonparametric analysis recipes and rerun invariance in MPX session history',
]
for f in features:
    if f not in manifest['supported']:
        manifest['supported'].append(f)

for path in (out / 'StatCraft-preview-manifest.json', root / 'work/StatCraft-preview-manifest.json'):
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Preview 92 manifest updated successfully')
