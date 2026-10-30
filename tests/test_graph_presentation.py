import copy
import unittest
from statcraft.graph_presentation import graph_presentation, validate_presentation


class GraphPresentationTests(unittest.TestCase):
    def test_defaults_labels_and_no_mutation(self):
        entry = {'title': 'Histogram of Strength', 'result': {'graph': 'histogram', 'variable': 'Strength'}}
        before = copy.deepcopy(entry)
        settings = graph_presentation(entry)
        self.assertEqual(settings['x_label'], 'Strength')
        self.assertEqual(settings['y_label'], 'Frequency')
        self.assertEqual(settings['subtitle'], '')
        self.assertFalse(settings['subtitle_enabled'])
        self.assertEqual(entry, before)

    def test_expanded_labels_and_saved_overrides(self):
        entry = {'title': 'Scatter', 'result': {'panels': [{'x_label': 'Load', 'y_label': 'Response'}]},
                 'graph_presentation': {'title': '', 'title_enabled': False, 'x_position': 'high', 'x_min': 2, 'x_max': 8}}
        settings = graph_presentation(entry)
        self.assertEqual(settings['x_label'], 'Load')
        self.assertEqual(settings['y_label'], 'Response')
        self.assertEqual(settings['x_min'], 2.0)
        self.assertFalse(settings['title_enabled'])

    def test_3d_axes_and_empty_title(self):
        settings = graph_presentation({'title': '', 'result': {'panels': [{'axes': ['A', 'B', 'C']}]}})
        self.assertEqual((settings['x_label'], settings['y_label']), ('A', 'B'))
        self.assertFalse(settings['title_enabled'])

    def test_invalid_bounds_are_rejected(self):
        for invalid in ({'x_min': 5, 'x_max': 5}, {'y_min': 9, 'y_max': 1}, {'x_min': float('nan')},
                        {'x_max': float('inf')}, {'y_min': True}, {'y_max': '2'},
                        {'x_min': 1}, {'y_max': 2}, {'x_min': -1e308, 'x_max': 1e308}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_presentation(invalid)

    def test_invalid_settings_and_length_are_rejected(self):
        for invalid in ({'title': 'x' * 146}, {'subtitle': None}, {'x_position': 'top'},
                        {'title_enabled': 1}, {'grid_enabled': 'yes'}, {'unknown': 1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_presentation(invalid)
        self.assertEqual(len(validate_presentation({'title': 'x' * 145})['title']), 145)

    def test_detached_settings_and_automatic_range(self):
        raw = {'x_min': 5, 'x_max': 20, 'footnote': 'Note', 'footnote_enabled': False}
        validated = validate_presentation(raw)
        validated['footnote'] = 'Changed'
        self.assertEqual(raw['footnote'], 'Note')
        self.assertIsNone(validated['y_max'])


if __name__ == '__main__': unittest.main()
