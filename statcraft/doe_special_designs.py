"""Original bounded mixture and finite-candidate D/I exchange design generators.

The exchange search is deterministic and local, with no global optimum claim.
I uses a uniform measure over the allowed finite candidate set, not continuous
region integration. Extreme vertices are enumerated from box constraints plus
the component-sum equality; this is not StatCraft's XVERT/CONAEV implementation.
"""
import copy
import itertools
import math
import random
import numpy as np
from scipy.linalg import qr
from .model import Column, Worksheet


KINDS = ('simplex_centroid', 'simplex_lattice', 'extreme_vertices', 'custom_optimal')
MAX_RUNS, MAX_CANDIDATES, MAX_TERMS = 4096, 4096, 64
SOURCES = [
    'https://www.itl.nist.gov/div898/handbook/pri/section5/pri542.htm',
    'https://www.itl.nist.gov/div898/handbook/pri/section5/pri543.htm',
    'https://www.itl.nist.gov/div898/handbook/pri/section5/pri554.htm',
    'https://www.itl.nist.gov/div898/handbook/pri/section5/pri521.htm',
    'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/perform-the-analysis/specify-the-methods/',
]


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer from {low} to {high}.')
    return value


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + ' must be a finite number.')
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(label + ' exceeds the supported numeric range.') from error
    if not math.isfinite(number):
        raise ValueError(label + ' must be finite.')
    return number


def _names(factors, minimum=2):
    if not isinstance(factors, (list, tuple)) or not minimum <= len(factors) <= 8:
        raise ValueError(f'Select from {minimum} to 8 factors or mixture components.')
    reserved = {'stdorder', 'runorder', 'pttype', 'blocks'}
    for factor in factors:
        if not isinstance(factor, dict):
            raise ValueError('Factors must be named objects.')
        name = factor.get('name')
        if not isinstance(name, str) or not name.strip() or name != name.strip() or len(name) > 128 or name.casefold() in reserved:
            raise ValueError('Factor names must be unique, nonblank and different from design-column names.')
        reserved.add(name.casefold())


def _compositions(total, count):
    if count == 1:
        yield (total,)
    else:
        for first in range(total, -1, -1):
            for rest in _compositions(total - first, count - 1):
                yield (first,) + rest


