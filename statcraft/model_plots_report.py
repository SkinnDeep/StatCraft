"""Structured report tables for model-driven Factorial Plots, Contour Plot and Surface Plot."""
import math


def _display(value):
    if value is None:
        return '*'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return '*'
        if math.isinf(value):
            return '-Infinity' if value < 0 else 'Infinity'
        return format(float(value), '.6g')
    return str(value)


def _hold_table(result):
    rows = []
    for h in result.get('hold_summary', []):
        role_txt = 'Factor' if h.get('role') == 'factor' else 'Continuous'
        rows.append([h.get('name', ''), role_txt, h.get('value'), str(h.get('rule', '')).title()])
    return ('Hold Values', ['Variable', 'Type', 'Hold Setting', 'Rule'], rows)


def sections(result):
    """Return (title, headers, rows) tuples for desktop Report tab, text export and Office snapshots."""
    analysis = result.get('analysis')
    resp = result.get('response_name', 'Response')
    if result.get('is_probability') and result.get('event') is not None:
        resp_label = f"{resp} (P({result['event']}))"
    else:
        resp_label = resp

    tables = []
    if analysis == 'factorial_plots':
        o = result.get('options', {})
        main_rows = []
        for me in result.get('main_effects', []):
            pts = me.get('key_points', [])
            if me.get('role') == 'factor':
                for pt in pts:
                    main_rows.append([me['name'], pt['label'], pt['value'], pt['fit'], me['effect']])
            elif len(pts) >= 3:
                for pt in pts:
                    main_rows.append([me['name'], pt['label'], pt['value'], pt['fit'], me['effect']])
        if main_rows:
            tables.append(('Main Effects Summary', ['Variable', 'Setting', 'Value', 'Fitted Mean', 'Range / Effect'], main_rows))

        int_rows = []
        for inter in result.get('interactions', []):
            pair_name = f"{inter['x_name']} * {inter['trace_name']}"
            for sr in inter.get('summary_rows', []):
                int_rows.append([
                    pair_name,
                    sr['trace_label'],
                    sr['low_fit'],
                    sr['mid_fit'],
                    sr['high_fit'],
                    sr['slope_change'],
                ])
        if int_rows:
            tables.append(('Interaction Effects Summary', ['Pair (X * Trace)', 'Trace Level', 'Low X Fit', 'Mid X Fit', 'High X Fit', 'High - Low'], int_rows))

        if result.get('hold_summary'):
            tables.append(_hold_table(result))

        method_rows = [
            ['Response', resp_label],
            ['Source model', result.get('model_title', '')],
            ['Selected variables', ', '.join(result.get('selected_names', []))],
            ['Terms to display', 'Only model terms' if o.get('terms_to_display') == 'model' else 'All terms'],
            ['Main effects plot', 'Displayed' if o.get('show_main_effects') else 'Hidden'],
            ['Interaction plot', 'Displayed' if o.get('show_interaction_plot') else 'Hidden'],
        ]
        tables.append(('Method', ['Setting', 'Value'], method_rows))
        return tables

    if analysis == 'model_contour_plot':
        o = result.get('options', {})
        grid_rows = []
        lvl_rows = []
        for p in result.get('panels', []):
            pair = f"{p['y_name']} vs {p['x_name']}"
            mn = p['min_point']
            mx = p['max_point']
            grid_rows.append([
                pair,
                f"[{_display(p['x_grid'][0])}, {_display(p['x_grid'][-1])}]",
                f"[{_display(p['y_grid'][0])}, {_display(p['y_grid'][-1])}]",
                f"{_display(mn['fit'])} at ({_display(mn['x'])}, {_display(mn['y'])})",
                f"{_display(mx['fit'])} at ({_display(mx['x'])}, {_display(mx['y'])})",
            ])
            lvl_rows.append([pair, ', '.join(_display(v) for v in p.get('levels', []))])
        tables.append(('Contour Grid Summary', ['Plot (Y vs X)', 'X Range', 'Y Range', 'Grid Minimum', 'Grid Maximum'], grid_rows))
        tables.append(('Contour Levels', ['Plot (Y vs X)', 'Levels'], lvl_rows))
        if result.get('hold_summary'):
            tables.append(_hold_table(result))
        method_rows = [
            ['Response', resp_label],
            ['Source model', result.get('model_title', '')],
            ['Grid resolution', f"{len(result['panels'][0]['x_grid'])} x {len(result['panels'][0]['y_grid'])}" if result.get('panels') else '41 x 41'],
            ['Contour display', ', '.join(k for k, flag in [('Area', o.get('show_area')), ('Contour lines', o.get('show_lines')), ('Design points', o.get('show_design_points'))] if flag)],
        ]
        tables.append(('Method', ['Setting', 'Value'], method_rows))
        return tables

    if analysis == 'model_surface_plot':
        o = result.get('options', {})
        grid_rows = []
        for p in result.get('panels', []):
            pair = f"{p['y_name']} vs {p['x_name']}"
            cp = p['center_point']
            mn = p['min_point']
            mx = p['max_point']
            grid_rows.append([
                pair,
                f"{_display(cp['fit'])} at ({_display(cp['x'])}, {_display(cp['y'])})",
                f"{_display(mn['fit'])} at ({_display(mn['x'])}, {_display(mn['y'])})",
                f"{_display(mx['fit'])} at ({_display(mx['x'])}, {_display(mx['y'])})",
            ])
        tables.append(('Surface Grid Summary', ['Surface (Y vs X)', 'Center Fit', 'Grid Minimum', 'Grid Maximum'], grid_rows))
        if result.get('hold_summary'):
            tables.append(_hold_table(result))
        method_rows = [
            ['Response', resp_label],
            ['Source model', result.get('model_title', '')],
            ['Grid resolution', f"{len(result['panels'][0]['x_grid'])} x {len(result['panels'][0]['y_grid'])}" if result.get('panels') else '25 x 25'],
            ['Surface style', 'Shaded surface with wireframe' if o.get('surface_style') == 'shaded' else 'Wireframe only'],
        ]
        tables.append(('Method', ['Setting', 'Value'], method_rows))
        return tables

    return tables


def text_report(result):
    analysis = result.get('analysis')
    resp = result.get('response_name', 'Response')
    heading = {
        'factorial_plots': f"Factorial Plots for {resp}",
        'model_contour_plot': f"Contour Plot of {resp}",
        'model_surface_plot': f"Surface Plot of {resp}",
    }.get(analysis, f"Model Plot of {resp}")
    lines = [heading, '']
    for title, headers, rows in sections(result):
        data = [[_display(v) for v in row] for row in rows]
        widths = [
            max(len(str(h)), max((len(row[i]) for row in data), default=0))
            for i, h in enumerate(headers)
        ]
        lines.append(title)
        lines.append('  '.join(str(h).ljust(w) for h, w in zip(headers, widths)))
        for row in data:
            lines.append('  '.join(v.ljust(w) for v, w in zip(row, widths)))
        lines.append('')
    if result.get('method_notes'):
        lines.append(result['method_notes'])
    for w in result.get('warnings', []):
        lines.append(str(w))
    return '\n'.join(lines)
