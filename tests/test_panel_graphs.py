import copy
import json
import unittest

from statcraft.model import Column, Worksheet
from statcraft.panel_graphs import build_panels, source_columns, validate_parameters


def histogram():
    return {'action': 'graph', 'parameters': {'method': 'histogram', 'indices': [0], 'bins': 2}}


def scatter(mode='simple'):
    return {'action': 'scatter_plot', 'parameters': {'x_index': 0, 'y_index': 1,
        'mode': mode, 'group_index': None, 'order': 'Increasing X',
        'title': '', 'x_label': '', 'y_label': ''}}


class PanelGraphTests(unittest.TestCase):
    def sheet(self):
        return Worksheet('Measurements', [Column('X', values=[5, 1, 6, 2, 7, 3]),
            Column('Y', values=[50, 10, 60, 20, 70, 30]),
            Column('Batch', 'text', ['B', 'A', 'B', 'A', 'B', 'A']),
            Column('Shift', values=[2, 1, 1, 2, 2, 1])])

    def test_histograms_are_independent_and_input_unchanged(self):
        sheet = self.sheet()
        recipe = histogram()
        before = copy.deepcopy((sheet, recipe))
        result = build_panels(sheet, recipe, [2])
        self.assertEqual([facet['label'] for facet in result['facets']], ['Batch = A', 'Batch = B'])
        self.assertEqual([facet['rows'] for facet in result['facets']], [[2, 4, 6], [1, 3, 5]])
        self.assertEqual(result['graphs'][0]['result']['histogram_source'], [1, 2, 3])
        self.assertEqual(result['graphs'][1]['result']['histogram_source'], [5, 6, 7])
        self.assertNotEqual(result['graphs'][0]['result']['graph_data'], result['graphs'][1]['result']['graph_data'])
        self.assertNotIn('recipe', result['graphs'][0])
        self.assertEqual(result['columns'], 2)
        self.assertEqual((sheet, recipe), before)
        json.dumps(result, allow_nan=False)

    def test_connect_rows_remap_to_original_identity(self):
        result = build_panels(self.sheet(), scatter('connect'), [2])
        series = result['graphs'][0]['result']['series'][0]
        self.assertEqual(series['x'], [1, 2, 3])
        self.assertEqual(series['row_indices'], [2, 4, 6])
        self.assertEqual(result['graphs'][1]['result']['series'][0]['row_indices'], [1, 3, 5])

    def test_custom_and_occurrence_order(self):
        sheet = self.sheet()
        sheet.columns[2].metadata['value_order'] = {'mode': 'custom', 'values': ['B', 'A']}
        custom = build_panels(sheet, histogram(), [2])
        self.assertEqual(custom['facets'][0]['label'], 'Batch = B')
        sheet.columns[2].metadata['value_order'] = {'mode': 'occurrence', 'values': []}
        self.assertEqual(build_panels(sheet, histogram(), [2])['facets'][0]['label'], 'Batch = B')

    def test_two_by_columns_use_observed_combinations_numeric_order(self):
        result = build_panels(self.sheet(), histogram(), [2, 3], False, True)
        self.assertEqual([facet['label'] for facet in result['facets']],
            ['Batch = A, Shift = 1', 'Batch = A, Shift = 2',
             'Batch = B, Shift = 1', 'Batch = B, Shift = 2'])
        self.assertFalse(result['shared_x'])
        self.assertTrue(result['shared_y'])
        self.assertEqual(result['count'], 4)

    def test_missing_and_empty_by_values_are_omitted(self):
        sheet = self.sheet()
        sheet.columns[2].values = ['B', '', None, 'A']
        result = build_panels(sheet, histogram(), [2])
        self.assertEqual([facet['rows'] for facet in result['facets']], [[4], [1]])
        sheet.columns[2].values = ['', None]
        with self.assertRaisesRegex(ValueError, 'no complete'):
            build_panels(sheet, histogram(), [2])

    def test_maximum_panels_checked_before_calculation(self):
        sheet = self.sheet()
        sheet.columns[2].values = [str(i) for i in range(17)]
        with self.assertRaisesRegex(ValueError, 'at most 16'):
            build_panels(sheet, histogram(), [2])

    def test_child_calculation_failure_has_group_label_and_is_atomic(self):
        sheet = self.sheet()
        sheet.columns[0].values = [None, 1, None, 2, None, 3]
        before = copy.deepcopy(sheet)
        with self.assertRaisesRegex(ValueError, 'Cannot create panel Batch = B'):
            build_panels(sheet, histogram(), [2])
        self.assertEqual(sheet, before)

    def test_invalid_parameters_and_recursive_recipes(self):
        for indices in ([], [2, 2], [True], [-1], [1, 2, 3], ['2']):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                validate_parameters(histogram(), indices)
        for source in (None, {}, {'action': 'panel_graph', 'parameters': {}},
                       {'action': 'describe_column', 'parameters': {'index': 0}}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_parameters(source, [2])
        with self.assertRaises(ValueError):
            validate_parameters(histogram(), [2], 1, False)
        with self.assertRaises(ValueError):
            build_panels(self.sheet(), histogram(), [40])
        sheet = self.sheet(); sheet.columns[2] = Column('Date', 'date', [45000] * 6)
        with self.assertRaisesRegex(ValueError, 'numeric or text'):
            build_panels(sheet, histogram(), [2])

    def test_parameters_and_dependencies_are_detached(self):
        source = scatter()
        result = validate_parameters(source, [2, 3])
        self.assertEqual(source_columns(**result), [0, 1, 2, 3])
        result['source_recipe']['parameters']['x_index'] = 10
        self.assertEqual(source['parameters']['x_index'], 0)

    def test_expanded_scatter_preserves_original_rows(self):
        source = {'action': 'expanded_graph', 'parameters': {'method': 'matrix_plot',
            'indices': [0, 1], 'group_index': None, 'bins': 10,
            'confidence': .95, 'distribution': 'Normal', 'parameters': {}}}
        result = build_panels(self.sheet(), source, [2])
        plotted = [series['row_indices'] for panel in result['graphs'][0]['result']['panels']
                   for series in panel.get('series', []) if 'row_indices' in series]
        self.assertTrue(plotted)
        self.assertTrue(all(rows == [2, 4, 6] for rows in plotted))

    def test_singleton_interval_reports_affected_facet(self):
        source = {'action': 'expanded_graph', 'parameters': {'method': 'interval_plot',
            'indices': [0], 'group_index': None, 'bins': 10,
            'confidence': .95, 'distribution': 'Normal', 'parameters': {}}}
        with self.assertRaisesRegex(ValueError, 'Batch = A, Shift = 2: Mean intervals'):
            build_panels(self.sheet(), source, [2, 3])


if __name__ == '__main__':
    unittest.main()
