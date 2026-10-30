"""Reliability row pairing and complete source identity coverage."""
import copy
import math
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.analysis_bindings import KEY, normalize, resolve, binding_columns
from statcraft.reliability_inputs import prepare_inputs
from statcraft.recipe_columns import remap_recipe
from statcraft.recipes import columns
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter


def sheet(times=None, censor=None, censor_kind='number'):
    return Worksheet('Life data', [
        Column('Life', values=[10, None, 30, 40, 50] if times is None else times),
        Column('Status', censor_kind, [1, 0, 0, 1, 1] if censor is None else censor),
        Column('Other', values=[99] * 5)])


def cfg(**updates):
    result = {'column_index': 0, 'censor_index': 1}
    result.update(updates)
    return result


class ReliabilityInputTests(unittest.TestCase):
    def test_missing_time_does_not_shift_censor_codes(self):
        result = prepare_inputs(sheet(), cfg())
        self.assertEqual(result['time_values'], [10, 30, 40, 50])
        self.assertEqual(result['censor_values'], [1, 0, 1, 1])
        self.assertEqual(result['row_indices'], [0, 2, 3, 4])
        self.assertEqual(result['omitted_rows'], [1])
        self.assertEqual(result['invalid_count'], 0)

    def test_missing_censor_omits_matching_time(self):
        result = prepare_inputs(sheet(censor=[1, 0, None, 1, 1]), cfg())
        self.assertEqual(result['time_values'], [10, 40, 50])
        self.assertEqual(result['censor_values'], [1, 1, 1])
        self.assertEqual(result['omitted_rows'], [1, 2])

    def test_shorter_censor_column_means_trailing_missing_pairs(self):
        result = prepare_inputs(sheet(censor=[1, 0, 0]), cfg())
        self.assertEqual(result['time_values'], [10, 30])
        self.assertEqual(result['censor_values'], [1, 0])
        self.assertEqual(result['omitted_rows'], [1, 3, 4])

    def test_shorter_time_column_does_not_create_false_failures(self):
        result = prepare_inputs(sheet(times=[10, 20], censor=[1, 0, 1, 1]), cfg())
        self.assertEqual(result['time_values'], [10, 20])
        self.assertEqual(result['omitted_rows'], [2, 3])

    def test_uncensored_ignores_censor_value_and_has_no_censor_source(self):
        result = prepare_inputs(sheet(), cfg(censor_index=None, censor_value=1))
        self.assertIsNone(result['censor_values'])
        self.assertIsNone(result['censor_value'])
        self.assertEqual(binding_columns('reliability_distribution', result['settings']), [0])

    def test_text_default_codes_are_validated_and_normalized(self):
        result = prepare_inputs(sheet(times=[10, 20, 30], censor=['1', '0', '1'], censor_kind='text'), cfg())
        self.assertEqual(result['censor_values'], [1, 0, 1])

    def test_custom_text_censor_code_stays_aligned(self):
        data = sheet(censor=['Failed', 'Right', 'Right', 'Failed', 'Failed'], censor_kind='text')
        result = prepare_inputs(data, cfg(censor_value='Right'))
        self.assertEqual(result['censor_values'], ['Failed', 'Right', 'Failed', 'Failed'])
        self.assertEqual(result['censor_value'], 'Right')

    def test_custom_numeric_censor_code_preserves_exact_values(self):
        result = prepare_inputs(sheet(censor=[7, 9, 9, 7, 7]), cfg(censor_value=9))
        self.assertEqual(result['censor_values'], [7, 9, 7, 7])

    def test_invalid_time_values_rejected_with_original_row(self):
        for value in (0, -2, float('nan'), float('inf'), True, '10'):
            with self.subTest(value=value):
                data = sheet()
                data.columns[0].values[2] = value
                with self.assertRaisesRegex(ValueError, 'row 3'):
                    prepare_inputs(data, cfg())

    def test_normal_family_positive_lifetime_boundary_is_explicit(self):
        data = sheet()
        data.columns[0].values[0] = -1
        with self.assertRaisesRegex(ValueError, 'positive'):
            prepare_inputs(data, cfg(dist_name='normal'))

    def test_invalid_censor_codes_not_silently_reclassified(self):
        for value in (2, -1, float('nan'), float('inf'), True, 'unknown'):
            with self.subTest(value=value):
                data = sheet()
                data.columns[1].values[2] = value
                with self.assertRaisesRegex(ValueError, 'row 3'):
                    prepare_inputs(data, cfg())

    def test_invalid_custom_censor_setting_rejected(self):
        for value in (float('nan'), float('inf'), True, '', [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_inputs(sheet(), cfg(censor_value=value))

    def test_same_time_and_censor_column_rejected(self):
        with self.assertRaisesRegex(ValueError, 'separate'):
            prepare_inputs(sheet(), cfg(censor_index=0))

    def test_wrong_time_or_censor_column_kind_rejected(self):
        data = sheet()
        data.columns[0].kind = 'text'
        with self.assertRaisesRegex(ValueError, 'data type'):
            prepare_inputs(data, cfg())
        data = sheet()
        data.columns[1].kind = 'date'
        with self.assertRaisesRegex(ValueError, 'data type'):
            prepare_inputs(data, cfg())

    def test_name_resolution_ambiguous_or_missing_rejected(self):
        data = sheet()
        data.columns[2].name = 'Life'
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            prepare_inputs(data, {'column_name': 'Life'})
        with self.assertRaisesRegex(ValueError, 'not found'):
            prepare_inputs(sheet(), {'column_name': 'Missing'})

    def test_prepare_is_deep_copy_and_preserves_source_rows(self):
        data = sheet()
        settings = cfg(options={'rows': [2]})
        old_data, old_settings = copy.deepcopy(data), copy.deepcopy(settings)
        result = prepare_inputs(data, settings)
        result['settings']['options']['rows'].append(3)
        result['time_values'][0] = 100
        self.assertEqual(data, old_data)
        self.assertEqual(settings, old_settings)

    def test_both_sources_tracked_without_capability_phantom_roles(self):
        settings = normalize('reliability_distribution', sheet(), cfg(subgroup_spec='Other', subgroup_col_index=2, single_column=False))
        self.assertEqual(settings[KEY], {'column_name': 0, 'censor_index': 1})
        self.assertEqual(binding_columns('reliability_distribution', settings), [0, 1])

    def test_move_rename_retains_time_and_censor_pair(self):
        data = sheet()
        recipe = {'action': 'reliability_distribution', 'parameters': {'settings': normalize('reliability_distribution', data, cfg())}}
        moved = remap_recipe(recipe, {0: 2, 1: 0, 2: 1})
        data.columns = [data.columns[1], data.columns[2], data.columns[0]]
        data.columns[0].name, data.columns[2].name = 'Outcome', 'Hours'
        result = prepare_inputs(data, moved['parameters']['settings'])
        self.assertEqual(result['time_values'], [10, 30, 40, 50])
        self.assertEqual(result['censor_values'], [1, 0, 1, 1])
        self.assertEqual(result['settings']['column_name'], 'Hours')
        self.assertEqual(result['settings']['censor_name'], 'Outcome')
        self.assertEqual(columns(moved), [0, 2])

    def test_delete_censor_blocks_recipe_and_undo_restores(self):
        p = Presenter()
        p.worksheet = sheet()
        recipe = {'action': 'reliability_distribution', 'parameters': {'settings': normalize('reliability_distribution', p.worksheet, cfg())}}
        entry = p._record('Reliability fixture', {'analysis': 'fixture'}, recipe=recipe)
        p.delete_columns([1])
        self.assertIn('source_unavailable', entry)
        with self.assertRaises(ValueError):
            p.rerun_result(entry)
        p.undo()
        self.assertNotIn('source_unavailable', entry)
        result = prepare_inputs(p.worksheet, entry['recipe']['parameters']['settings'])
        self.assertEqual(result['censor_values'], [1, 0, 1, 1])

    def test_mpx_roundtrip_after_moves_preserves_both_bindings(self):
        with scratch() as folder:
            p = Presenter()
            p.worksheet = sheet()
            recipe = {'action': 'reliability_distribution', 'parameters': {'settings': normalize('reliability_distribution', p.worksheet, cfg())}}
            p._record('Reliability fixture', {'analysis': 'fixture'}, recipe=recipe)
            p.move_columns([1], 'before_c1')
            path = Path(folder) / 'aligned.mpx'
            p.save(path)
            q = Presenter()
            q.load(path)
            entry = q.history[0]
            result = prepare_inputs(q.worksheet, entry['recipe']['parameters']['settings'])
            self.assertEqual(result['time_values'], [10, 30, 40, 50])
            self.assertEqual(result['censor_values'], [1, 0, 1, 1])
            self.assertEqual(columns(entry['recipe']), [0, 1])


if __name__ == '__main__':
    unittest.main()
