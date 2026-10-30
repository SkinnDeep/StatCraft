"""Original finite, perspective camera math for the software 3D renderer.

The data cube is normalized per axis. Camera depth increases toward the viewer;
painters therefore draw in ascending depth order.
"""
import math
import numbers


DEFAULT_VIEW = {'azimuth': -35.0, 'elevation': 25.0, 'zoom': 1.0}


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError('3D camera values must be finite numbers.')
    return float(value)


def view_state(azimuth=-35.0, elevation=25.0, zoom=1.0, pan_x=0.0, pan_y=0.0):
    azimuth, elevation, zoom = map(_finite, (azimuth, elevation, zoom))
    res = {'azimuth': (azimuth + 180) % 360 - 180,
           'elevation': max(-89.0, min(89.0, elevation)),
           'zoom': max(.4, min(2.5, zoom))}
    if pan_x != 0.0 or pan_y != 0.0:
        res['pan_x'] = _finite(pan_x)
        res['pan_y'] = _finite(pan_y)
    return res


def normalize_point(point, ranges):
    if len(point) != 3 or len(ranges) != 3:
        raise ValueError('3D coordinates require three axes.')
    output = []
    for value, limits in zip(point, ranges):
        if len(limits) != 2:
            raise ValueError('3D axis bounds require two limits.')
        value, low, high = map(_finite, (value, *limits))
        span = high - low
        if high <= low or not math.isfinite(span):
            raise ValueError('3D axis bounds must increase within finite precision.')
        normalized = 2 * ((value - low) / span) - 1
        output.append(_finite(normalized))
    return tuple(output)


def camera_point(point, state):
    """Return horizontal, vertical and toward-camera coordinates."""
    state = view_state(**state)
    if len(point) != 3:
        raise ValueError('3D coordinates require three axes.')
    x, y, z = map(_finite, point)
    az, el = map(math.radians, (state['azimuth'], state['elevation']))
    horizontal = x * math.cos(az) - y * math.sin(az)
    away = x * math.sin(az) + y * math.cos(az)
    return (horizontal, z * math.cos(el) - away * math.sin(el),
            away * math.cos(el) + z * math.sin(el))


def project_point(point, ranges, state, viewport):
    """Project a data point into (left, top, width, height), retaining depth."""
    state = view_state(**state)
    if len(viewport) != 4:
        raise ValueError('3D viewport requires left, top, width and height.')
    left, top, width, height = map(_finite, viewport)
    if width <= 0 or height <= 0:
        raise ValueError('3D viewport dimensions must be positive.')
    horizontal, vertical, depth = camera_point(normalize_point(point, ranges), state)
    distance = 6.0
    if depth >= distance - .1:
        raise ValueError('A 3D coordinate is beyond the camera near plane.')
    perspective = distance / (distance - depth)
    scale = .28 * min(width, height) * state['zoom']
    pan_x = state.get('pan_x', 0.0)
    pan_y = state.get('pan_y', 0.0)
    return (_finite(left + width / 2 + horizontal * scale * perspective + pan_x),
            _finite(top + height / 2 - vertical * scale * perspective + pan_y), depth)


def depth_order(points, ranges, state):
    """Return original point indices from farthest to nearest."""
    return sorted(range(len(points)),
                  key=lambda i: camera_point(normalize_point(points[i], ranges), state)[2])
