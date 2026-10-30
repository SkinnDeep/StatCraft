"""Presenter-level source binding, structure editing and MPX round trips."""
import copy
import math
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.analysis_bindings import KEY
from statcraft.recipes import columns


def presenter():
    p = Presenter()
    p.worksheet = Worksheet('Binding Data', [
        Column('Measure', values=[10 + math.sin(i) * .8 + i * .02 for i in range(24)]),
        Column('Second', values=[20 + math.cos(i * .6) + math.sin(i) * .3 for i in range(24)]),
        Column('Group', values=[i // 4 + 1 for i in range(24)]),
        Column('Defect', 'text', ['Chip', 'Burr', 'Crack', 'Chip'] * 6),
        Column('Counts', values=[1, 2, 3, 1, 4, 2] * 4),
        Column('Exposure', values=[20] * 24),
    ])
    return p


def cases():
    return [
        ('imr_chart', {'variables': [0]}),
        ('attribute_control_chart', {'chart_type': 'P', 'variables': [4], 'is_subgroup_col': True, 'subgroup_col_idx': 5}),
        ('time_weighted_control_chart', {'chart_type': 'EWMA', 'columns': ['Measure'], 'subgroup_text': 'Group', 'subgroup_spec': [i // 4 + 1 for i in range(24)]}),
        ('rare_event_control_chart', {'chart_type': 'G', 'columns': ['Counts']}),
        ('multivariate_control_chart', {'chart_type': 'TSQUARED', 'variables': ['Measure', 'Second'], 'subgroup_size': 1}),
        ('pareto_chart', {'defect_column': 'Defect', 'is_summarized': True, 'count_column': 'Counts', 'by_column': 'Group'}),
        ('normal_capability', {'column_name': 'Measure', 'subgroup_spec': 4, 'lsl': 8., 'usl': 14.}),
        ('normal_sixpack', {'column_name': 'Measure', 'subgroup_spec': 4, 'lsl': 8., 'usl': 14.}),
        ('tolerance_intervals', {'variable_indices': [0]}),
    ]


def numeric_tree(value, path=()):
    # Compare all calculation numbers while allowing source labels to follow renames.
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key in ('source_rows', 'row_indices', 'variable_indices'):
                continue
            result.update(numeric_tree(child, path + (str(key),)))
        return result
    if isinstance(value, (list, tuple)):
        result = {}
        for i, child in enumerate(value):
            result.update(numeric_tree(child, path + (i,)))
        return result
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {path: value}
    return {}


class AnalysisBindingWorkflowTests(unittest.TestCase):
    def assertSameNumbers(self, before, after):
        a, b = numeric_tree(before), numeric_tree(after)
        self.assertEqual(set(a), set(b))
        self.assertTrue(a, 'The comparison must exercise actual calculation results.')
        for path, value in a.items():
            with self.subTest(numeric_path=path):
                if math.isnan(value):
                    self.assertTrue(math.isnan(b[path]))
                elif value == b[path]:
                    continue
                else:
                    self.assertAlmostEqual(value, b[path], delta=max(1e-10, abs(value) * 1e-10))

    def test_move_rename_rerun_all_nine_families(self):
        for action, settings in cases():
            with self.subTest(action=action):
                p = presenter()
                entry = getattr(p, action)(settings=copy.deepcopy(settings))
                before = copy.deepcopy(entry['result'])
                p.insert_columns(0)
                p.move_columns([1], 'after_last')
                for i in range(len(p.worksheet.columns)):
                    p.rename_column(i, 'Renamed ' + str(i + 1))
                self.assertSameNumbers(before, p.rerun_result(entry)['result'])

    def test_source_delete_blocked_then_undo_restores_all_families(self):
        for action, settings in cases():
            with self.subTest(action=action):
                p = presenter()
                entry = getattr(p, action)(settings=copy.deepcopy(settings))
                before = copy.deepcopy(entry['result'])
                p.delete_columns([columns(entry['recipe'])[0]])
                with self.assertRaisesRegex(ValueError, 'deleted'):
                    p.rerun_result(entry)
                p.undo()
                self.assertSameNumbers(before, p.rerun_result(entry)['result'])

    def test_mpx_save_load_rerun_all_nine_families_after_move(self):
        with scratch() as folder:
            p = presenter()
            entries = [getattr(p, action)(settings=copy.deepcopy(settings)) for action, settings in cases()]
            before = [copy.deepcopy(entry['result']) for entry in entries]
            p.insert_columns(0)
            p.move_columns([1], 'after_last')
            path = Path(folder) / 'bindings.mpx'
            p.save(path)
            q = Presenter()
            q.load(path)
            saved = [entry for entry in q.history if entry.get('recipe', {}).get('action') in {action for action, _ in cases()}]
            self.assertEqual(len(saved), len(cases()))
            for old, entry in zip(before, saved):
                with self.subTest(action=entry['recipe']['action']):
                    self.assertSameNumbers(old, q.rerun_result(entry)['result'])

    def test_each_multi_variable_output_has_narrow_dependencies(self):
        for action, settings, expected in [
            ('imr_chart', {'variables': [0, 1]}, [[0], [1]]),
            ('rare_event_control_chart', {'chart_type': 'G', 'columns': ['Counts', 'Exposure']}, [[4], [5]]),
            ('time_weighted_control_chart', {'chart_type': 'EWMA', 'columns': ['Measure', 'Second'], 'subgroup_spec': 1}, [[0], [1]]),
        ]:
            with self.subTest(action=action):
                p = presenter()
                getattr(p, action)(settings=settings)
                self.assertEqual([columns(entry['recipe']) for entry in p.history], expected)
                for entry in list(p.history):
                    self.assertSameNumbers(entry['result'], p.rerun_result(entry)['result'])

    def test_across_column_capability_and_sixpack_survive_move_rename(self):
        for action in ('normal_capability', 'normal_sixpack'):
            with self.subTest(action=action):
                p = presenter()
                entry = getattr(p, action)(settings={'single_column': False, 'cols_across': ['Measure', 'Second'], 'lsl': 5., 'usl': 25.})
                before = copy.deepcopy(entry['result'])
                p.move_columns([0], 'after_last')
                p.rename_column(5, 'New Measure')
                p.rename_column(0, 'New Second')
                self.assertSameNumbers(before, p.rerun_result(entry)['result'])

    def test_subgroup_column_renames_survive_in_all_supported_families(self):
        for action, settings in [
            ('normal_capability', {'column_name': 'Measure', 'subgroup_spec': 'Group', 'lsl': 8., 'usl': 14.}),
            ('normal_sixpack', {'column_name': 'Measure', 'subgroup_spec': 'Group', 'lsl': 8., 'usl': 14.}),
            ('multivariate_control_chart', {'chart_type': 'TSQUARED', 'variables': ['Measure', 'Second'], 'subgroup_size': 'Group'}),
        ]:
            with self.subTest(action=action):
                p = presenter()
                entry = getattr(p, action)(settings=settings)
                before = copy.deepcopy(entry['result'])
                p.move_columns([2], 'before_c1')
                p.rename_column(0, 'New Batch')
                self.assertSameNumbers(before, p.rerun_result(entry)['result'])

    def test_legacy_names_without_trustworthy_dependencies_blocked(self):
        for action, settings in [('pareto_chart', {'defect_column': 'Defect'}), ('multivariate_control_chart', {'variables': ['Measure', 'Second']})]:
            with self.subTest(action=action):
                p = presenter()
                entry = getattr(p, action)(settings=settings)
                entry['recipe']['parameters']['settings'].pop(KEY)
                entry['dependencies'] = []
                with self.assertRaisesRegex(ValueError, 'no verified source bindings'):
                    p.rerun_result(entry)

    def test_legacy_index_recipe_migrates_only_matching_fingerprints(self):
        p = presenter()
        entry = p.tolerance_intervals(settings={'variable_indices': [0]})
        entry['recipe']['parameters']['settings'].pop(KEY)
        self.assertSameNumbers(entry['result'], p.rerun_result(entry)['result'])
        p.worksheet.columns[0].values[0] += 2
        with self.assertRaisesRegex(ValueError, 'no verified source bindings'):
            p.rerun_result(entry)

    def test_pareto_by_column_zero_is_passed_to_engine(self):
        from unittest.mock import patch
        from statcraft.pareto_engine import run_pareto_chart
        p = presenter()
        with patch('statcraft.pareto_engine.run_pareto_chart', wraps=run_pareto_chart) as run:
            entry = p.pareto_chart(settings={'defect_column': 'Defect', 'by_column': 0})
        self.assertEqual(run.call_args.kwargs['by_data'], p.worksheet.columns[0].values)
        self.assertEqual(columns(entry['recipe']), [0, 3])

    def test_rare_event_date_text_sources_stay_bound(self):
        for chart in ('G', 'T'):
            with self.subTest(chart=chart):
                p = presenter()
                p.worksheet.columns.append(Column('Dates', 'text', ['2026-01-01', '2026-01-03', '2026-01-07', '2026-01-08', '2026-01-13', '2026-01-16']))
                entry = p.rare_event_control_chart(settings={'chart_type': chart, 'columns': ['Dates'], 'form_of_data': 0})
                before = copy.deepcopy(entry['result'])
                p.insert_columns(0)
                p.rename_column(7, 'Event Times')
                self.assertSameNumbers(before, p.rerun_result(entry)['result'])


if __name__ == '__main__':
    unittest.main()