def _mixture(kind, factors, options):
    total = _finite(options.get('total', 1.), 'Mixture total')
    if total <= 0:
        raise ValueError('Mixture total must be positive.')
    lower = [_finite(factor.get('low', 0.), 'Component lower bound') for factor in factors]
    upper = [_finite(factor.get('high', total), 'Component upper bound') for factor in factors]
    if any(lo < 0 or hi < lo or hi > total for lo, hi in zip(lower, upper)):
        raise ValueError('Component bounds must satisfy 0 <= lower <= upper <= mixture total.')
    tolerance = 64 * np.finfo(float).eps * max(total, 1.)
    if math.fsum(lower) > total + tolerance or math.fsum(upper) < total - tolerance:
        raise ValueError('Component bounds and the mixture total define an empty region.')
    q = len(factors)
    remaining = total - math.fsum(lower)
    if kind != 'extreme_vertices':
        if remaining <= tolerance:
            raise ValueError('A standard simplex design requires a nondegenerate L-simplex.')
        if any(hi + tolerance < lo + remaining for lo, hi in zip(lower, upper)):
            raise ValueError('Upper component bounds cut the standard simplex. Select an extreme-vertices design instead.')
        if kind == 'simplex_centroid':
            coordinates = []
            for size in range(1, q + 1):
                for subset in itertools.combinations(range(q), size):
                    coordinates.append([1. / size if j in subset else 0. for j in range(q)])
            degree = q
        else:
            degree = _integer(options.get('degree', 2), 1, 8, 'Lattice degree')
            if math.comb(q + degree - 1, degree) > MAX_RUNS:
                raise ValueError('This simplex lattice exceeds the 4096-point limit.')
            coordinates = [[value / degree for value in comp] for comp in _compositions(degree, q)]
        points = [[lo + remaining * value for lo, value in zip(lower, coordinate)] for coordinate in coordinates]
        center = [lo + remaining / q for lo in lower]
    else:
        degree = _integer(options.get('degree', 1), 1, 1, 'Extreme-vertices degree (vertices only)')
        found = {}
        # A vertex of one equality intersected with a box has at most one
        # component away from its bounds. Enumerate each possible free one.
        for free in range(q):
            fixed = [j for j in range(q) if j != free]
            for choices in itertools.product((0, 1), repeat=q - 1):
                point = [0.] * q
                for j, high in zip(fixed, choices):
                    point[j] = upper[j] if high else lower[j]
                value = total - math.fsum(point[j] for j in fixed)
                if lower[free] - tolerance <= value <= upper[free] + tolerance:
                    point[free] = min(upper[free], max(lower[free], value))
                    key = tuple(round(value / total, 14) for value in point)
                    found.setdefault(key, point)
        points = [found[key] for key in sorted(found)]
        if not points:
            raise ValueError('No feasible mixture vertices were found within supported precision.')
        center = np.mean(np.asarray(points), axis=0).tolist()
    descriptors = [dict(name=factor['name'], kind='number', low=lo, high=hi, column_index=4 + i)
                   for i, (factor, lo, hi) in enumerate(zip(factors, lower, upper))]
    diagnostics = {'component_total': total, 'degree': degree, 'base_points': len(points),
                   'rank': int(np.linalg.matrix_rank(np.asarray(points))),
                   'vertex_count': len(points) if kind == 'extreme_vertices' else q,
                   'centroid_definition': 'Mean of enumerated vertices' if kind == 'extreme_vertices' else 'L-simplex barycenter'}
    return points, center, descriptors, diagnostics


def _optimal_factors(factors):
    descriptors = []
    for i, factor in enumerate(factors):
        kind = factor.get('kind', 'number')
        if kind == 'categorical':
            kind = 'text'
        if kind not in ('number', 'text'):
            raise ValueError('Optimal factors must be numeric or categorical text.')
        levels = factor.get('levels')
        if not isinstance(levels, (list, tuple)) or not 2 <= len(levels) <= 12:
            raise ValueError('Each optimal factor needs 2 to 12 explicit candidate levels.')
        if kind == 'number':
            levels = [_finite(value, 'Numeric candidate level') for value in levels]
            lo, hi = min(levels), max(levels)
            if not math.isfinite(hi - lo) or hi <= lo:
                raise ValueError('Numeric candidate range must be positive and finite.')
        else:
            if any(not isinstance(value, str) or not value.strip() for value in levels):
                raise ValueError('Categorical candidate levels must be nonblank text.')
            levels = [value.strip() for value in levels]
        if len(set(levels)) != len(levels):
            raise ValueError('Candidate levels must be distinct within each factor.')
        descriptor = dict(name=factor['name'], kind=kind, levels=levels, column_index=4 + i)
        if kind == 'number':
            center, half_range = lo / 2 + hi / 2, (hi - lo) / 2
            if half_range <= 0 or not lo < center < hi:
                raise ValueError('Numeric candidate midpoint exceeds supported precision.')
            descriptor.update(low=lo, high=hi, center=center, half_range=half_range)
        else:
            descriptor['reference_level'] = levels[0]
        descriptors.append(descriptor)
    return descriptors


