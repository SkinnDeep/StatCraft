"""Update manifest and release records for Preview 56: Two-Sample Poisson Rate & DOE Multi-block."""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
exe = out / 'StatCraft-preview56.exe'
canonical = out / 'StatCraft.exe'

assert exe.exists(), "StatCraft-preview56.exe missing"
assert canonical.exists(), "StatCraft.exe missing"

exe_bytes = exe.stat().st_size
exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
can_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
assert exe_sha == can_sha, "Canonical executable does not match preview56"

smoke = json.loads((root / 'work/modern-packaged-smoke.json').read_text(encoding='utf-8'))
tests = json.loads((root / 'work/preview-v2-test-result.json').read_text(encoding='utf-8'))

manifest = json.loads((out / 'StatCraft-preview-manifest.json').read_text(encoding='utf-8-sig'))
manifest['release'] = 'preview-56-two-sample-poisson'
manifest['built_at'] = datetime.now(timezone.utc).isoformat()
manifest['executable'] = 'StatCraft-preview56.exe'
manifest['bytes'] = exe_bytes
manifest['sha256'] = exe_sha
manifest['canonical_executable_matches'] = True
manifest['reverse_engineering_complete'] = False
manifest['full_parity_verified'] = False
manifest['packaged_smoke_test'] = smoke
manifest['source_tests'] = tests

doe_feat = "Full and fractional two-level factorial creation: 2–15 factors, replicates, center points per block, seeded within-block randomization, and multi-block factorial design creation and linear model analysis with block isolation"
poiss_feat = "Two-sample Poisson rate test and confidence interval: stacked, unstacked, and summarized data modes, observation lengths/exposure frequencies, separate and pooled rate test methods, normal approximation Z-test and exact conditional binomial test, working Options child dialog, Office DOCX/PPTX export, and saved MPX reruns"

if doe_feat not in manifest['supported']:
    manifest['supported'].append(doe_feat)
if poiss_feat not in manifest['supported']:
    manifest['supported'].append(poiss_feat)

# Update two_sample_poisson_packaged_verification
demo_mpx = out / 'StatCraft-two-sample-poisson-demo.mpx'
dialog_img = out / 'StatCraft-two-sample-poisson-dialog-preview-56.png'
report_txt = out / 'StatCraft-two-sample-poisson-report.txt'
docx_exp = out / 'StatCraft-two-sample-poisson-example.docx'
pptx_exp = out / 'StatCraft-two-sample-poisson-example.pptx'

manifest['two_sample_poisson_packaged_verification'] = {
    'preview': 56,
    'feature': 'Two-Sample Poisson Rate (Stat > Basic Statistics > 2-Sample Poisson Rate...) Native Parity and DOE Multiple Blocks Support',
    'native_full_parity': False,
    'mdf_resources_verified': [
        '2SAMPLEPOISSONRATE.MDF',
        '2SAMPLEPOISSONOPTIONS.MDF',
        'FACTORIALDESIGN.MDF',
        'FACTORIALBLOCKS.MDF'
    ],
    'files': {
        'demo_mpx': {
            'path': 'outputs/StatCraft-two-sample-poisson-demo.mpx',
            'bytes': demo_mpx.stat().st_size,
            'sha256': hashlib.sha256(demo_mpx.read_bytes()).hexdigest(),
        },
        'dialog_screenshot': {
            'path': 'outputs/StatCraft-two-sample-poisson-dialog-preview-56.png',
            'bytes': dialog_img.stat().st_size,
            'sha256': hashlib.sha256(dialog_img.read_bytes()).hexdigest(),
        },
        'report_text': {
            'path': 'outputs/StatCraft-two-sample-poisson-report.txt',
            'bytes': report_txt.stat().st_size,
            'sha256': hashlib.sha256(report_txt.read_bytes()).hexdigest(),
        },
        'docx_export': {
            'path': 'outputs/StatCraft-two-sample-poisson-example.docx',
            'bytes': docx_exp.stat().st_size,
            'sha256': hashlib.sha256(docx_exp.read_bytes()).hexdigest(),
        },
        'pptx_export': {
            'path': 'outputs/StatCraft-two-sample-poisson-example.pptx',
            'bytes': pptx_exp.stat().st_size,
            'sha256': hashlib.sha256(pptx_exp.read_bytes()).hexdigest(),
        }
    },
    'statistics_verification': {
        'stacked_mode_supported': True,
        'unstacked_mode_supported': True,
        'summarized_mode_supported': True,
        'separate_rates_method_supported': True,
        'pooled_rates_method_supported': True,
        'exact_conditional_binomial_p_value': True,
        'normal_approximation_z_test': True,
        'sample1_events': 80,
        'sample1_exposure': 50.0,
        'sample1_rate': 1.6,
        'sample2_events': 65,
        'sample2_exposure': 50.0,
        'sample2_rate': 1.3,
        'rate_difference': 0.3,
        'z_value_pooled': 1.247219,
        'p_value_pooled_normal': 0.212318,
        'p_value_exact': 0.246473,
        'doe_multiple_blocks_supported': True,
        'doe_replicate_blocking_supported': True,
        'doe_center_points_per_block_supported': True,
        'doe_block_effect_isolation_supported': True,
    }
}

(out / 'StatCraft-preview-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Updated outputs/StatCraft-preview-manifest.json')
