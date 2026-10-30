"""Source identities must survive structure edits without changing options."""
import copy
import unittest
from statcraft.analysis_bindings import normalize, resolve, binding_columns, KEY
from statcraft.model import Worksheet, Column
from statcraft.recipe_columns import remap_recipe, remap_mapping, state, restore
from statcraft.recipes import columns


class AnalysisBindingTests(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet('Data', [Column('Weight', 'number', [1., 2., 3.]),
            Column('Length', 'number', [4., 5., 6.]),
            Column('Size', 'number', [2., 2., 2.]),
            Column('Defect', 'text', ['A', 'B', 'A'])])

    def recipe(self, action, settings):
        return {'action': action, 'parameters': {'settings': normalize(action, self.ws, settings)}}

    def test_tolerance_move_then_rename_uses_identity(self):
        recipe = self.recipe('tolerance_intervals', {'variable_indices': [0], 'settings': {'min_percent': 95}})
        moved = remap_recipe(recipe, {0: 1, 1: 0, 2: 2, 3: 3})
        self.ws.columns[0], self.ws.columns[1] = self.ws.columns[1], self.ws.columns[0]
        self.ws.columns[1].name = 'Mass'
        result = resolve('tolerance_intervals', self.ws, moved['parameters']['settings'])
        self.assertEqual(result['variable_indices'], [1])
        self.assertEqual(columns(moved), [1])
        self.assertEqual(result['settings'], {'min_percent': 95})

    def test_summarized_tolerance_has_no_phantom_default_column(self):
        recipe = self.recipe('tolerance_intervals', {'is_summarized': True, 'variable_indices': [0], 'n': 20, 'mean': 1, 'std': 2})
        self.assertEqual(columns(recipe), [])
        self.assertEqual(columns(remap_recipe(recipe, {})), [])

    def test_normal_single_and_subgroup_follow_move(self):
        recipe = self.recipe('normal_capability', {'column_name': 'Weight', 'subgroup_spec': 'Size', 'lsl': 1, 'usl': 3, 'options': {'target': 2}})
        moved = remap_recipe(recipe, {0: 2, 1: 1, 2: 0, 3: 3})
        self.ws.columns[0], self.ws.columns[2] = self.ws.columns[2], self.ws.columns[0]
        self.ws.columns[0].name = 'Batch'
        result = resolve('normal_capability', self.ws, moved['parameters']['settings'])
        self.assertEqual((result['column_name'], result['subgroup_spec']), (2, 'Batch'))
        self.assertEqual((result['lsl'], result['usl'], result['options']['target']), (1, 3, 2))

    def test_normal_across_ignores_inactive_single_selectors(self):
        recipe = self.recipe('normal_sixpack', {'single_column': False, 'cols_across': ['Weight', 'Length'], 'column_index': 3, 'subgroup_col_index': 2})
        self.assertEqual(columns(recipe), [0, 1])

    def test_attribute_constants_are_not_indices(self):
        recipe = self.recipe('attribute_control_chart', {'variables': [0], 'is_subgroup_col': False, 'subgroup_col_idx': 2, 'subgroup_size': 2, 'chart_type': 'P', 'options': {'omit_subgroups': [1, 2]}})
        moved = remap_recipe(recipe, {0: 1})
        settings = moved['parameters']['settings']
        self.assertEqual(columns(moved), [1])
        self.assertEqual(settings['subgroup_size'], 2)
        self.assertEqual(settings['options']['omit_subgroups'], [1, 2])

    def test_attribute_size_source_is_tracked(self):
        recipe = self.recipe('attribute_control_chart', {'variables': [0], 'is_subgroup_col': True, 'subgroup_col_idx': 2, 'chart_type': 'P'})
        self.assertEqual(columns(recipe), [0, 2])
        with self.assertRaises(KeyError):
            remap_recipe(recipe, {0: 0})

    def test_time_subgroup_column_refreshes_values(self):
        recipe = self.recipe('time_weighted_control_chart', {'columns': ['Weight'], 'subgroup_text': 'Size', 'subgroup_spec': [2, 2, 2]})
        self.ws.columns[2].name = 'Batch Size'
        self.ws.columns[2].values[0] = 3
        result = resolve('time_weighted_control_chart', self.ws, recipe['parameters']['settings'])
        self.assertEqual(result['subgroup_text'], 'Batch Size')
        self.assertEqual(result['subgroup_spec'], [3, 2, 2])
        self.assertEqual(columns(recipe), [0, 2])

    def test_time_rows_ignore_inactive_subgroup_column(self):
        recipe = self.recipe('time_weighted_control_chart', {'arranged_mode': 1, 'columns': ['Weight', 'Length'], 'subgroup_text': 'Size', 'subgroup_spec': [2, 2, 2]})
        self.assertEqual(columns(recipe), [0, 1])

    def test_time_constant_size_is_not_column(self):
        recipe = self.recipe('time_weighted_control_chart', {'columns': ['Weight'], 'subgroup_text': '2', 'subgroup_spec': 2})
        self.assertEqual(columns(recipe), [0])

    def test_multivariate_size_constant_and_column_distinct(self):
        recipe = self.recipe('multivariate_control_chart', {'variables': ['Weight', 'Length'], 'subgroup_size': 2})
        self.assertEqual(columns(recipe), [0, 1])
        recipe = self.recipe('multivariate_control_chart', {'variables': ['Weight', 'Length'], 'subgroup_size': 'Size'})
        self.assertEqual(columns(recipe), [0, 1, 2])
        self.ws.columns[2].name = 'Group'
        result = resolve('multivariate_control_chart', self.ws, recipe['parameters']['settings'])
        self.assertEqual(result['subgroup_size'], 'Group')

    def test_pareto_tracks_defect_count_and_by(self):
        recipe = self.recipe('pareto_chart', {'is_summarized': True, 'defect_column': 'Defect', 'count_column': 'Length', 'by_column': 'Size'})
        self.assertEqual(columns(recipe), [1, 2, 3])
        moved = remap_recipe(recipe, {0: 3, 1: 2, 2: 1, 3: 0})
        self.ws.columns.reverse()
        settings = resolve('pareto_chart', self.ws, moved['parameters']['settings'])
        self.assertEqual((settings['defect_column'], settings['count_column'], settings['by_column']), (0, 2, 1))

    def test_pareto_raw_ignores_old_count_selector(self):
        recipe = self.recipe('pareto_chart', {'defect_column': 'Defect', 'count_column': 'Length'})
        self.assertEqual(columns(recipe), [3])

    def test_narrow_recipe_ignores_stale_variable_cache(self):
        settings = normalize('rare_event_control_chart', self.ws, {'columns': ['Weight', 'Length']})
        settings['columns'] = ['Length']
        settings.pop(KEY)
        self.assertEqual(binding_columns('rare_event_control_chart', normalize('rare_event_control_chart', self.ws, settings)), [1])

    def test_missing_or_duplicate_names_fail(self):
        for name in ('Unknown',):
            with self.assertRaises(ValueError):
                normalize('pareto_chart', self.ws, {'defect_column': name})
        self.ws.columns[1].name = 'Weight'
        with self.assertRaises(ValueError):
            normalize('rare_event_control_chart', self.ws, {'columns': ['Weight']})

    def test_changed_source_kind_rejected(self):
        settings = normalize('imr_chart', self.ws, {'variables': [0]})
        self.ws.columns[0].kind = 'text'
        with self.assertRaises(ValueError):
            resolve('imr_chart', self.ws, settings)

    def test_bad_metadata_rejected(self):
        for metadata in (None, [], {'variables': [True]}, {'variables': [-1]}, {'variables': [0, 0]}, {'unknown': [0]}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                binding_columns('imr_chart', {'variables': [0], KEY: metadata})

    def test_legacy_numeric_tolerance_remaps(self):
        recipe = {'action': 'tolerance_intervals', 'parameters': {'settings': {'variable_indices': [0]}}}
        self.assertEqual(columns(remap_recipe(recipe, {0: 2})), [2])

    def test_legacy_name_only_requires_verified_migration(self):
        recipe = {'action': 'pareto_chart', 'parameters': {'settings': {'defect_column': 'Defect'}}}
        with self.assertRaises(ValueError):
            columns(recipe)
        with self.assertRaises(ValueError):
            resolve('pareto_chart', self.ws, recipe['parameters']['settings'])

    def test_delete_invalidates_and_undo_restores(self):
        recipe = self.recipe('tolerance_intervals', {'variable_indices': [0]})
        entry = {'recipe': recipe, 'dependencies': [{'index': 0, 'fingerprint': 'example'}]}
        before = state(entry)
        remap_mapping([{'entry': entry, 'before': before}], {1: 0, 2: 1, 3: 2})
        self.assertIn('source_unavailable', entry)
        restore(entry, before)
        self.assertNotIn('source_unavailable', entry)
        self.assertEqual(columns(entry['recipe']), [0])

    def test_basic_inference_active_selectors_move(self):
        cases = [
            ('one_sample_t', {'sample_cols': [0], 'freq_cols': [2]}, [0, 2]),
            ('one_sample_z', {'sample_cols': [0]}, [0]),
            ('one_sample_poisson', {'sample_cols': [0], 'freq_cols': []}, [0]),
            ('one_sample_proportion', {'sample_cols': [0]}, [0]),
            ('paired_t', {'sample1_col': 0, 'sample2_col': 1}, [0, 1]),
            ('two_sample_t', {'data_format': 0, 'samples_col': 0, 'sample_ids_col': 3}, [0, 3]),
            ('two_sample_proportion', {'sample1_col': 0, 'sample2_col': 1}, [0, 1]),
            ('two_sample_poisson', {'sample1_col': 0, 'sample2_col': 1, 'length1_col': 2}, [0, 1, 2]),
            ('one_variance', {'mode': 0, 'columns': [0]}, [0]),
            ('two_variances', {'mode': 1, 's1_col': 0, 's2_col': 1}, [0, 1]),
        ]
        for action, settings, expected in cases:
            with self.subTest(action=action):
                recipe = {'action': action, 'parameters': {'settings': settings}}
                moved = remap_recipe(recipe, {0: 3, 1: 2, 2: 1, 3: 0})
                self.assertEqual(sorted(columns(moved)), sorted(3 - i for i in expected))

    def test_summarized_inference_keeps_numeric_summaries(self):
        for action, mode in [('one_sample_t', 'data_format'), ('two_sample_poisson', 'data_format'), ('two_variances', 'mode')]:
            with self.subTest(action=action):
                settings = {mode: 2, 'sample_cols': [0], 'sample1_col': 0, 'mean': 1, 'n': 2, 'std': 3}
                recipe = {'action': action, 'parameters': {'settings': settings}}
                self.assertEqual(remap_recipe(recipe, {})['parameters']['settings'], settings)

    def test_normalize_is_deep_copy(self):
        settings = {'variables': [0], 'options': {'tests': [1, 2]}}
        before = copy.deepcopy(settings)
        result = normalize('imr_chart', self.ws, settings)
        result['options']['tests'].append(3)
        self.assertEqual(settings, before)


if __name__ == '__main__':
    unittest.main()