def _candidate_set(descriptors, forbidden):
    product_count = math.prod(len(factor['levels']) for factor in descriptors)
    if product_count > MAX_CANDIDATES:
        raise ValueError('The candidate-level product exceeds the 4096-point limit.')
    if not isinstance(forbidden, list) or len(forbidden) > 100:
        raise ValueError('Forbidden combinations must be a list of at most 100 objects.')
    by_name = {factor['name']: factor for factor in descriptors}
    for restriction in forbidden:
        if not isinstance(restriction, dict) or not restriction:
            raise ValueError('Each forbidden combination must specify at least one named factor level.')
        for name, value in restriction.items():
            if name not in by_name or value not in by_name[name]['levels'] or isinstance(value, bool):
                raise ValueError('Forbidden combinations must reference existing factor names and levels.')
    points = []
    names = [factor['name'] for factor in descriptors]
    for point in itertools.product(*(factor['levels'] for factor in descriptors)):
        row = dict(zip(names, point))
        if not any(all(row[name] == value for name, value in rule.items()) for rule in forbidden):
            points.append(list(point))
    if not points:
        raise ValueError('Forbidden combinations exclude every candidate point.')
    return points, product_count


def model_matrix(points, descriptors, model='main_effects'):
    """Build the declared coded model; interactions never multiply a factor by itself."""
    if model not in ('main_effects', 'interactions', 'quadratic', 'full_quadratic'):
        raise ValueError('Choose main_effects, interactions, quadratic or full_quadratic.')
    n = len(points)
    columns, terms, per_factor = [np.ones(n)], ['Constant'], []
    for j, factor in enumerate(descriptors):
        basis = []
        if factor['kind'] == 'number':
            values = np.asarray([point[j] for point in points], dtype=float)
            code = (values - factor['center']) / factor['half_range']
            basis.append((code, factor['name']))
        else:
            for level in factor['levels'][1:]:
                basis.append((np.asarray([float(point[j] == level) for point in points]), factor['name'] + '[' + level + ']'))
        for values, label in basis:
            columns.append(values);terms.append(label)
        per_factor.append(basis)
    if model in ('interactions', 'full_quadratic'):
        for left in range(len(descriptors)):
            for right in range(left + 1, len(descriptors)):
                for lvals, lname in per_factor[left]:
                    for rvals, rname in per_factor[right]:
                        columns.append(lvals * rvals);terms.append(lname + '*' + rname)
    if model in ('quadratic', 'full_quadratic'):
        for j, factor in enumerate(descriptors):
            if factor['kind'] == 'number':
                columns.append(per_factor[j][0][0] ** 2);terms.append(factor['name'] + '^2')
    if len(terms) > MAX_TERMS:
        raise ValueError('The requested model exceeds the 64-term limit.')
    return np.column_stack(columns), terms


def _metrics(matrix, moment):
    rank = int(np.linalg.matrix_rank(matrix))
    if rank != matrix.shape[1]:
        raise ValueError('Selected design is rank deficient for the requested model.')
    information = matrix.T @ matrix
    sign, log_det = np.linalg.slogdet(information)
    if sign <= 0:
        raise ValueError('Selected model information is not numerically positive definite.')
    inverse = np.linalg.solve(information, np.eye(matrix.shape[1]))
    return float(log_det), float(np.trace(inverse @ moment)), inverse


