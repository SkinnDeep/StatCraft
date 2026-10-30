"""Standard probability calculations; native-product equivalence is unverified."""
import math
from scipy import stats


PARAMETERS = {
    'Normal': ('Mean', 'Standard deviation'),
    'Student t': ('Degrees of freedom',),
    'Chi-square': ('Degrees of freedom',),
    'F': ('Numerator degrees of freedom', 'Denominator degrees of freedom'),
    'Binomial': ('Trials', 'Success probability'),
    'Poisson': ('Mean',),
    'Exponential': ('Mean',),
    'Weibull': ('Shape', 'Scale'),
}
DEFAULTS = {'Normal': (0, 1), 'Student t': (10,), 'Chi-square': (5,),
            'F': (5, 10), 'Binomial': (10, .5), 'Poisson': (5,),
            'Exponential': (1,), 'Weibull': (2, 1)}


def calculate(distribution, operation, value, parameters):
    if distribution not in PARAMETERS:
        raise ValueError('Choose a supported distribution.')
    if len(parameters) != len(PARAMETERS[distribution]):
        raise ValueError('Incorrect number of distribution parameters.')
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError('Enter a finite numeric input.')
    if any(isinstance(x, bool) or not math.isfinite(float(x)) for x in parameters):
        raise ValueError('Distribution parameters must be finite numbers.')
    p = tuple(float(x) for x in parameters)
    if distribution == 'Normal':
        if p[1] <= 0: raise ValueError('Standard deviation must be positive.')
        model = stats.norm(loc=p[0], scale=p[1])
    elif distribution == 'Binomial':
        if p[0] < 0 or p[0] != int(p[0]) or not 0 <= p[1] <= 1:
            raise ValueError('Trials must be a nonnegative integer and probability must be between 0 and 1.')
        model = stats.binom(int(p[0]), p[1])
    else:
        if any(x <= 0 for x in p): raise ValueError('Shape, mean, scale and degrees of freedom must be positive.')
        if distribution == 'Student t': model = stats.t(p[0])
        elif distribution == 'Chi-square': model = stats.chi2(p[0])
        elif distribution == 'F': model = stats.f(*p)
        elif distribution == 'Poisson': model = stats.poisson(p[0])
        elif distribution == 'Exponential': model = stats.expon(scale=p[0])
        else: model = stats.weibull_min(p[0], scale=p[1])
    value = float(value)
    if operation == 'Inverse CDF':
        if not 0 < value < 1: raise ValueError('Inverse probability must lie strictly between 0 and 1.')
        answer = model.ppf(value)
    elif operation == 'CDF': answer = model.cdf(value)
    elif operation == 'PDF/PMF':
        answer = model.pmf(value) if distribution in ('Binomial', 'Poisson') else model.pdf(value)
    else: raise ValueError('Choose PDF/PMF, CDF or Inverse CDF.')
    answer = float(answer)
    if not math.isfinite(answer): raise ValueError('Result is outside the finite supported numeric range.')
    return {'distribution': distribution, 'operation': operation, 'input': value,
            'parameters': dict(zip(PARAMETERS[distribution], p)), 'result': answer}
