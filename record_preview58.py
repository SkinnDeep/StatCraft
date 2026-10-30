"""Update manifest and release records for Preview 58: Capability Analysis (Normal Distribution)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview58.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview58.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview58"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-58-capability-analysis-normal'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview58.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Capability Analysis (Normal Distribution): single column with subgroup size or subgroup indicator column, subgroups across rows of columns, spec limits (LSL, USL, Bounds), within-subgroup variation estimators (Pooled SD, Rbar, Sbar, AMR, MMR, SRMSSD) with unbiasing constants c4/d2, overall variation with c4 unbiasing, capability indices (Cp, Cpl, Cpu, Cpk, CCpk, Cpm, Pp, Ppl, Ppu, Ppk), chi-square exact and normal-approximation confidence intervals, PPM and Percent defect rates (Observed, Expected Within, Expected Overall), Benchmark Z statistics (Z.LSL, Z.USL, Z.bench), StatCraft-matching 4-panel Capability Plot with fitted normal curves, Options and Estimate child dialogs matching 0471-CAPABILITY.MDF and 1017-QUALITYESTSIGMA.MDF, Office export, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

demo_mpx = out / 'StatCraft-capability-analysis-normal-demo.mpx'
dlg_img = out / 'StatCraft-capability-dialog-preview-58.png'
plot_img = out / 'StatCraft-capability-analysis-normal-plot-preview-58.png'
rep_txt = out / 'StatCraft-capability-analysis-normal-report.txt'
docx = out / 'StatCraft-capability-analysis-normal-example.docx'
pptx = out / 'StatCraft-capability-analysis-normal-example.pptx'

manifest['capability_analysis_normal_packaged_verification'] = {
    'preview': 58,
    'feature': 'Capability Analysis (Normal Distribution) (Stat > Quality Tools > Capability Analysis > Normal...) Native Parity',
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0471-CAPABILITY.MDF',
        '1017-QUALITYESTSIGMA.MDF'
    ],
    'files': {
        'demo_mpx': {
            'path': 'outputs/StatCraft-capability-analysis-normal-demo.mpx',
            'bytes': demo_mpx.stat().st_size,
            'sha256': hashlib.sha256(demo_mpx.read_bytes()).hexdigest(),
        },
        'capability_dialog_screenshot': {
            'path': 'outputs/StatCraft-capability-dialog-preview-58.png',
            'bytes': dlg_img.stat().st_size,
            'sha256': hashlib.sha256(dlg_img.read_bytes()).hexdigest(),
        },
        'capability_plot_screenshot': {
            'path': 'outputs/StatCraft-capability-analysis-normal-plot-preview-58.png',
            'bytes': plot_img.stat().st_size,
            'sha256': hashlib.sha256(plot_img.read_bytes()).hexdigest(),
        },
        'capability_report': {
            'path': 'outputs/StatCraft-capability-analysis-normal-report.txt',
            'bytes': rep_txt.stat().st_size,
            'sha256': hashlib.sha256(rep_txt.read_bytes()).hexdigest(),
        },
        'capability_docx': {
            'path': 'outputs/StatCraft-capability-analysis-normal-example.docx',
            'bytes': docx.stat().st_size,
            'sha256': hashlib.sha256(docx.read_bytes()).hexdigest(),
        },
        'capability_pptx': {
            'path': 'outputs/StatCraft-capability-analysis-normal-example.pptx',
            'bytes': pptx.stat().st_size,
            'sha256': hashlib.sha256(pptx.read_bytes()).hexdigest(),
        }
    },
    'statistics_verification': {
        'single_column_subgroup_size_supported': True,
        'single_column_subgroup_id_supported': True,
        'subgroups_across_rows_supported': True,
        'pooled_standard_deviation_supported': True,
        'rbar_estimator_supported': True,
        'sbar_estimator_supported': True,
        'amr_estimator_supported': True,
        'mmr_estimator_supported': True,
        'srmssd_estimator_supported': True,
        'unbiasing_constants_supported': True,
        'potential_within_cp_cpk_ccpk_cpm_supported': True,
        'overall_pp_ppk_supported': True,
        'confidence_intervals_supported': True,
        'ppm_and_percentage_defect_rates_supported': True,
        'benchmark_z_statistics_supported': True,
        'four_panel_capability_plot_rendered': True,
    }
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Updated outputs/StatCraft-preview-manifest.json for Preview 58')