def _exchange(matrix, runs, criterion, iterations):
    # Pivoted QR selects a full-rank starting subset. Add remaining distinct runs
    # greedily, then cyclically exchange each selected row with an allowed point.
    _, _, pivots = qr(matrix.T, pivoting=True, mode='economic')
    p = matrix.shape[1]
    selected = [int(i) for i in pivots[:p]]
    moment = matrix.T @ matrix / len(matrix)
    while len(selected) < runs:
        _, current_i, inverse = _metrics(matrix[selected], moment)
        h = np.einsum('ij,ij->i', matrix @ inverse, matrix)
        if criterion == 'D':
            scores = np.log1p(h)
        else:
            middle = inverse @ moment @ inverse
            reduction = np.einsum('ij,ij->i', matrix @ middle, matrix) / (1 + h)
            scores = reduction
        scores[selected] = -np.inf
        selected.append(int(np.argmax(scores)))
    initial_d, initial_i, _ = _metrics(matrix[selected], moment)
    swaps, passes, converged, evaluations = 0, 0, False, 0
    for iteration in range(iterations):
        changed = False
        for position in range(runs):
            current_d, current_i, inverse = _metrics(matrix[selected], moment)
            old = matrix[selected[position]]
            h_old = float(old @ inverse @ old)
            projected = matrix @ inverse
            h_new = np.einsum('ij,ij->i', projected, matrix)
            cross = projected @ old
            ratio = (1 - h_old) * (1 + h_new) + cross ** 2
            feasible = ratio > 1e-10
            if criterion == 'D':
                scores = np.full(len(matrix), -np.inf)
                scores[feasible] = current_d + np.log(ratio[feasible])
            else:
                middle = inverse @ moment @ inverse
                d_old = float(old @ middle @ old)
                d_cross = matrix @ middle @ old
                d_new = np.einsum('ij,ij->i', matrix @ middle, matrix)
                scores = np.full(len(matrix), np.inf)
                scores[feasible] = current_i + ((1 + h_new[feasible]) * d_old - 2 * cross[feasible] * d_cross[feasible] + (h_old - 1) * d_new[feasible]) / ratio[feasible]
            excluded = [i for j, i in enumerate(selected) if j != position]
            scores[excluded] = -np.inf if criterion == 'D' else np.inf
            best = int(np.argmax(scores) if criterion == 'D' else np.argmin(scores))
            evaluations += len(matrix)
            improvement = scores[best] - current_d if criterion == 'D' else current_i - scores[best]
            if improvement > 1e-9 * (1 + abs(current_d if criterion == 'D' else current_i)):
                trial = list(selected);trial[position] = best
                # Verify the actual objective instead of trusting a near-singular
                # determinant-lemma approximation.
                try:
                    actual_d, actual_i, _ = _metrics(matrix[trial], moment)
                except (ValueError, np.linalg.LinAlgError):
                    continue
                gain = actual_d - current_d if criterion == 'D' else current_i - actual_i
                if gain > 1e-9 * (1 + abs(current_d if criterion == 'D' else current_i)):
                    selected = trial;swaps += 1;changed = True
        passes += 1
        if not changed:
            converged = True
            break
    final_d, final_i, _ = _metrics(matrix[selected], moment)
    return sorted(selected), dict(initial_log_determinant=initial_d, initial_average_prediction_variance=initial_i,
        log_determinant=final_d, average_prediction_variance=final_i, exchanges=swaps, passes=passes,
        converged=converged, candidate_evaluations=evaluations)


def _optimal(factors, options):
    descriptors = _optimal_factors(factors)
    candidates, product_count = _candidate_set(descriptors, options.get('forbidden', []))
    model = options.get('model', 'main_effects')
    matrix, terms = model_matrix(candidates, descriptors, model)
    p = matrix.shape[1]
    if np.linalg.matrix_rank(matrix) != p:
        raise ValueError('The allowed candidates cannot estimate the requested model with full rank.')
    runs = _integer(options.get('runs', min(len(candidates), max(p + 2, 2 * len(factors) + 1))), p, min(256, len(candidates)), 'Selected runs')
    iterations = _integer(options.get('max_iterations', 8), 1, 20, 'Exchange passes')
    if runs * len(candidates) * iterations > 2000000:
        raise ValueError('The requested exchange search exceeds the two-million candidate-evaluation limit. Reduce runs, candidates or passes.')
    criterion = options.get('criterion', 'D')
    if criterion not in ('D', 'I'):
        raise ValueError('Choose D or I optimality.')
    indices, diagnostics = _exchange(matrix, runs, criterion, iterations)
    diagnostics.update(criterion=criterion, model=model, terms=terms, rank=p, model_columns=p,
        candidate_count=len(candidates), candidate_product_count=product_count, selected_candidate_indices=indices,
        objective=diagnostics['log_determinant'] if criterion == 'D' else diagnostics['average_prediction_variance'],
        objective_direction='maximize' if criterion == 'D' else 'minimize',
        integration='Uniform measure over allowed finite candidates',
        search='Original deterministic QR initialization and cyclic point-exchange local heuristic',
        global_optimum_verified=False)
    return [candidates[i] for i in indices], None, descriptors, diagnostics


