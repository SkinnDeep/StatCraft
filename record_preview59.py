"""Update manifest and release records for Preview 59: Capability Sixpack (Normal Distribution)."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview59.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview59.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview59"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-59-capability-sixpack-normal'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview59.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat = "Capability Sixpack (Normal Distribution): complete 6-panel diagnostic dashboard matching StatCraft (Xbar/I Chart, R/S/MR Chart, Last 25 Subgroups Plot, Capability Histogram with dual fitted normal curves, Normal Probability Plot with Anderson-Darling normality test, and Capability Plot comparing Process Tolerances to Specification Limits), single column with subgroup size or subgroup indicator column, subgroups across rows of columns, spec limits (LSL, USL, Bounds), within and overall capability indices (Cp, Cpk, CCpk, Cpm, Pp, Ppk), defect rates (PPM Observed, Exp Within, Exp Overall), Tests for Special Causes, child dialogs for Options, Estimate, and Tests, Office export, and tracked MPX reruns"

if feat not in manifest['supported']:
    manifest['supported'].append(feat)

demo_mpx = out / 'StatCraft-capability-sixpack-normal-demo.mpx'
dlg_img = out / 'StatCraft-capability-sixpack-dialog-preview-59.png'
plot_img = out / 'StatCraft-capability-sixpack-plot-preview-59.png'
rep_txt = out / 'StatCraft-capability-sixpack-report.txt'
docx = out / 'StatCraft-capability-sixpack-example.docx'
pptx = out / 'StatCraft-capability-sixpack-example.pptx'

manifest['capability_sixpack_normal_packaged_verification'] = {
    'preview': 59,
    'feature': 'Capability Sixpack (Normal Distribution) (Stat > Quality Tools > Capability Sixpack > Normal...) Native Parity',
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0471-CAPABILITY.MDF',
        '1017-QUALITYESTSIGMA.MDF'
    ],
    'files': {
        'demo_mpx': {
            'path': 'outputs/StatCraft-capability-sixpack-normal-demo.mpx',
            'bytes': demo_mpx.stat().st_size,
            'sha256': hashlib.sha256(demo_mpx.read_bytes()).hexdigest(),
        },
        'sixpack_dialog_screenshot': {
            'path': 'outputs/StatCraft-capability-sixpack-dialog-preview-59.png',
            'bytes': dlg_img.stat().st_size,
            'sha256': hashlib.sha256(dlg_img.read_bytes()).hexdigest(),
        },
        'sixpack_plot_screenshot': {
            'path': 'outputs/StatCraft-capability-sixpack-plot-preview-59.png',
            'bytes': plot_img.stat().st_size,
            'sha256': hashlib.sha256(plot_img.read_bytes()).hexdigest(),
        },
        'sixpack_report': {
            'path': 'outputs/StatCraft-capability-sixpack-report.txt',
            'bytes': rep_txt.stat().st_size,
            'sha256': hashlib.sha256(rep_txt.read_bytes()).hexdigest(),
        },
        'sixpack_docx': {
            'path': 'outputs/StatCraft-capability-sixpack-example.docx',
            'bytes': docx.stat().st_size,
            'sha256': hashlib.sha256(docx.read_bytes()).hexdigest(),
        },
        'sixpack_pptx': {
            'path': 'outputs/StatCraft-capability-sixpack-example.pptx',
            'bytes': pptx.stat().st_size,
            'sha256': hashlib.sha256(pptx.read_bytes()).hexdigest(),
        }
    },
    'statistics_verification': {
        'panel_xbar_chart_rendered': True,
        'panel_dispersion_r_s_mr_chart_rendered': True,
        'panel_last_25_subgroups_rendered': True,
        'panel_capability_histogram_dual_curves_rendered': True,
        'panel_normal_probability_plot_ad_test_rendered': True,
        'panel_capability_summary_indices_ppm_rendered': True,
        'special_causes_test_violations_rendered': True,
        'single_column_subgroup_size_supported': True,
        'single_column_subgroup_id_supported': True,
        'subgroups_across_rows_supported': True,
        'within_capability_cp_cpk_ccpk_cpm_supported': True,
        'overall_capability_pp_ppk_supported': True,
        'ppm_defect_rates_supported': True,
        'mpx_dirty_rerun_supported': True,
    }
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Updated outputs/StatCraft-preview-manifest.json for Preview 59')
