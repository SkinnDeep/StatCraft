"""Independent correlation and binary-proportion procedures.

Methods: SciPy pearsonr/spearmanr/binomtest/fisher_exact; Fisher-z correlation
intervals; Newcombe difference interval formed from Wilson score intervals.
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html
https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.confint_proportions_2indep.html
No native numerical-parity claim. No vendor runtime or copied application code.
"""
import math
import warnings
from itertools import combinations, zip_longest
from scipy import stats
from .engine import normalize_numeric
from .inference import _confidence


def correlation(samples, names, method='Pearson', missing='Pairwise', confidence=.95):
    confidence = _confidence(confidence)
    if method not in ('Pearson','Spearman') or missing not in ('Pairwise','Listwise'):
        raise ValueError('Choose Pearson/Spearman and Pairwise/Listwise deletion.')
    if not 2 <= len(samples) <= 50 or len(names) != len(samples):
        raise ValueError('Select 2 to 50 numeric variables.')
    data = [[normalize_numeric(v) for v in sample] for sample in samples]
    rows = list(zip_longest(*data, fillvalue=None))
    complete = [row for row in rows if all(v is not None for v in row)]
    records, notes = [], []
    for a,b in combinations(range(len(data)),2):
        pairs = [(r[a],r[b]) for r in (complete if missing=='Listwise' else rows)
                 if r[a] is not None and r[b] is not None]
        record = {'variable_1':names[a], 'variable_2':names[b], 'count':len(pairs),
                  'missing':len(rows)-len(pairs), 'correlation':None, 'p_value':None}
        if method == 'Pearson': record.update(ci_low=None, ci_high=None)
        if len(pairs) < 3:
            notes.append(f'{names[a]} / {names[b]}: at least 3 complete pairs are required.')
        else:
            x,y = zip(*pairs)
            if min(x)==max(x) or min(y)==max(y):
                notes.append(f'{names[a]} / {names[b]}: correlation is undefined for constant inputs.')
            else:
                with warnings.catch_warnings(record=True) as observed:
                    warnings.simplefilter('always')
                    result = stats.pearsonr(x,y) if method=='Pearson' else stats.spearmanr(x,y)
                r,p = float(result.statistic),float(result.pvalue)
                if not math.isfinite(r) or not math.isfinite(p):
                    notes.append(f'{names[a]} / {names[b]}: unsupported numerical range.')
                else:
                    record.update(correlation=r, p_value=p)
                    if method=='Pearson':
                        ci = result.confidence_interval(confidence)
                        record.update(ci_low=float(ci.low),ci_high=float(ci.high))
                    if observed: notes.append(f'{names[a]} / {names[b]}: numerical precision may be poor for nearly constant inputs.')
                    if method=='Spearman' and len(pairs)<=500:
                        notes.append(f'{names[a]} / {names[b]}: Spearman P uses a large-sample approximation; a permutation test is not implemented.')
        records.append(record)
    return {'method':method, 'confidence':confidence, 'correlations':records,
            'missing_policy':missing+' deletion with worksheet-row alignment; N* counts omitted rows.',
            'assumptions':['Independent observations. Pearson P and Fisher-z intervals assume a bivariate normal population.',
                           'Two-sided tests of zero correlation. P values are not adjusted for multiple comparisons.'] if method=='Pearson' else
                          ['Independent observations; average ranks for ties; two-sided tests. P values are not adjusted for multiple comparisons.'],
            'warnings':notes}


def _binary(values):
    clean = [normalize_numeric(v) for v in values]
    present = [v for v in clean if v is not None]
    if not present: raise ValueError('A binary sample needs at least one observed 0 or 1.')
    if any(v not in (0,1) for v in present): raise ValueError('Binary samples must contain only 0, 1 or missing values; 1 is the event.')
    return int(sum(present)),len(present),len(clean)-len(present)


def one_proportion(values, null_proportion=.5, confidence=.95, alternative='two-sided'):
    confidence = _confidence(confidence)
    null = normalize_numeric(null_proportion)
    if null is None or not 0 <= null <= 1: raise ValueError('Hypothesized proportion must be between 0 and 1.')
    if alternative not in ('two-sided','less','greater'): raise ValueError('Unsupported alternative hypothesis.')
    k,n,missing = _binary(values)
    test = stats.binomtest(k,n,null,alternative=alternative)
    ci = test.proportion_ci(confidence,method='exact')
    return {'method':'Exact binomial test', 'events':k, 'count':n, 'missing':missing,
            'proportion':k/n, 'null_proportion':null, 'alternative':alternative,
            'p_value':float(test.pvalue), 'confidence':confidence,
            'ci_low':float(ci.low), 'ci_high':float(ci.high),
            'ci_method':'Clopper-Pearson exact; one-sided bound for a one-sided alternative.',
            'assumptions':['Independent Bernoulli observations with a common event probability; 1 is the event.'],
            'missing_policy':'Missing observations omitted from the sample.'}


def two_proportions(first, second, confidence=.95):
    confidence = _confidence(confidence)
    k1,n1,m1 = _binary(first); k2,n2,m2 = _binary(second)
    p1,p2 = k1/n1,k2/n2
    ci1=stats.binomtest(k1,n1).proportion_ci(confidence,method='wilson')
    ci2=stats.binomtest(k2,n2).proportion_ci(confidence,method='wilson')
    difference=p1-p2
    low = max(-1.,difference-math.hypot(p1-ci1.low,ci2.high-p2))
    high = min(1.,difference+math.hypot(ci1.high-p1,p2-ci2.low))
    pooled=(k1+k2)/(n1+n2); se=math.sqrt(pooled*(1-pooled)*(1/n1+1/n2))
    z=difference/se if se else None
    fisher=stats.fisher_exact([[k1,n1-k1],[k2,n2-k2]],alternative='two-sided')
    notes=[]
    if min(n1*pooled,n1*(1-pooled),n2*pooled,n2*(1-pooled))<5:
        notes.append('Some expected cell counts are below 5; the normal approximation can be inaccurate. Fisher exact P is also reported.')
    if se==0: notes.append('Pooled Z and its P value are undefined because the pooled variance is zero.')
    return {'method':'Two independent proportions', 'difference':difference, 'null_difference':0,
            'samples':[{'sample':1,'events':k1,'count':n1,'missing':m1,'proportion':p1},
                       {'sample':2,'events':k2,'count':n2,'missing':m2,'proportion':p2}],
            'z':z, 'pooled_z_p_value':float(2*stats.norm.sf(abs(z))) if z is not None else None,
            'fisher_exact_p_value':float(fisher.pvalue), 'confidence':confidence,
            'ci_low':float(low), 'ci_high':float(high), 'ci_method':'Newcombe difference of Wilson score intervals, without continuity correction.',
            'assumptions':['Independent samples of independent Bernoulli observations; 1 is the event.',
                           'Two-sided tests of equal event probabilities. Difference is sample 1 minus sample 2.'],
            'missing_policy':'Missing observations omitted separately within each sample.', 'warnings':notes}