def create_design(kind, factors, replicates=1, centers=0, randomize=True, seed=1, blocks=1, options=None, name='DOE plan'):
    """Create a bounded original DOE worksheet with standard design bookkeeping."""
    if kind not in KINDS:
        raise ValueError('Unsupported special DOE design kind.')
    factors = copy.deepcopy(factors)
    _names(factors, 1 if kind == 'custom_optimal' else 2)
    replicates = _integer(replicates, 1, 20, 'Replicates')
    centers = _integer(centers, 0, 20, 'Additional center points per block')
    blocks = _integer(blocks, 1, 20, 'Blocks')
    seed = _integer(seed, -(2 ** 63), 2 ** 63 - 1, 'Randomization seed')
    if type(randomize) is not bool:
        raise ValueError('Randomize must be true or false.')
    if replicates % blocks:
        raise ValueError('Whole-replicate blocking requires the number of blocks to divide replicates.')
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ValueError('Design worksheet name must be nonblank text of at most 128 characters.')
    if options is not None and not isinstance(options, dict):
        raise ValueError('Design options must be an object.')
    options = copy.deepcopy(options or {})
    if kind == 'custom_optimal' and centers:
        raise ValueError('Additional center runs are not defined for this finite-candidate design. Include center levels among the explicit candidate settings instead.')
    if kind == 'custom_optimal':
        points, center, descriptors, diagnostics = _optimal(factors, options)
    else:
        points, center, descriptors, diagnostics = _mixture(kind, factors, options)
    count = len(points) * replicates + centers * blocks
    if count > MAX_RUNS:
        raise ValueError('The generated plan exceeds the 4096-run limit.')
    groups = {block: [] for block in range(1, blocks + 1)}
    for rep in range(replicates):
        block = rep % blocks + 1
        groups[block].extend({'settings': list(point), 'point_type': 1, 'block': block} for point in points)
    for block in groups:
        groups[block].extend({'settings': list(center), 'point_type': 0, 'block': block} for _ in range(centers))
    standard = [row for block in groups for row in groups[block]]
    for index, row in enumerate(standard, 1):
        row['standard_order'] = index
    plan = []
    rng = random.Random(seed)
    for block in groups:
        rows = list(groups[block])
        if randomize:
            rng.shuffle(rows)
        plan.extend(rows)
    columns = [Column('StdOrder', values=[row['standard_order'] for row in plan]),
               Column('RunOrder', values=list(range(1, count + 1))),
               Column('PtType', values=[row['point_type'] for row in plan]),
               Column('Blocks', values=[row['block'] for row in plan])]
    columns.extend(Column(factor['name'], factor['kind'], [row['settings'][j] for row in plan]) for j, factor in enumerate(descriptors))
    notes = ['Original generated design; native generation algorithms and serialization parity are unverified.',
             'Blocks allocate complete replicates; no optimal block-confounding search is performed.']
    if kind == 'extreme_vertices':
        notes.append('Enumerated box-constrained mixture vertices only; native higher-degree face-centroid augmentation is not implemented.')
    if kind == 'custom_optimal':
        notes.extend(['Unique candidate points are selected within each replicate; arbitrary unequal run replication is not optimized.',
                      'D/I criteria describe the coded model and the finite candidate region; the deterministic exchange search does not prove a global optimum.',
                      'Diagnostics describe one selected replicate; repeating the complete plan multiplies information but does not change the selected support.'])
    metadata = {'schema': 'statcraft-special-design-v1', 'origin': 'Original StatCraft design', 'design': kind,
                'kind': kind, 'factors': descriptors, 'replicates': replicates, 'centers': centers,
                'blocks': blocks, 'randomize': randomize, 'seed': seed, 'options': options,
                'diagnostics': diagnostics, 'notes': notes, 'sources': SOURCES, 'native_parity': False}
    return Worksheet(name.strip(), columns, metadata={'doe': metadata})
