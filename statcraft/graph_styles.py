"""Validated StatCraft graph-object appearance metadata, independent of Qt.

Target identifiers refer to a panel and a rendered object, for example
``p0:s1`` (the second series) or ``p0:bars``.  These are StatCraft snapshot
identifiers, not a claim about the native application's saved graph format.
Styles contain appearance only; statistical results remain untouched.
"""
import math
import numbers
import re


_TARGET = re.compile(r'p[0-9]+:(?:s[0-9]+|bars|box|axis|grid|fit[0-9]+|ref[0-9]+|(?:int|mean|median|bar)[0-9]+)\Z')
_COLOR = re.compile(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\Z')
COLOR_FIELDS = frozenset(('color', 'fill', 'edge'))
NUMBER_RANGES = {'line_width': (0, 12), 'marker_size': (1, 30), 'opacity': (0, 1)}
ENUM_FIELDS = {
    'line_style': frozenset(('solid', 'dash', 'dot', 'none')),
    'marker': frozenset(('circle', 'square', 'triangle', 'diamond', 'plus', 'cross', 'none')),
}
BOOL_FIELDS = frozenset(('visible', 'legend_visible'))
FIELDS = COLOR_FIELDS | NUMBER_RANGES.keys() | ENUM_FIELDS.keys() | BOOL_FIELDS


def _validate_target(target):
    if not isinstance(target, str) or _TARGET.fullmatch(target) is None:
        raise ValueError('Graph style target must identify a panel and supported object, such as p0:s0.')


def _validate_style(style):
    if not isinstance(style, dict) or set(style) - FIELDS:
        raise ValueError('Invalid graph object style fields.')
    result = {}
    for field, value in style.items():
        if field in COLOR_FIELDS:
            if not isinstance(value, str) or _COLOR.fullmatch(value) is None:
                raise ValueError(field.capitalize() + ' must use #RRGGBB or #RRGGBBAA format.')
            result[field] = value.lower()
        elif field in NUMBER_RANGES:
            low, high = NUMBER_RANGES[field]
            if (isinstance(value, bool) or not isinstance(value, numbers.Real)
                    or not math.isfinite(value) or not low <= value <= high):
                raise ValueError(field.replace('_', ' ').capitalize()
                                 + ' must be a finite number between ' + str(low) + ' and ' + str(high) + '.')
            result[field] = float(value)
        elif field in ENUM_FIELDS:
            if not isinstance(value, str) or value not in ENUM_FIELDS[field]:
                raise ValueError('Invalid ' + field.replace('_', ' ') + '.')
            result[field] = value
        else:
            if type(value) is not bool:
                raise ValueError(field.replace('_', ' ').capitalize() + ' must be on or off.')
            result[field] = value
    return result


def validate_styles(styles):
    """Return a detached JSON-safe sparse style map, or raise ValueError.

    Empty maps and empty per-object styles are valid.  Missing values inherit
    the renderer's defaults rather than forcing a common graph palette.
    Validation completes without modifying the caller's map, even on failure.
    """
    if not isinstance(styles, dict):
        raise ValueError('Graph object styles must be a map.')
    result = {}
    for target, style in styles.items():
        _validate_target(target)
        result[target] = _validate_style(style)
    return result


def style_for(styles, target, defaults=None):
    """Resolve one object's appearance over validated renderer defaults.

    ``styles`` is normally a previously validated snapshot map. The complete
    map is still checked here so invalid persisted metadata cannot silently
    reach a renderer. A new dictionary is returned on every call.
    """
    _validate_target(target)
    resolved = _validate_style({} if defaults is None else defaults)
    resolved.update(validate_styles(styles).get(target, {}))
    return resolved
