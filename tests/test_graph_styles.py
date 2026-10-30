import copy
import json
import unittest

from statcraft.graph_styles import style_for, validate_styles


class GraphStylesTests(unittest.TestCase):
    def test_sparse_styles_normalize_and_round_trip(self):
        raw = {'p0:s0': {'color': '#AAbbCC', 'fill': '#123456AA', 'line_width': 2,
                         'line_style': 'dash', 'marker': 'diamond', 'marker_size': 8,
                         'opacity': 0.5, 'visible': True, 'legend_visible': False}}
        result = validate_styles(raw)
        self.assertEqual(result['p0:s0']['color'], '#aabbcc')
        self.assertEqual(result['p0:s0']['fill'], '#123456aa')
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)
        self.assertEqual(raw['p0:s0']['color'], '#AAbbCC')

    def test_all_target_types_and_empty_styles(self):
        targets = ('p0:s0', 'p12:s345', 'p0:bars', 'p1:box', 'p2:axis',
                   'p3:grid', 'p4:fit0', 'p5:ref12')
        raw = {target: {} for target in targets}
        self.assertEqual(validate_styles(raw), raw)
        self.assertEqual(validate_styles({}), {})

    def test_resolution_preserves_defaults_and_input(self):
        styles = {'p0:s0': {'color': '#123456', 'marker': 'none'}}
        defaults = {'color': '#ABCDEF', 'line_width': 1, 'marker': 'circle'}
        before = copy.deepcopy((styles, defaults))
        actual = style_for(styles, 'p0:s0', defaults)
        self.assertEqual(actual, {'color': '#123456', 'line_width': 1.0, 'marker': 'none'})
        actual['color'] = '#654321'
        self.assertEqual((styles, defaults), before)
        self.assertEqual(style_for(styles, 'p1:s0', defaults)['color'], '#abcdef')

    def test_result_is_deeply_detached(self):
        raw = {'p0:bars': {'fill': '#123456'}}
        result = validate_styles(raw)
        result['p0:bars']['fill'] = '#abcdef'
        result['p1:bars'] = {}
        self.assertEqual(raw, {'p0:bars': {'fill': '#123456'}})

    def test_invalid_targets_are_rejected(self):
        for target in ('', 's0', 'p-1:s0', 'p0:unknown', 'p0:s0\n', 'p0:fit',
                       'p0:s-1', 'p0:ref-1', 'p١:s0', None, 1):
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_styles({target: {}})
        with self.assertRaises(ValueError):
            style_for({}, 'anything')

    def test_invalid_colors_and_fields_are_rejected(self):
        for color in ('red', '#fff', '#12345', '#123456789', '#gg1234', '#123456\n', None, 123456):
            for field in ('color', 'fill', 'edge'):
                with self.subTest(color=color, field=field), self.assertRaises(ValueError):
                    validate_styles({'p0:s0': {field: color}})
        for raw in (None, [], {'p0:s0': []}, {'p0:s0': {'result': 3}}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_styles(raw)

    def test_numeric_bounds_and_types_are_enforced(self):
        invalid = {'line_width': (-1, 13, True, '2', float('nan'), float('inf')),
                   'marker_size': (0, 31, False, None), 'opacity': (-0.1, 1.1, True)}
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_styles({'p0:s0': {field: value}})
        self.assertEqual(validate_styles({'p0:s0': {'line_width': 0, 'marker_size': 30, 'opacity': 0}})
                         ['p0:s0'], {'line_width': 0.0, 'marker_size': 30.0, 'opacity': 0.0})

    def test_enum_and_boolean_values_are_exact(self):
        for field, value in (('line_style', 'dashed'), ('line_style', []), ('marker', 'star'),
                             ('marker', {}), ('visible', 1), ('legend_visible', 'true')):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_styles({'p0:s0': {field: value}})

    def test_failed_validation_does_not_partially_apply(self):
        raw = {'p0:s0': {'color': '#ABCDEF'}, 'p0:s1': {'line_width': -3}}
        before = copy.deepcopy(raw)
        with self.assertRaises(ValueError):
            validate_styles(raw)
        self.assertEqual(raw, before)
        with self.assertRaises(ValueError):
            style_for(raw, 'p0:s0', {'line_width': 1})


if __name__ == '__main__':
    unittest.main()
