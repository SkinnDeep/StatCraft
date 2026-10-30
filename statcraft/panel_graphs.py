"""Original reproducible BY-variable graph panels from independent subsets.

Each child is recalculated through the existing typed recipe engine; splitting
an already rendered image would lose group-specific bins, fits and row identity.
"""
import copy
import math

from .value_order import ordered_values

SUPPORTED_ACTIONS = frozenset(('graph', 'scatter_plot', 'expanded_graph'))
MAX_FACETS = 16


def validate_parameters(source_recipe, by_indices, shared_x=True, shared_y=True):
    """Validate and detach serializable panel recipe parameters without state changes."""
    from .recipes import columns
    if not isinstance(source_recipe, dict) or source_recipe.get('action') not in SUPPORTED_ACTIONS:
        raise ValueError('Panels require a supported histogram, scatterplot or expanded graph recipe.')
    columns(source_recipe)
    if (not isinstance(by_indices, (list, tuple)) or not 1 <= len(by_indices) <= 2
            or any(type(i) is not int or i < 0 for i in by_indices)
            or len(set(by_indices)) != len(by_indices)):
        raise ValueError('Select one or two distinct BY columns.')
    if type(shared_x) is not bool or type(shared_y) is not bool:
        raise ValueError('Shared scales must be on or off.')
    return dict(source_recipe=copy.deepcopy(source_recipe), by_indices=list(by_indices),
                shared_x=shared_x, shared_y=shared_y)


def source_columns(source_recipe, by_indices, shared_x=True, shared_y=True):
    """Source and BY dependencies for recipe fingerprinting."""
    from .recipes import columns
    parameters = validate_parameters(source_recipe, by_indices, shared_x, shared_y)
    return sorted(set(columns(parameters['source_recipe']) + parameters['by_indices']))


def _remap_rows(value, original_rows):
    if isinstance(value, list):
        return [_remap_rows(item, original_rows) for item in value]
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= len(original_rows):
        raise ValueError('A child graph contains an invalid worksheet row identity.')
    return original_rows[value - 1]


def _remap_result(value, original_rows):
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if key in ('row_indices', 'plot_rows'):
                value[key] = _remap_rows(item, original_rows)
            else:
                _remap_result(item, original_rows)
    elif isinstance(value, list):
        for item in value:
            _remap_result(item, original_rows)


def build_panels(worksheet, source_recipe, by_indices, shared_x=True, shared_y=True):
    """Build all facets atomically; caller records the final result only on success."""
    from .app import Presenter
    from .recipes import run, fingerprints
    parameters = validate_parameters(source_recipe, by_indices, shared_x, shared_y)
    worksheet.validate()
    fingerprints(worksheet, source_columns(**parameters))
    by_columns = [worksheet.columns[index] for index in parameters['by_indices']]
    if any(column.kind not in ('number', 'text') for column in by_columns):
        raise ValueError('BY variables must be numeric or text columns.')
    groups = {}
    for index in range(worksheet.row_count):
        key = tuple(column.values[index] if index < len(column.values) else None
                    for column in by_columns)
        if any(value is None or value == '' for value in key):
            continue
        if key not in groups:
            if len(groups) >= MAX_FACETS:
                raise ValueError('Panel graphs support at most 16 observed BY-variable combinations.')
            groups[key] = []
        groups[key].append(index + 1)
    if not groups:
        raise ValueError('The BY variables contain no complete nonempty group values.')
    ranks = []
    for position, column in enumerate(by_columns):
        levels = ordered_values(column, [key[position] for key in groups])
        ranks.append({value: rank for rank, value in enumerate(levels)})
    keys = sorted(groups, key=lambda key: tuple(ranks[i][value] for i, value in enumerate(key)))
    graphs, facets = [], []
    for key in keys:
        rows = groups[key]
        label = ', '.join(column.name + ' = ' + str(value)
                          for column, value in zip(by_columns, key))
        subset = copy.deepcopy(worksheet)
        for column in subset.columns:
            column.values = [column.values[row - 1] if row <= len(column.values) else None for row in rows]
        presenter = Presenter()
        presenter.worksheet = subset
        try:
            child = run(presenter, parameters['source_recipe'])
        except (ValueError, ArithmeticError) as exc:
            raise ValueError('Cannot create panel ' + label + ': ' + str(exc)) from exc
        _remap_result(child['result'], rows)
        child['title'] = label
        child['result']['plot_title'] = label
        # Child dependencies describe an ephemeral subset, not the original
        # worksheet. Only the outer panel recipe is rerunnable/fingerprinted.
        child.pop('recipe', None)
        child.pop('dependencies', None)
        graphs.append(child)
        facets.append(dict(label=label, rows=list(rows)))
    return dict(graph='panel_graph', title='Panel Graph', plot_title='Panel Graph',
                graphs=graphs, facets=facets, shared_x=shared_x, shared_y=shared_y,
                columns=math.ceil(math.sqrt(len(graphs))), count=len(graphs),
                by_variables=[column.name for column in by_columns],
                convention='Separate graph calculations for observed BY-variable combinations; '
                'missing BY values are omitted. Text levels follow column value order; '
                'numeric levels sort numerically. Shared scales are a rendering preference.')
