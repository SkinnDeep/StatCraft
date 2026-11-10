"""Standard probability calculations covering continuous and discrete distributions."""
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
    'Lognormal': ('Location', 'Scale'),
    'Gamma': ('Shape', 'Scale'),
    'Beta': ('First shape', 'Second shape'),
    'Uniform': ('Lower endpoint', 'Upper endpoint'),
    'Triangular': ('Lower endpoint', 'Mode', 'Upper endpoint'),
    'Logistic': ('Location', 'Scale'),
    'Loglogistic': ('Location', 'Scale'),
    'Cauchy': ('Location', 'Scale'),
    'Laplace': ('Location', 'Scale'),
    'Smallest Extreme Value': ('Location', 'Scale'),
    'Largest Extreme Value': ('Location', 'Scale'),
    'Bernoulli': ('Event probability',),
    'Geometric': ('Event probability',),
    'Negative Binomial': ('Number of events (r)', 'Event probability'),
    'Hypergeometric': ('Population size (N)', 'Event count in pop (M)', 'Sample size (n)'),
    'Integer': ('Minimum integer', 'Maximum integer'),
}

DEFAULTS = {
    'Normal': (0, 1),
    'Student t': (10,),
    'Chi-square': (5,),
    'F': (5, 10),
    'Binomial': (10, 0.5),
    'Poisson': (5,),
    'Exponential': (1,),
    'Weibull': (2, 1),
    'Lognormal': (0, 1),
    'Gamma': (2, 1),
    'Beta': (2, 2),
    'Uniform': (0, 1),
    'Triangular': (0, 0.5, 1),
    'Logistic': (0, 1),
    'Loglogistic': (0, 1),
    'Cauchy': (0, 1),
    'Laplace': (0, 1),
    'Smallest Extreme Value': (0, 1),
    'Largest Extreme Value': (0, 1),
    'Bernoulli': (0.5,),
    'Geometric': (0.5,),
    'Negative Binomial': (5, 0.5),
    'Hypergeometric': (50, 10, 5),
    'Integer': (1, 10),
}

DISCRETE_DISTRIBUTIONS = frozenset((
    'Binomial', 'Poisson', 'Bernoulli', 'Geometric',
    'Negative Binomial', 'Hypergeometric', 'Integer',
))


def _build_model(distribution: str, p: tuple[float, ...]):
    if distribution == 'Normal':
        if p[1] <= 0:
            raise ValueError('Standard deviation must be positive.')
        return stats.norm(loc=p[0], scale=p[1])
    if distribution == 'Binomial':
        if p[0] < 0 or p[0] != int(p[0]) or not 0 <= p[1] <= 1:
            raise ValueError('Trials must be a nonnegative integer and probability must be between 0 and 1.')
        return stats.binom(int(p[0]), p[1])
    if distribution == 'Lognormal':
        if p[1] <= 0:
            raise ValueError('Scale must be positive.')
        return stats.lognorm(s=p[1], scale=math.exp(p[0]))
    if distribution == 'Uniform':
        if p[1] <= p[0]:
            raise ValueError('Upper endpoint must be strictly greater than lower endpoint.')
        return stats.uniform(loc=p[0], scale=p[1] - p[0])
    if distribution == 'Triangular':
        if not (p[0] <= p[1] <= p[2]) or p[2] <= p[0]:
            raise ValueError('Lower endpoint <= Mode <= Upper endpoint with Lower < Upper.')
        return stats.triang(c=(p[1] - p[0]) / (p[2] - p[0]), loc=p[0], scale=p[2] - p[0])
    if distribution in ('Logistic', 'Cauchy', 'Laplace', 'Smallest Extreme Value', 'Largest Extreme Value'):
        if p[1] <= 0:
            raise ValueError('Scale must be positive.')
        cls = {
            'Logistic': stats.logistic,
            'Cauchy': stats.cauchy,
            'Laplace': stats.laplace,
            'Smallest Extreme Value': stats.gumbel_l,
            'Largest Extreme Value': stats.gumbel_r,
        }[distribution]
        return cls(loc=p[0], scale=p[1])
    if distribution == 'Loglogistic':
        if p[1] <= 0:
            raise ValueError('Scale must be positive.')
        return stats.fisk(c=1.0 / p[1], scale=math.exp(p[0]))
    if distribution == 'Bernoulli':
        if not 0 <= p[0] <= 1:
            raise ValueError('Event probability must be between 0 and 1.')
        return stats.bernoulli(p[0])
    if distribution == 'Geometric':
        if not 0 < p[0] <= 1:
            raise ValueError('Event probability must be between 0 (exclusive) and 1.')
        return stats.geom(p[0])
    if distribution == 'Negative Binomial':
        if p[0] < 1 or p[0] != int(p[0]) or not 0 < p[1] <= 1:
            raise ValueError('Number of events must be a positive integer and probability in (0, 1].')
        return stats.nbinom(int(p[0]), p[1])
    if distribution == 'Hypergeometric':
        pop, events, sample = p
        if any(x < 0 or x != int(x) for x in p) or pop < 1 or events > pop or sample > pop:
            raise ValueError('Population, event count, and sample size must be valid integers with M, n <= N.')
        return stats.hypergeom(M=int(pop), n=int(events), N=int(sample))
    if distribution == 'Integer':
        if p[0] != int(p[0]) or p[1] != int(p[1]) or p[1] < p[0]:
            raise ValueError('Endpoints must be integers with Minimum <= Maximum.')
        return stats.randint(int(p[0]), int(p[1]) + 1)

    if any(x <= 0 for x in p):
        raise ValueError('Shape, mean, scale and degrees of freedom must be positive.')
    if distribution == 'Student t':
        return stats.t(p[0])
    if distribution == 'Chi-square':
        return stats.chi2(p[0])
    if distribution == 'F':
        return stats.f(*p)
    if distribution == 'Poisson':
        return stats.poisson(p[0])
    if distribution == 'Exponential':
        return stats.expon(scale=p[0])
    if distribution == 'Weibull':
        return stats.weibull_min(p[0], scale=p[1])
    if distribution == 'Gamma':
        return stats.gamma(a=p[0], scale=p[1])
    if distribution == 'Beta':
        return stats.beta(a=p[0], b=p[1])
    raise ValueError('Choose a supported distribution.')


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
    model = _build_model(distribution, p)
    value = float(value)
    if operation == 'Inverse CDF':
        if not 0 < value < 1:
            raise ValueError('Inverse probability must lie strictly between 0 and 1.')
        answer = model.ppf(value)
    elif operation == 'CDF':
        answer = model.cdf(value)
    elif operation == 'PDF/PMF':
        answer = model.pmf(value) if distribution in DISCRETE_DISTRIBUTIONS else model.pdf(value)
    else:
        raise ValueError('Choose PDF/PMF, CDF or Inverse CDF.')
    answer = float(answer)
    if not math.isfinite(answer):
        raise ValueError('Result is outside the finite supported numeric range.')
    return {
        'distribution': distribution,
        'operation': operation,
        'input': value,
        'parameters': dict(zip(PARAMETERS[distribution], p)),
        'result': answer,
    }
