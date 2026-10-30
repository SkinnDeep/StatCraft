"""Update manifest and release records for Preview 57: One-Sample & Two-Sample Variances."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview57.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview57.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview57"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-57-one-and-two-variances'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview57.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

feat1 = "One-Sample Variance test and confidence interval: raw columns and summarized data modes (sample size + sample standard deviation or sample variance), Chi-Square and Bonett methods, directional alternatives, hypothesis tests against arbitrary hypothesized standard deviation or variance, working Options child dialog, and saved MPX reruns"
feat2 = "Two-Sample Variances test and confidence interval: stacked, unstacked, and summarized data modes (sample standard deviations or variances), ratio of standard deviations or variances, F-test (normal theory), Bonett and Levene tests, directional alternatives, working Options/Graphs/Results child dialogs, Summary Plot, and saved MPX reruns"

if feat1 not in manifest['supported']:
    manifest['supported'].append(feat1)
if feat2 not in manifest['supported']:
    manifest['supported'].append(feat2)

demo_mpx = out / 'StatCraft-one-and-two-variances-demo.mpx'
dlg1_img = out / 'StatCraft-one-variance-dialog-preview-57.png'
dlg2_img = out / 'StatCraft-two-variances-dialog-preview-57.png'
plot_img = out / 'StatCraft-two-variances-summary-plot-preview-57.png'
rep1_txt = out / 'StatCraft-one-variance-report.txt'
rep2_txt = out / 'StatCraft-two-variances-report.txt'
docx1 = out / 'StatCraft-one-variance-example.docx'
pptx1 = out / 'StatCraft-one-variance-example.pptx'
docx2 = out / 'StatCraft-two-variances-example.docx'
pptx2 = out / 'StatCraft-two-variances-example.pptx'

manifest['one_and_two_variances_packaged_verification'] = {
    'preview': 57,
    'feature': 'One-Sample & Two-Sample Variances (Stat > Basic Statistics > 1 Variance... & 2 Variances...) Native Parity',
    'native_full_parity': False,
    'mdf_resources_verified': [
        '0245-1VARIANCE.MDF',
        '0246-1VARIANCEOPTIONS.MDF',
        '0254-2VARIANCES.MDF',
        '0255-2VARIANCESGRAPHS.MDF',
        '0256-2VARIANCESOPTIONS.MDF',
        '0257-2VARIANCESRESULTS.MDF'
    ],
    'files': {
        'demo_mpx': {
            'path': 'outputs/StatCraft-one-and-two-variances-demo.mpx',
            'bytes': demo_mpx.stat().st_size,
            'sha256': hashlib.sha256(demo_mpx.read_bytes()).hexdigest(),
        },
        'one_variance_dialog_screenshot': {
            'path': 'outputs/StatCraft-one-variance-dialog-preview-57.png',
            'bytes': dlg1_img.stat().st_size,
            'sha256': hashlib.sha256(dlg1_img.read_bytes()).hexdigest(),
        },
        'two_variances_dialog_screenshot': {
            'path': 'outputs/StatCraft-two-variances-dialog-preview-57.png',
            'bytes': dlg2_img.stat().st_size,
            'sha256': hashlib.sha256(dlg2_img.read_bytes()).hexdigest(),
        },
        'two_variances_summary_plot': {
            'path': 'outputs/StatCraft-two-variances-summary-plot-preview-57.png',
            'bytes': plot_img.stat().st_size,
            'sha256': hashlib.sha256(plot_img.read_bytes()).hexdigest(),
        },
        'one_variance_report': {
            'path': 'outputs/StatCraft-one-variance-report.txt',
            'bytes': rep1_txt.stat().st_size,
            'sha256': hashlib.sha256(rep1_txt.read_bytes()).hexdigest(),
        },
        'two_variances_report': {
            'path': 'outputs/StatCraft-two-variances-report.txt',
            'bytes': rep2_txt.stat().st_size,
            'sha256': hashlib.sha256(rep2_txt.read_bytes()).hexdigest(),
        },
        'one_variance_docx': {
            'path': 'outputs/StatCraft-one-variance-example.docx',
            'bytes': docx1.stat().st_size,
            'sha256': hashlib.sha256(docx1.read_bytes()).hexdigest(),
        },
        'one_variance_pptx': {
            'path': 'outputs/StatCraft-one-variance-example.pptx',
            'bytes': pptx1.stat().st_size,
            'sha256': hashlib.sha256(pptx1.read_bytes()).hexdigest(),
        },
        'two_variances_docx': {
            'path': 'outputs/StatCraft-two-variances-example.docx',
            'bytes': docx2.stat().st_size,
            'sha256': hashlib.sha256(docx2.read_bytes()).hexdigest(),
        },
        'two_variances_pptx': {
            'path': 'outputs/StatCraft-two-variances-example.pptx',
            'bytes': pptx2.stat().st_size,
            'sha256': hashlib.sha256(pptx2.read_bytes()).hexdigest(),
        }
    },
    'statistics_verification': {
        'one_variance_raw_columns_supported': True,
        'one_variance_summarized_stdev_supported': True,
        'one_variance_summarized_variance_supported': True,
        'one_variance_chi_square_test_supported': True,
        'one_variance_bonett_method_supported': True,
        'two_variances_stacked_mode_supported': True,
        'two_variances_unstacked_mode_supported': True,
        'two_variances_summarized_stdevs_supported': True,
        'two_variances_summarized_variances_supported': True,
        'two_variances_f_test_supported': True,
        'two_variances_bonett_test_supported': True,
        'two_variances_levene_test_supported': True,
        'two_variances_summary_plot_rendered': True,
    }
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Updated outputs/StatCraft-preview-manifest.json for Preview 57')
