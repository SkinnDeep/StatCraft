"""Read inert saved MPX output groups without executing native commands.

The schema is established from shipped MPX JSON: graph references are object
paths into package members; response surfaces carry saved meshes and contour
polygons. Unsupported graph forms remain visible with an explicit warning.
"""
import json
import math
from statistics import NormalDist

MAX_ITEMS = 100
MAX_POINTS = 100000


class _Reader:
    def __init__(self, members):
        self.members = members
        self.cache = {}

    def resolve(self, value, depth=0):
        if not isinstance(value, str) or not value.startswith('/'):
            return value
        if depth >= 24 or '..' in value.split('/') or '\\' in value:
            return None
        parts = value.split('/')
        for end in range(len(parts), 1, -1):
            name = '/'.join(parts[:end]) + '.json'
            if name not in self.members:
                continue
            if name not in self.cache:
                raw = self.members[name]
                if len(raw) > 32 * 1024 * 1024:
                    return None
                try:
                    self.cache[name] = json.loads(raw)
                except (ValueError, TypeError, RecursionError):
                    return None
            obj = self.cache[name]
            try:
                for key in parts[end:]:
                    obj = obj[int(key)] if isinstance(obj, list) else obj[key]
            except (KeyError, ValueError, TypeError, IndexError):
                return None
            if isinstance(obj, str) and obj == value:
                return None
            return self.resolve(obj, depth + 1)
        return None

    def vector(self, obj, depth=0):
        obj = self.resolve(obj)
        if depth > 15 or not isinstance(obj, dict):
            return []
        for key in ('NumericData', 'TextData'):
            data = obj.get(key)
            if isinstance(data, list) and data:
                return data[:MAX_POINTS]
        for key in ('WorksheetVar', 'WorksheetVarBody', 'VarData', 'VarDataBody'):
            values = self.vector(obj.get(key), depth + 1)
            if values:
                return values
        if obj.get('Numeric') is True and _number(obj.get('Value')):
            return [obj['Value']]
        return []

    def label(self, obj, depth=0):
        obj = self.resolve(obj)
        if depth > 12 or not isinstance(obj, dict):
            return ''
        if isinstance(obj.get('Base'), str):
            return obj['Base'][:4096]
        values = self.vector(obj)
        if values and isinstance(values[0], str):
            return ' '.join(str(v) for v in values[:20])[:4096]
        for key in ('Value', 'LabelText', 'OverallAxisLabel', 'AxisLabel'):
            text = self.label(obj.get(key), depth + 1)
            if text:
                return text
        return ''


def _number(x):
    return type(x) in (int, float) and math.isfinite(x) and abs(x) < 1e29


def _format(value, col=None, row=None):
    if isinstance(value, dict):
        obj = value.get('Value', value)
        if not isinstance(obj, dict):
            return str(obj)[:4096]
        if 'FormattedLines' in obj:
            return ' '.join(str(v).replace('\u00a0', ' ') for v in obj['FormattedLines'][:100])[:4096]
        if 'Base' in obj:
            base = str(obj['Base']).replace('\u00a0', ' ')[:4096]
            if '%' in base and any('%' + str(i) in base for i in range(1, 10)):
                return ''  # Unexpanded sentence templates are not display text.
            return base
        return str(obj.get('Label', ''))[:4096]
    if _number(value):
        fmt = (col or {}).get('Format', {}).get('Value', {})
        cell_formats = (col or {}).get('CellFormats', [])
        if row is not None and row < len(cell_formats):
            fmt = cell_formats[row].get('Value', fmt)
        if fmt.get('Subtype') == 4:
            places = fmt.get('NumericFmtSubtype', {}).get('DecimalPlaces', 2)
            return format(value * 100, '.' + str(max(0, min(12, int(places)))) + 'f') + '%'
        if fmt.get('Numeric') == 0 and isinstance(fmt.get('NumDecPlaces'), int):
            return format(value, '.' + str(max(0, min(12, fmt['NumDecPlaces']))) + 'f')
        return format(value, '.10g')
    if isinstance(value, (int, float)):
        # Missing sentinel in Minitab tables is 1.23456e+30 or >= 1e29 (render blank in tables)
        if abs(value) >= 1e29:
            return ''
        return '*'
    return str(value)[:4096]


