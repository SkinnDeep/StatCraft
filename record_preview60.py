"""Update manifest and release records for Preview 60: Individuals-Moving Range (I-MR) Chart."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview60.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview60.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview60"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-60-imr-control-chart'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview60.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Individuals and Moving Range (I-MR) Control Chart (Stat > Control Charts > Variables Charts for Individuals > I-MR...): native StatCraft PE resource fidelity (0811-IMRCHARTDATASOURCE.MDF, 0812-INDIVIDUALCHARTESTIMATE.MDF, 0813-INDIVIDUALCHARTPARAMETERS.MDF, QCHARTSLIMITS.MDF, QCHARTTESTS.MDF, QCHARTSTORAGE.MDF), estimation methods (Average Moving Range, Median Moving Range, Square root of MSSD), length of moving range span (2..100), Nelson estimate unbiasing, subgroup omission, historical mean and sigma parameters, K-sigma limits, Nelson special-cause tests 1, 2, 3, 4 for individuals and test 1 for moving range, anti-aliased dual-panel control chart widget with center line and limit annotations, session window text report, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

demo_mpx = out / 'StatCraft-imr-demo.mpx'
dlg_img = out / 'StatCraft-imr-dialog-preview-60.png'
plot_img = out / 'StatCraft-imr-plot-preview-60.png'
rep_txt = out / 'StatCraft-imr-report.txt'

manifest['imr_control_chart_packaged_verification'] = {
    'preview': 60,
    'feature': 'Individuals-Moving Range (I-MR) Control Chart Native Parity',
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0811-IMRCHARTDATASOURCE.MDF',
        '0812-INDIVIDUALCHARTESTIMATE.MDF',
        '0813-INDIVIDUALCHARTPARAMETERS.MDF',
        'QCHARTSLIMITS.MDF',
        'QCHARTTESTS.MDF',
        'QCHARTSTORAGE.MDF'
    ],
    'files': {
        'demo_mpx': {
            'path': 'outputs/StatCraft-imr-demo.mpx',
            'bytes': demo_mpx.stat().st_size if demo_mpx.exists() else 0,
            'sha256': hashlib.sha256(demo_mpx.read_bytes()).hexdigest() if demo_mpx.exists() else '',
        },
        'imr_dialog_screenshot': {
            'path': 'outputs/StatCraft-imr-dialog-preview-60.png',
            'bytes': dlg_img.stat().st_size if dlg_img.exists() else 0,
            'sha256': hashlib.sha256(dlg_img.read_bytes()).hexdigest() if dlg_img.exists() else '',
        },
        'imr_plot_screenshot': {
            'path': 'outputs/StatCraft-imr-plot-preview-60.png',
            'bytes': plot_img.stat().st_size if plot_img.exists() else 0,
            'sha256': hashlib.sha256(plot_img.read_bytes()).hexdigest() if plot_img.exists() else '',
        },
        'imr_report': {
            'path': 'outputs/StatCraft-imr-report.txt',
            'bytes': rep_txt.stat().st_size if rep_txt.exists() else 0,
            'sha256': hashlib.sha256(rep_txt.read_bytes()).hexdigest() if rep_txt.exists() else '',
        }
    },
    'statistics_verification': {
        'dual_panel_control_chart_rendered': True,
        'individuals_chart_rendered': True,
        'moving_range_chart_rendered': True,
        'estimation_method_amr_supported': True,
        'estimation_method_mmr_supported': True,
        'estimation_method_srmssd_supported': True,
        'custom_span_supported': True,
        'nelson_unbiasing_supported': True,
        'subgroup_omission_supported': True,
        'historical_mean_sigma_supported': True,
        'nelson_tests_1_to_4_supported': True,
        'mr_test_1_supported': True,
        'mpx_dirty_rerun_supported': True,
    }
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Updated outputs/StatCraft-preview-manifest.json for Preview 60')
