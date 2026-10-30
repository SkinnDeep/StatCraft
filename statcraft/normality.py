"""Normal AD test and an original normal-probability-plot snapshot.

AD statistic: scipy.stats.anderson, pinned SciPy 1.18 API method='interpolate'.
P approximation: Stephens finite-sample adjustment and normal AD approximations
documented in statsmodels.stats._adnorm.normal_ad. Blom plotting positions.
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.anderson.html
https://www.statsmodels.org/stable/_modules/statsmodels/stats/_adnorm.html
This standard implementation does not establish native-product equivalence.
"""
import math
import statistics
from scipy import stats
from .engine import normalize_numeric
from .inference import _confidence


def normality(values):
    values=[normalize_numeric(v) for v in values]
    clean=sorted(v for v in values if v is not None)
    n=len(clean)
    if n<8: raise ValueError('The implemented normality test requires at least 8 nonmissing observations.')
    scale=max(map(abs,clean)) or 1.
    scaled=[v/scale for v in clean]
    center=statistics.fmean(scaled); sigma=statistics.stdev(scaled)
    if not sigma or not math.isfinite(sigma): raise ValueError('Normality testing requires variable, nonconstant data.')
    mean,stdev=center*scale,sigma*scale
    if not all(math.isfinite(v) for v in (mean,stdev)) or not stdev:
        raise ValueError('The data range exceeds supported normality-test precision.')
    test=stats.anderson(scaled,dist='norm',method='interpolate')
    ad=float(test.statistic)
    if not math.isfinite(ad) or ad<0: raise ValueError('The data range exceeds supported normality-test precision.')
    adjusted=ad*(1+.75/n+2.25/(n*n))
    if adjusted<.2: p=-math.expm1(-13.436+101.14*adjusted-223.73*adjusted**2)
    elif adjusted<.34: p=-math.expm1(-8.318+42.796*adjusted-59.938*adjusted**2)
    elif adjusted<.6: p=math.exp(.9177-4.279*adjusted-1.38*adjusted**2)
    elif adjusted<=13: p=math.exp(1.2937-5.709*adjusted+.0186*adjusted**2)
    else: p=None
    if p is not None: p=max(0.,min(1.,p))
    quantiles=stats.norm.ppf([(i-.375)/(n+.25) for i in range(1,n+1)]).tolist()
    reference_y=[(v-center)/sigma for v in (scaled[0],scaled[-1])]
    if not all(math.isfinite(v) for v in reference_y): raise ValueError('Normal plot range exceeds supported precision.')
    warnings=[]
    if len(set(clean))<n: warnings.append('Ties are present. The test assumes continuous data; rounding can affect its calibration.')
    if n<20: warnings.append('Small samples have limited power to detect departures from normality.')
    if p is None: warnings.append('The adjusted AD statistic exceeds 13; the P approximation is outside its supported range. The result is beyond the 1% rejection boundary.')
    return {'method':'Anderson-Darling normality test', 'count':n, 'missing':len(values)-n,
            'mean':mean, 'sample_stdev':stdev, 'anderson_darling':ad,
            'adjusted_statistic':adjusted, 'p_value':p,
            'p_value_method':'Stephens normal-distribution approximation, including finite-sample adjustment.',
            'alpha':.05, 'reject_at_5_percent':adjusted>13 or p<.05,
            'interpretation':'Evidence against a normal population at 5%.' if adjusted>13 or p<.05 else 'Normality is not rejected at 5%; this does not establish that the population is normal.',
            'graph':'normal_probability',
            'graph_data':{'observed':clean,'normal_scores':quantiles,'reference_x':[clean[0],clean[-1]],'reference_y':reference_y},
            'convention':'Blom positions (i - 0.375)/(N + 0.25); normal-probability scale; reference line uses sample mean and sample standard deviation. No confidence bands.',
            'assumptions':['Independent observations from a continuous population. Mean and standard deviation are estimated from the sample.'],
            'missing_policy':'Missing numeric observations omitted; all observed values are used in the statistic and plot.',
            'warnings':warnings}


def one_variance(values, null_stdev=1., confidence=.95):
    """Two-sided chi-square test and confidence interval for a normal population."""
    confidence=_confidence(confidence)
    null=normalize_numeric(null_stdev)
    if null is None or null<=0: raise ValueError('Hypothesized standard deviation must be positive and finite.')
    values=[normalize_numeric(v) for v in values]
    clean=[v for v in values if v is not None]
    if len(clean)<2: raise ValueError('A variance test needs at least 2 nonmissing observations.')
    sd=statistics.stdev(clean); variance=sd*sd
    if sd<=0: raise ValueError('The implemented variance test requires nonconstant data.')
    df=len(clean)-1; ratio=sd/null; statistic=df*ratio*ratio
    tail=(1-confidence)/2
    low=sd*math.sqrt(df/float(stats.chi2.isf(tail,df)))
    high=sd*math.sqrt(df/float(stats.chi2.ppf(tail,df)))
    if not all(math.isfinite(v) for v in (variance,statistic,low,high,low*low,high*high)):
        raise ValueError('Variance test or confidence interval exceeds supported numerical range.')
    return {'method':'Chi-square test for one normal-population variance', 'count':len(clean),'missing':len(values)-len(clean),
            'sample_stdev':sd,'sample_variance':variance,'null_stdev':null,
            'chi_square':statistic,'degrees_of_freedom':df,
            'p_value':min(1.,float(2*min(stats.chi2.cdf(statistic,df),stats.chi2.sf(statistic,df)))),
            'confidence':confidence,'stdev_ci_low':low,'stdev_ci_high':high,
            'variance_ci_low':low*low,'variance_ci_high':high*high,
            'assumptions':['Independent observations from a normal population. The chi-square variance test is sensitive to departures from normality.',
                           'Two-sided alternative: population standard deviation differs from the hypothesized value.'],
            'missing_policy':'Missing numeric observations omitted. Bonett and robust variance methods are not implemented.'}
