"""Original median-centered Levene/Brown-Forsythe and Bartlett tests.

Published formulas and local policies: outputs/statcraft-variance-test-contracts.md.
Bonett, simultaneous comparisons and variance confidence intervals unsupported.
"""
import math
from scipy import stats
from .engine import normalize_numeric
from .inference import _summary


def _median(values):
    ordered=sorted(values); n=len(ordered)
    return ordered[n//2] if n%2 else math.fsum((ordered[n//2-1]/2,ordered[n//2]/2))


def equal_variances(groups, method='Levene'):
    """Independent groups, each >=2 nonmissing observations; no pairing.

    Levene is median-centered (Brown-Forsythe), using an approximate F tail.
    Bartlett uses the corrected log-variance statistic and chi-square tail.
    Numeric missing normalization omits None/sentinel/NaN/infinities per group.
    """
    if not isinstance(method,str):
        raise ValueError('Method must be Levene or Bartlett.')
    selected=method.strip().lower()
    if selected in ('levene','brown-forsythe'):
        selected='levene'
    elif selected!='bartlett':
        raise ValueError('Method must be median-centered Levene or Bartlett.')
    groups=list(groups)
    if len(groups)<2:
        raise ValueError('At least two groups are required.')
    clean_groups=[]; summaries=[]
    try:
        for index, group in enumerate(groups):
            raw=list(group); clean=[]
            for value in raw:
                value=normalize_numeric(value)
                if value is not None:clean.append(value)
            if len(clean)<2:
                raise ValueError(f'Group {index+1} requires at least two finite nonmissing observations.')
            n,mean,sd,_=_summary(clean)
            median=_median(clean)
            clean_groups.append(clean)
            summaries.append(dict(group=index+1,count=n,missing=len(raw)-n,
                                  mean=mean,median=median,sample_stdev=sd))
        k=len(groups); total=sum(s['count'] for s in summaries)
        if selected=='levene':
            deviations=[[abs(v-s['median']) for v in g] for g,s in zip(clean_groups,summaries)]
            scale=max(v for g in deviations for v in g)
            if not math.isfinite(scale):
                raise ValueError('Absolute deviations exceed the supported numeric range.')
            if scale==0:
                raise ValueError('Levene inference is undefined without residual variation in absolute deviations.')
            z=[[v/scale for v in g] for g in deviations]
            means=[math.fsum(g)/len(g) for g in z]
            grand=math.fsum(s['count']/total*m for s,m in zip(summaries,means))
            between=math.fsum(s['count']*(m-grand)**2 for s,m in zip(summaries,means))
            within=math.fsum((v-m)**2 for g,m in zip(z,means) for v in g)
            if within<=0:
                raise ValueError('Levene inference is undefined without residual variation in absolute deviations.')
            statistic=(between/(k-1))/(within/(total-k))
            p=float(stats.f.sf(statistic,k-1,total-k))
            label='Levene (median-centered Brown-Forsythe F test)'
            df=[k-1,total-k]; denominator=total-k
            assumptions='Independent observations and groups; common population variances under the null. Median-centered absolute deviations are compared using an approximate F distribution; this method is less sensitive to nonnormality than Bartlett.'
        else:
            sds=[s['sample_stdev'] for s in summaries]
            if any(sd<=0 for sd in sds):
                raise ValueError('Bartlett requires positive sample variance in every group.')
            # Common scaling cancels from the log likelihood; no variance squaring overflow.
            reference=max(sds)
            log_ratios=[2*(math.log(sd)-math.log(reference)) for sd in sds]
            pooled=math.fsum((s['count']-1)/(total-k)*math.exp(lr)
                             for s,lr in zip(summaries,log_ratios))
            correction=1+(math.fsum(1/(s['count']-1) for s in summaries)-1/(total-k))/(3*(k-1))
            numerator=(total-k)*math.log(pooled)-math.fsum((s['count']-1)*lr for s,lr in zip(summaries,log_ratios))
            statistic=max(0.,numerator/correction)
            p=float(stats.chi2.sf(statistic,k-1))
            label='Bartlett (corrected chi-square test)'
            df=k-1; denominator=None
            assumptions='Independent observations and groups from normal populations; equal population variances under the null. Bartlett is sensitive to departures from normality; its chi-square reference is approximate.'
        if not math.isfinite(statistic) or not math.isfinite(p):
            raise ValueError('Variance-test arithmetic exceeds the supported numeric range.')
    except OverflowError as exc:
        raise ValueError('Variance-test arithmetic exceeds the supported numeric range.') from exc
    return dict(method=label,test_statistic=statistic,p_value=p,df=df,
                df_numerator=k-1,df_denominator=denominator,
                group_statistics=summaries,count=total,missing=sum(s['missing'] for s in summaries),
                assumptions=assumptions,warnings=[],
                missing_policy='Numeric missing values (None, sentinel, NaN and infinities) are omitted independently within each group.')
