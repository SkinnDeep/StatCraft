"""Original detached graph-layout composition; no native serialization claim."""
from copy import deepcopy


def layout_eligible(entry):
    """Exclude nested compositions; an ordinary multi-panel graph is eligible."""
    if not isinstance(entry, dict):
        return False
    result = entry.get('result', entry)
    if not isinstance(result, dict):
        return False
    if _contains_composition(result):
        return False
    if result.get('panel_by') is not None or result.get('panel_variable') is not None:
        return False
    if result.get('plot_residuals') is False:
        return False
    return (result.get('graph') in ('categorical_points','dotplot_graphs','boxplot_graphs','histogram_graphs','histogram', 'scatter', 'boxplot', 'expanded', 'normal_probability')
            or result.get('chart') in ('P', 'U')
            or 'within_stdev' in result or 'i_center' in result or 'xbar_center' in result
            or ('fitted' in result and 'residuals' in result))


def _contains_composition(value, seen=None):
    """Check nested result payloads without treating plotting panels as layouts."""
    if not isinstance(value, (dict, list, tuple)):
        return False
    if seen is None:
        seen = set()
    if id(value) in seen:
        return False
    seen.add(id(value))
    if isinstance(value, dict):
        if value.get('graph') in ('graph_layout', 'panel', 'panel_graph', 'panelled'):
            return True
        children = value.values()
    else:
        children = value
    return any(_contains_composition(child, seen) for child in children)


def _identity(entry):
    for key in ('entry_id', 'id'):
        if entry.get(key) is not None:
            return (key, str(entry[key]))
    return ('object', id(entry))


def build_layout(entries, rows=2, columns=2, title='Graph Layout'):
    """Validate selected sources and deeply snapshot graph data and styles."""
    if type(rows) is not int or not 1 <= rows <= 9 or type(columns) is not int or not 1 <= columns <= 9:
        raise ValueError('Layout rows and columns must be integers from 1 to 9.')
    if not isinstance(title, str) or len(title) > 145:
        raise ValueError('Layout title must be text with at most 145 characters.')
    if not isinstance(entries, (list, tuple)) or not entries:
        raise ValueError('Select at least one graph for the layout.')
    if len(entries) > 16:
        raise ValueError('A layout supports at most 16 selected graphs.')
    if len(entries) > rows * columns:
        raise ValueError('Selected graphs exceed layout capacity (' + str(rows * columns) + ').')
    identities = set()
    for entry in entries:
        if not layout_eligible(entry):
            raise ValueError('Choose individual supported graphs; layouts and panel graphs cannot be nested.')
        identity = _identity(entry)
        if identity in identities:
            raise ValueError('A source graph can appear only once in a layout.')
        identities.add(identity)
    return dict(graph='graph_layout', graphs=deepcopy(list(entries)),
                rows=rows, columns=columns, title=title)
