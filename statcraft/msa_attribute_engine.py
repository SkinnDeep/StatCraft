"""Nominal attribute agreement with explicit trial and eligibility accounting.

Fleiss point estimates use all completed trials. Inferential Fleiss standard
errors and p-values, category-specific coefficients and ordinal statistics are
not implemented; unavailable quantities remain None rather than fabricated.
"""
from __future__ import annotations
import math
from collections import defaultdict
import numpy as np
from scipy import stats


SOURCES = [
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/attribute-agreement-analysis/attribute-agreement-analysis/methods-and-formulas/kappa-statistics/',
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/attribute-agreement-analysis/attribute-agreement-analysis/methods-and-formulas/assessment-agreement/',
]


def _binomial_ci(successes, total, confidence=0.95):
    """Exact interval, with the documented one-sided tail at boundary outcomes."""
    if total <= 0:
        return None, None
    alpha = 1.0 - confidence
    lower = 0.0 if successes == 0 else float(stats.beta.ppf(alpha if successes == total else alpha / 2, successes, total - successes + 1))
    upper = 1.0 if successes == total else float(stats.beta.ppf(1 - (alpha if successes == 0 else alpha / 2), successes + 1, total - successes))
    return lower * 100, upper * 100


def _unavailable(note):
    return {'kappa': None, 'se': None, 'z': None, 'p_value': None, 'note': note}


def _compute_cohen_kappa(ratings1, ratings2, categories):
    if not ratings1 or len(ratings1) != len(ratings2):
        return _unavailable('Kappa needs aligned paired ratings.')
    categories = sorted(set(categories) | set(ratings1) | set(ratings2))
    lookup = {value: i for i, value in enumerate(categories)}
    matrix = np.zeros((len(categories), len(categories)))
    for first, second in zip(ratings1, ratings2):
        matrix[lookup[first], lookup[second]] += 1
    n = float(matrix.sum())
    p = matrix / n
    observed = float(np.trace(p))
    rows, cols = p.sum(axis=1), p.sum(axis=0)
    expected = float(np.sum(rows * cols))
    if 1 - expected <= 1e-12:
        return _unavailable('Kappa is undefined when chance agreement is one (constant category).')
    kappa = (observed - expected) / (1 - expected)
    variance = (expected + expected ** 2 - float(np.sum(rows * cols * (rows + cols)))) / ((1 - expected) ** 2 * n)
    if variance <= 0:
        return {'kappa': kappa, 'se': None, 'z': None, 'p_value': None, 'note': 'Null standard error is not estimable.'}
    se = math.sqrt(variance)
    z = kappa / se
    return {'kappa': kappa, 'se': se, 'z': z, 'p_value': float(stats.norm.sf(z)), 'note': ''}