def _report(data):
    if not isinstance(data, dict):
        return ''
    if 'Base' in data:
        return _format(data)
    titles = [_report(v.get('Value', {})) for v in data.get('Titles', []) if isinstance(v, dict)]
    lines = [t for t in titles if t]
    columns = []
    for item in data.get('TableCol', [])[:64]:
        col = item.get('Value', {}) if isinstance(item, dict) else {}
        labels = [_format(v) for v in (col.get('Labels') or col.get('UnformattedLabels', []))[:8]]
        values = col.get('StringValues', col.get('Values', col.get('Cells', [])))
        if not isinstance(values, list):
            values = []
        cells = [_format(v, col, row) for row, v in enumerate(values[:4096])]
        columns.append((' '.join(labels), cells))
    if columns:
        widths = [min(60, max([len(label)] + [len(v) for v in cells] + [1])) for label, cells in columns]
        if any(label for label, cells in columns):
            lines.append('  '.join(label.ljust(w) for (label, _), w in zip(columns, widths)).rstrip())
        for row in range(max((len(cells) for _, cells in columns), default=0)):
            lines.append('  '.join((cells[row] if row < len(cells) else '').ljust(w)
                                   for (_, cells), w in zip(columns, widths)).rstrip())
    for item in data.get('Footnotes', [])[:64]:
        if isinstance(item, dict):
            text = _report(item.get('Value', {}))
            if text:
                lines.append(text)
    return '\n'.join(lines)


def _axis(reader, figure, axis, panel_index=0):
    states = figure.get('AxisLabelStates', [])
    if axis < len(states):
        state = states[axis]
        labels = state.get('AxisLabels', [])
        if panel_index < len(labels):
            text = reader.label(labels[panel_index])
            if text and text not in ('Default Axis Label', 'Axis Label'):
                return text
        for key in ('OverallAxisLabel', 'AxisLabel'):
            text = reader.label(state.get(key))
            if text and text != 'Default Axis Label':
                return text
    return ''


def _grid(model, key):
    obj = model.get(key)
    if not isinstance(obj, dict):
        return None
    xs, ys, zs = obj.get('XMesh'), obj.get('YMesh'), obj.get('ZValues')
    if (not isinstance(xs, list) or not isinstance(ys, list) or not isinstance(zs, list)
            or not (2 <= len(xs) <= 512 and 2 <= len(ys) <= 512)
            or len(xs) * len(ys) != len(zs) or len(zs) > MAX_POINTS
            or not all(_number(v) for v in xs + ys + zs)):
        return None
    return {'x': xs[:], 'y': ys[:], 'z': [zs[i:i + len(xs)] for i in range(0, len(zs), len(xs))]}


def _series(reader, model, kind, group_vals=None, group_name=''):
    if 'BinCountCol' in model:
        xs = reader.vector(model.get('MidPointCol'))
        ys = reader.vector(model.get('BinCountCol'))
        cut = reader.vector(model.get('CutPointCol'))
    else:
        xs, ys = reader.vector(model.get('XCol')), reader.vector(model.get('YCol'))
        cut = []
    if xs and not ys and kind == 'probability':
        xs = sorted(x for x in xs if _number(x))
        if not xs:
            return []
        count = len(xs)
        # Display-only ranks; native serialized output retains residual values
        # and fitted distribution, but does not store its symbol ordinates.
        ys = [NormalDist().inv_cdf((i + 1 - .3) / (count + .4)) for i in range(count)]
    if not xs or not ys:
        return []
    count = min(len(xs), len(ys), MAX_POINTS)
    categories = []
    if all(isinstance(v, str) for v in xs[:count]):
        categories = xs[:count]
        xs = list(range(1, count + 1))
    points = [(x, y) for x, y in zip(xs[:count], ys[:count]) if _number(x) and _number(y)]
    if not points:
        return []

    # If grouping variable exists (e.g. Interaction Plot), separate into distinct curves
    if group_vals and len(group_vals) >= count:
        from collections import defaultdict
        grouped = defaultdict(list)
        for x, y, g in zip(xs[:count], ys[:count], group_vals[:count]):
            if _number(x) and _number(y):
                grouped[g].append((x, y))
        out = []
        palette = ['#0054a6', '#931313', '#00841f', '#9112b6', '#515151', '#cf8703']
        for i, (g_val, pairs) in enumerate(grouped.items()):
            pairs.sort(key=lambda p: p[0])
            lbl = f"{group_name}: {g_val:g}" if group_name and isinstance(g_val, float) else f"{group_name}: {g_val}" if group_name else str(g_val)
            entry = {'x': [p[0] for p in pairs], 'y': [p[1] for p in pairs],
                     'kind': kind, 'color': palette[i % len(palette)],
                     'label': lbl}
            out.append(entry)
        return out

    groups = [[]]
    for pair in points:
        # Saved interaction curves concatenate increasing X sequences. Preserve
        # their boundaries rather than joining the end of one curve to the next.
        if kind == 'line' and groups[-1] and pair[0] < groups[-1][-1][0]:
            groups.append([])
        groups[-1].append(pair)
    out = []
    for i, pairs in enumerate(groups):
        entry = {'x': [p[0] for p in pairs], 'y': [p[1] for p in pairs],
                 'kind': kind, 'color': ['#0054a6', '#ce0000', '#00843d', '#9b59b6'][i % 4]}
        if categories:
            entry['categories'] = categories
        if cut and all(_number(v) for v in cut):
            entry['edges'] = cut
        out.append(entry)
    return out


