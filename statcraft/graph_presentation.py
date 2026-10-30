"""Original, JSON-safe annotation and Cartesian-scale presentation settings.

Native host serialization is unverified. These settings belong to StatCraft's
result snapshots and do not alter the underlying statistical calculation.
"""
import math
import numbers


FIELDS = {
    'title', 'subtitle', 'footnote', 'title_enabled', 'subtitle_enabled',
    'footnote_enabled', 'x_label', 'y_label', 'x_position', 'y_position',
    'x_min', 'x_max', 'y_min', 'y_max', 'grid_enabled',
}
DEFAULTS = dict(title='', subtitle='', footnote='', title_enabled=True,
                subtitle_enabled=False, footnote_enabled=False,
                x_label='', y_label='', x_position='low', y_position='low',
                x_min=None, x_max=None, y_min=None, y_max=None,
                grid_enabled=True)


def validate_presentation(settings):
    """Return a detached normalized full setting map, or raise ValueError."""
    if not isinstance(settings, dict) or set(settings) - FIELDS:
        raise ValueError('Invalid graph presentation fields.')
    result = dict(DEFAULTS)
    result.update(settings)
    for name in ('title', 'subtitle', 'footnote', 'x_label', 'y_label'):
        value = result[name]
        if not isinstance(value, str) or len(value) > 145:
            raise ValueError(name.replace('_', ' ').capitalize() + ' must contain at most 145 characters.')
    for name in ('title_enabled', 'subtitle_enabled', 'footnote_enabled', 'grid_enabled'):
        if type(result[name]) is not bool:
            raise ValueError(name.replace('_', ' ').capitalize() + ' must be on or off.')
    for axis in ('x', 'y'):
        if result[axis + '_position'] not in ('off', 'low', 'high'):
            raise ValueError(axis.upper() + '-axis label position must be Off, Low or High.')
        for edge in ('min', 'max'):
            key = axis + '_' + edge
            value = result[key]
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
                    raise ValueError(axis.upper() + '-axis limits must be finite numbers or blank.')
                result[key] = float(value)
        low, high = result[axis + '_min'], result[axis + '_max']
        if (low is None) != (high is None):
            raise ValueError('Enter both ' + axis.upper() + '-axis limits, or leave both blank for automatic scaling.')
        if low is not None and (low >= high or not math.isfinite(high - low)):
            raise ValueError(axis.upper() + '-axis minimum must be less than maximum within a finite range.')
    return result


def graph_presentation(entry):
    """Resolve saved presentation over existing graph labels, without mutation."""
    entry = entry if isinstance(entry, dict) else {}
    result = entry.get('result', {})
    result = result if isinstance(result, dict) else {}
    if result.get('analysis')=='native_saved_output':
        from .native_graph_view import presentation
        return presentation(entry)
    panels = result.get('panels', [])
    first = panels[0] if isinstance(panels, list) and panels and isinstance(panels[0], dict) else {}
    axes = first.get('axes', [])
    axes = axes if isinstance(axes, list) else []
    text = lambda value: str(value)[:145] if value is not None else ''
    defaults = dict(DEFAULTS)
    defaults['title'] = text(result.get('plot_title', entry.get('title', result.get('title', 'Graph'))))
    if result.get('graph')=='graph_layout':defaults['title']=text(result.get('title','Graph Layout'))
    defaults['subtitle'] = text(result.get('subtitle', ''))
    defaults['footnote'] = text(result.get('footnote', ''))
    defaults['title_enabled'] = bool(defaults['title'])
    defaults['subtitle_enabled'] = bool(defaults['subtitle'])
    defaults['footnote_enabled'] = bool(defaults['footnote'])
    defaults['x_label'] = text(result.get('xlabel', first.get('x_label', first.get('xlabel',
        axes[0] if axes else result.get('variable', '')))))
    defaults['y_label'] = text(result.get('ylabel', first.get('y_label', first.get('ylabel',
        axes[1] if len(axes) > 1 else 'Frequency' if result.get('graph') == 'histogram' else ''))))
    if result.get('graph')=='histogram' and entry.get('histogram_settings'):
        options=entry['histogram_settings'];defaults['y_label']=('Cumulative ' if options.get('cumulative') else '')+options.get('scale','Frequency')
    saved = entry.get('graph_presentation')
    if isinstance(saved, dict):
        defaults.update(saved)
    return validate_presentation(defaults)