def _compute_fleiss_kappa(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        return _unavailable('No eligible samples for kappa.')
    totals = matrix.sum(axis=1)
    if np.any(matrix < 0) or not np.all(np.isfinite(matrix)) or not np.allclose(totals, totals[0]):
        return _unavailable('Fleiss kappa requires equal numbers of ratings per eligible sample.')
    m = float(totals[0])
    if m < 2:
        return _unavailable('Kappa requires at least two ratings per sample.')
    marginals = matrix.sum(axis=0) / (matrix.shape[0] * m)
    expected = float(np.sum(marginals ** 2))
    if 1 - expected <= 1e-12:
        return _unavailable('Kappa is undefined when chance agreement is one (constant category).')
    observed = float(np.mean((np.sum(matrix ** 2, axis=1) - m) / (m * (m - 1))))
    return {'kappa': (observed - expected) / (1 - expected), 'se': None, 'z': None, 'p_value': None,
            'note': 'Fleiss point estimate only; its inferential standard error and p-value are not implemented.'}


def _label(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            raise ValueError('Attribute study categories and identifiers must be finite.')
        return format(value, '.15g')
    text = str(value).strip()
    return text or None


def analyze_attribute_agreement(attribute_data, samples, appraisers, standard=None, trials=None, alpha=0.05):
    n = len(attribute_data)
    if len(samples) != n or len(appraisers) != n:
        raise ValueError('Attribute data, samples, and appraisers must have identical lengths.')
    if standard is not None and len(standard) != n:
        raise ValueError('The standard column must have the same length as the attribute data.')
    if trials is not None and len(trials) != n:
        raise ValueError('The trial column must have the same length as the attribute data.')
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError('Alpha must be strictly between zero and one.')
    confidence = 1 - alpha
    standards, valid, seen = {}, [], set()
    occurrence = defaultdict(int)
    expected_trials = defaultdict(set)
    omitted = []
    for row in range(n):
        value, sample, appraiser = map(_label, (attribute_data[row], samples[row], appraisers[row]))
        truth = _label(standard[row]) if standard is not None else None
        if sample is not None and truth is not None:
            if sample in standards and standards[sample] != truth:
                raise ValueError('Conflicting standard ratings for sample ' + sample + '.')
            standards[sample] = truth
        if sample is None or appraiser is None:
            omitted.append(row)
            continue
        if trials is None:
            occurrence[(appraiser, sample)] += 1
            trial = str(occurrence[(appraiser, sample)])
        else:
            trial = _label(trials[row])
            if trial is None:
                omitted.append(row)
                continue
            identity = appraiser, sample, trial
            if identity in seen:
                raise ValueError('Duplicate trial identifier for appraiser ' + appraiser + ', sample ' + sample + ', trial ' + trial + '.')
            seen.add(identity)
        expected_trials[appraiser].add(trial)
        if value is None:
            omitted.append(row)
            continue
        valid.append((value, sample, appraiser, trial))
    if len(valid) < 4:
        raise ValueError('Attribute Agreement Analysis requires at least 4 valid observations.')
    categories = sorted({row[0] for row in valid} | set(standards.values()))
    sample_ids = sorted({row[1] for row in valid})
    app_ids = sorted({row[2] for row in valid})
    tree = {app: defaultdict(dict) for app in app_ids}
    for value, sample, app, trial in valid:
        tree[app][sample][trial] = value
    lookup = {category: i for i, category in enumerate(categories)}

    def complete(app, sample):
        return set(tree[app][sample]) == expected_trials[app]

    def ratings(app, sample):
        return [tree[app][sample][trial] for trial in sorted(expected_trials[app])]

    def matrix(groups):
        out = np.zeros((len(groups), len(categories)))
        for i, group in enumerate(groups):
            for value in group:
                out[i, lookup[value]] += 1
        return out

    def assessment(groups):
        total = len(groups)
        matched = sum(len(set(group)) == 1 for group in groups)
        low, high = _binomial_ci(matched, total, confidence)
        return {'inspected': total, 'matched': matched, 'percent': 100 * matched / total if total else None,
                'ci_lower': low, 'ci_upper': high}

    def known_assessment(app_list, eligible):
        matched = sum(all(value == standards[sample] for app in app_list for value in ratings(app, sample)) for sample in eligible)
        low, high = _binomial_ci(matched, len(eligible), confidence)
        result = {'inspected': len(eligible), 'matched': matched, 'percent': 100 * matched / len(eligible) if eligible else None,
                  'ci_lower': low, 'ci_upper': high}
        # StatCraft's known-standard coefficient is the average of per-trial
        # coefficients, not the coefficient of pooled ratings.
        components = []
        for app in app_list:
            for trial in sorted(expected_trials[app]):
                groups = [[tree[app][sample][trial], standards[sample]] for sample in eligible]
                components.append(_compute_fleiss_kappa(matrix(groups)))
        if not components or any(item['kappa'] is None for item in components):
            result.update(_unavailable('Known-standard kappa is not estimable for every included trial.'))
        else:
            result.update(kappa=sum(item['kappa'] for item in components) / len(components), se=None, z=None, p_value=None,
                          note='Mean of per-trial Fleiss coefficients; inferential statistics are not implemented.')
        result['kappa_method'] = 'Mean per-trial Fleiss'
        return result

    within, versus = [], []
    for app in app_ids:
        eligible = [sample for sample in sample_ids if complete(app, sample) and len(expected_trials[app]) >= 2]
        groups = [ratings(app, sample) for sample in eligible]
        result = assessment(groups)
        result.update(appraiser=app, kappa_method='Fleiss (all completed trials)',
                      excluded_samples=len(sample_ids) - len(eligible))
        result.update(_compute_fleiss_kappa(matrix(groups)))
        if len(expected_trials[app]) < 2:
            result['note'] = 'Within-appraiser repeatability requires at least two trials.'
        within.append(result)
        if standards:
            eligible_std = [sample for sample in sample_ids if sample in standards and complete(app, sample)]
            result = known_assessment([app], eligible_std)
            result.update(appraiser=app, excluded_samples=len(sample_ids) - len(eligible_std))
            versus.append(result)
    eligible_between = [sample for sample in sample_ids if len(app_ids) >= 2 and all(complete(app, sample) for app in app_ids)]
    groups = [[value for app in app_ids for value in ratings(app, sample)] for sample in eligible_between]
    between = assessment(groups)
    between.update(_compute_fleiss_kappa(matrix(groups)))
    between.update(kappa_method='Fleiss (all completed appraiser trials)', excluded_samples=len(sample_ids) - len(eligible_between))
    eligible_known = [sample for sample in eligible_between if sample in standards]
    all_known = known_assessment(app_ids, eligible_known) if standards else None
    notes = [
        'Agreement denominators use eligible samples with all expected trials; incomplete samples are excluded separately for each table.',
        'Trial identifiers align observations when supplied; otherwise trial numbers follow occurrence order within each appraiser/sample.',
        'Only nominal overall Fleiss point coefficients are implemented; category-specific, ordinal and inferential kappa results remain unavailable.',
    ]
    return {'analysis': 'attribute_agreement_analysis', 'method': 'Nominal attribute agreement with completed-trial eligibility',
            'n_samples': len(sample_ids), 'n_appraisers': len(app_ids), 'categories': categories, 'has_standard': bool(standards),
            'within_appraiser': within, 'appraiser_vs_standard': versus, 'between_appraisers': between,
            'all_appraisers_vs_standard': all_known, 'confidence_level': confidence, 'alpha': alpha,
            'n_valid': len(valid), 'omitted_rows': omitted, 'notes': notes, 'sources': SOURCES,
            'native_full_parity': False}