def _figure(reader, figure):
    figure = reader.resolve(figure)
    if not isinstance(figure, dict):
        return []
    models = [reader.resolve(m) for m in figure.get('GraphModels', [])[:64]]
    if not models:
        return []
    reps = figure.get('DataRepList', [])
    graph_types = [r.get('GraphType') for r in reps if isinstance(r, dict)]
    tags = {d.get('Value', {}).get('Tag') for r in reps if isinstance(r, dict)
            for d in r.get('DataReps', []) if isinstance(d, dict) and d.get('Value', {}).get('Show', True)}
    surface = any(isinstance(m, dict) and 'RSPlotContourGrid' in m for m in models)
    contour = any(isinstance(m, dict) and 'ContourGrid' in m for m in models)
    kind = ('surface' if surface else 'contour' if contour else 'histogram' if any(isinstance(m, dict) and 'BinCountCol' in m for m in models)
            else 'probability' if 12 in graph_types and figure.get('FigureState', {}).get('DistributionType', {}).get('DistributionType') == 1
            else 'bar' if 4 in [d.get('Key') for r in reps if isinstance(r, dict) for d in r.get('DataReps', []) if isinstance(d, dict)]
            else 'line' if any('Connect Line' in str(t) for t in tags) or any(gt in (16, 17, 57) for gt in graph_types) else 'scatter')
    panels = figure.get('Panels', [])[:64] or [{}]

    # Check legend for group column in interaction / grouped plots
    group_vals = []
    group_name = ''
    for leg in figure.get('Legends', []):
        for sec in leg.get('LegendSection', []):
            header = sec.get('SectionHeader', {}).get('SectionHeader', [])
            if header: group_name = header[0]
            for cvar in sec.get('ColumnVars', []):
                vals = reader.vector(cvar)
                if vals:
                    group_vals = vals
                    name = cvar.get('WorksheetVarBody', {}).get('Name')
                    if name: group_name = name
                    break

    output = []
    for panel_index, native_panel in enumerate(panels):
        ids = native_panel.get('GraphModels', list(range(len(models))))

        # Detect panel label (e.g. Factor name 'A', 'B' in multi-panel Main Effects)
        p_label = native_panel.get('PanelLabel', {}).get('PanelLabel')
        if not p_label:
            for index in ids[:64]:
                if 0 <= index < len(models) and isinstance(models[index], dict):
                    m_name = models[index].get('XCol', {}).get('WorksheetVar', {}).get('WorksheetVarBody', {}).get('Name')
                    if m_name:
                        p_label = m_name
                        break
        x_lbl = p_label or _axis(reader, figure, 0, panel_index)

        panel = {'kind': kind, 'x_label': x_lbl, 'y_label': _axis(reader, figure, 1, panel_index),
                 'z_label': _axis(reader, figure, 2), 'series': [], 'title': p_label or native_panel.get('XLabel', '')}
        frame = native_panel.get('Frame', {})
        transform = frame.get('DataDeviceXTransform', {})
        bounds = [transform.get(k) for k in ('AXMin', 'AXMax', 'AYMin', 'AYMax')]
        if all(_number(v) for v in bounds) and bounds[0] < bounds[1] and bounds[2] < bounds[3]:
            panel['bounds'] = bounds
        for axis in ('X', 'Y'):
            ticks = frame.get(axis + 'GridLine', {}).get('MajorTickPositions', [])
            if isinstance(ticks, list) and len(ticks) <= 100 and all(_number(v) for v in ticks):
                panel[axis.lower() + '_ticks'] = ticks

        # Extract reference lines (XReference / YReference)
        ref_lines = []
        for ref_key, orientation in (('XReference', 'x'), ('YReference', 'y')):
            for ref in frame.get(ref_key, []):
                if not isinstance(ref, dict) or ref.get('Show') is False:
                    continue
                ref_state = ref.get('ReferenceState', {})
                pos_val = ref_state.get('ReferencePos', {}).get('Value')
                if not _number(pos_val):
                    continue
                rgba = ref_state.get('RGBA', 'ce0000ff')
                color = '#' + rgba[:6] if len(rgba) >= 6 else '#ce0000'
                l_type = ref_state.get('Type', {}).get('Value', 3)
                style = 'dash' if l_type in (2, 3) else 'solid'
                b_label_state = ref_state.get('BorderLabelState', {})
                label_text = reader.label(b_label_state.get('LabelText')) or ''
                if not label_text and _number(pos_val):
                    label_text = f"{pos_val:.3g}"
                ref_lines.append({
                    'axis': orientation,
                    'pos': float(pos_val),
                    'color': color,
                    'style': style,
                    'label': label_text,
                    'tag': ref.get('Tag', '')
                })

        for index in ids[:64]:
            if type(index) is not int or not 0 <= index < len(models) or not isinstance(models[index], dict):
                continue
            model = models[index]
            if surface or contour:
                grid = _grid(model, 'RSPlotContourGrid' if surface else 'ContourGrid')
                if grid:
                    panel['grid'] = grid
                levels = figure.get('ContourLevelsC', [])
                if isinstance(levels, list) and len(levels) < 100 and all(_number(v) for v in levels):
                    panel['levels'] = levels
                polygons = []
                colors = ['#ffffcc', '#c2e699', '#78c679', '#31a354', '#006837', '#004529', '#00331f']
                for legend in figure.get('Legends', []):
                    for section in legend.get('LegendSection', []):
                        for geom in section.get('LegendGeomGroups', []):
                            rgba = geom.get('DataRepState', {}).get('FillAttrib', {}).get('FillRGBA', [])
                            if rgba and all(isinstance(c, str) and len(c) == 8 for c in rgba):
                                colors = ['#' + c[:6] for c in rgba]
                panel['colors'] = colors
                for level, data in enumerate(model.get('ContourAreaData', [])[:100]):
                    for xs, ys in zip(data.get('XData', [])[:4096], data.get('YData', [])[:4096]):
                        if len(xs) == len(ys) and len(xs) < MAX_POINTS and all(_number(v) for v in xs + ys):
                            polygons.append({'x': xs, 'y': ys, 'color': colors[min(level, len(colors) - 1)]})
                if polygons:
                    panel['polygons'] = polygons
                lines = []
                for level, data in enumerate(model.get('ContourConnectData', [])[:100]):
                    for xs, ys in zip(data.get('XData', [])[:4096], data.get('YData', [])[:4096]):
                        if len(xs) == len(ys) and len(xs) < MAX_POINTS and all(_number(v) for v in xs + ys):
                            lines.append({'x': xs, 'y': ys, 'level': levels[level] if level < len(levels) else level})
                if lines:
                    panel['contour_lines'] = lines
            else:
                panel['series'].extend(_series(reader, model, kind, group_vals, group_name))
                if kind == 'probability':
                    panel['note'] = 'Symbol plotting positions reconstructed from saved residuals; fitted distribution retained.'
                    parameters = model.get('Parameters', [])
                    if parameters and len(parameters[0]) >= 2 and all(_number(v) for v in parameters[0][:2]):
                        mean, sigma = parameters[0][:2]
                        qs = [-2.3263478740043597, 2.3263478740043597]
                        panel['series'].append({'x': [mean + sigma * q for q in qs], 'y': qs,
                                                'kind': 'line', 'color': '#ce0000', 'label': 'Saved fitted normal'})
                if kind == 'bar':
                    panel['horizontal'] = True
                    category_ticks = panel.get('x_ticks', [])
                    effect_ticks = panel.get('y_ticks', [])
                    panel['x_ticks'], panel['y_ticks'] = effect_ticks, category_ticks
                    panel['x_label'], panel['y_label'] = panel['y_label'], panel['x_label']
                    for ref in ref_lines:
                        ref['axis'] = 'x' if ref['axis'] == 'y' else 'y'
                    descending = reader.vector(figure.get('FigureState', {}).get('CategoryOrder')) == [3.0]
                    for series in panel['series']:
                        cats = series.get('categories', [])
                        if len(category_ticks) == len(series['x']):
                            order = sorted(range(len(series['y'])), key=lambda i: -series['y'][i]) if descending else list(range(len(series['y'])))
                            series['y'] = [series['y'][i] for i in order]
                            if cats:
                                series['categories'] = [cats[i] for i in order]
                            series['x'] = list(reversed(category_ticks)) if figure.get('ReverseXWhenVertical') else category_ticks[:]
                            series['bar_width'] = abs(category_ticks[1] - category_ticks[0]) * .8 if len(category_ticks) > 1 else .8
                if kind == 'histogram':
                    for series in panel['series']:
                        edges = series.get('edges', [])
                        if len(edges) >= 2:
                            series['bar_width'] = edges[1] - edges[0]
        if ref_lines:
            panel['ref_lines'] = ref_lines
        if panel['series'] or panel.get('grid') or panel.get('polygons'):
            output.append(panel)
    return output


def _graph(reader, reference):
    graph = reader.resolve(reference)
    if not isinstance(graph, dict):
        return {'title': 'Saved graph', 'panels': [], 'warnings': ['Saved graph member is missing or unreadable: ' + str(reference)], 'native_uri': reference}
    if 'Graph' in graph:
        graph = graph['Graph']
    panels = []
    for fl in graph.get('FigureList', [])[:64]:
        fl = reader.resolve(fl)
        if isinstance(fl, dict):
            for fig in fl.get('Figures', [])[:64]:
                panels.extend(_figure(reader, fig))
    warnings = []
    if not panels:
        warnings.append('This saved graph has an unsupported native representation; its original data is retained in the MPX.')
    return {'title': str(graph.get('Title', 'Saved graph'))[:4096], 'panels': panels,
            'warnings': warnings + [p['note'] for p in panels if p.get('note')], 'native_uri': reference}


def read_outputs(metadata, members):
    """Return saved native groups in original order; never execute commands.

    Native records are re-read from retained package members on each load and
    must not be encoded into StatCraft's authored-result session namespace.
    """
    reader = _Reader(members)
    worksheets = {w.get('Id'): w.get('Name', '') for w in metadata.get('Worksheets', {}).get('Items', []) if isinstance(w, dict)}
    commands = metadata.get('Commands', {}).get('Items', [])
    records = []
    for command in commands[:1000] if isinstance(commands, list) else []:
        if not isinstance(command, dict):
            continue
        worksheet_id = command.get('OutputWorksheet') or command.get('InputWorksheet')
        if worksheet_id not in worksheets:
            continue
        for description in command.get('OutputGroups', [])[:100]:
            if not isinstance(description, dict):
                continue
            uri = description.get('Uri')
            group = reader.resolve(uri)
            if not isinstance(group, dict):
                group = {'ErrorText': 'Saved native output member is missing or unreadable: ' + str(uri), 'Outputs': []}
            texts, graphs, seen = [], [], set()
            def consume(outputs, depth=0):
                if depth > 16 or not isinstance(outputs, list):
                    return
                for item in outputs[:4096]:
                    if not isinstance(item, dict) or item.get('Visible') is False:
                        continue
                    data = item.get('Data', {})
                    text = _report(data)
                    if text:
                        texts.append(text)
                    ref = item.get('GraphDoc')
                    if isinstance(ref, str) and ref and ref not in seen:
                        seen.add(ref)
                        graph = _graph(reader, ref)
                        if graph:
                            graphs.append(graph)
                    consume(item.get('Outputs'), depth + 1)
            try:
                consume(group.get('Outputs', []))
            except (TypeError, ValueError, KeyError, IndexError, AttributeError, RecursionError) as exc:
                texts.append('Some saved native output uses an unsupported or damaged structure: ' + type(exc).__name__ + '.')
            if group.get('ErrorText'):
                texts.append(str(group['ErrorText'])[:4096])
            title = str(description.get('Title', 'Saved output'))[:4096]
            records.append({'entry_id': 'native:' + str(command.get('Id', '')) + ':' + str(group.get('Id', uri)),
                            'origin': 'native', 'worksheet_id': worksheet_id, 'worksheet_name': worksheets[worksheet_id],
                            'time': str(command.get('Executed', ''))[:100], 'title': title,
                            'native_command_id': command.get('Id', ''), 'native_group_uri': uri,
                            'result': {'analysis': 'native_saved_output', 'text': '\n\n'.join(texts), 'graphs': graphs,
                                       'warnings': list(dict.fromkeys(g['title'] + ': ' + warning for g in graphs for warning in g.get('warnings', []))),
                                       'source': 'Saved native project output; no analysis was rerun.'}})
            if len(records) >= MAX_ITEMS:
                return records
    return records
