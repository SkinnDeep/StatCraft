import unittest
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.model_plots import (
    contour_plot_settings,
    discover_models,
    factorial_plots,
    factorial_plots_settings,
    model_contour_plot,
    model_surface_plot,
    resolve_hold_settings,
    surface_plot_settings,
)
from statcraft.model_plots_report import sections, text_report
from statcraft.optimizer import _fit_model_bundle
from statcraft.recipe_columns import remap_recipe
from statcraft.recipes import columns


class TestModelPlots(unittest.TestCase):
    def _build_presenter(self):
        p = Presenter()
        p.worksheet = Worksheet(
            'ProcessData',
            [
                Column('Temp', 'number', [150, 150, 150, 150, 200, 200, 200, 200, 175, 175, 160, 190]),
                Column('Pressure', 'number', [10, 10, 20, 20, 10, 10, 20, 20, 15, 15, 12, 18]),
                Column('Time', 'number', [30, 60, 30, 60, 30, 60, 30, 60, 45, 45, 40, 50]),
                Column('Catalyst', 'text', ['A', 'B', 'B', 'A', 'B', 'A', 'A', 'B', 'A', 'B', 'A', 'B']),
                Column('Yield', 'number', [62.0, 68.5, 71.0, 79.0, 74.5, 82.0, 86.0, 94.5, 78.0, 80.5, 70.0, 88.0]),
                Column('Pass', 'number', [0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1]),
            ],
        )
        return p

    def test_settings_validation(self):
        fp = factorial_plots_settings({'show_main_effects': True, 'show_interaction_plot': False})
        self.assertTrue(fp['show_main_effects'])
        self.assertFalse(fp['show_interaction_plot'])
        with self.assertRaises(ValueError):
            factorial_plots_settings({'show_main_effects': False, 'show_interaction_plot': False})

        cp = contour_plot_settings({'level_mode': 'values', 'custom_levels': [65, 75, 85]})
        self.assertEqual(cp['custom_levels'], [65.0, 75.0, 85.0])
        with self.assertRaises(ValueError):
            contour_plot_settings({'level_mode': 'values', 'custom_levels': [80, 70]})

        sp = surface_plot_settings({'surface_style': 'wireframe', 'pair_mode': 'all'})
        self.assertEqual(sp['surface_style'], 'wireframe')
        self.assertEqual(sp['pair_mode'], 'all')

    def test_factorial_prediction_values_and_columns(self):
        p = Presenter()
        p.create_factorial(
            [{'name': 'Temp', 'low': -1.0, 'high': 1.0}, {'name': 'Pressure', 'low': 10.0, 'high': 20.0}],
            replicates=2,
            randomize=False,
        )
        p.worksheet.columns.append(Column('Yield', 'number', [60.0, 70.0, 66.0, 80.0, 61.0, 69.0, 65.0, 81.0]))
        fit_entry = p.analyze_factorial(6, [4, 5], max_order=2)
        pred_entry = p.predict_model(
            fit_entry['recipe'],
            input_mode='values',
            values=[[-1.0, 10.0], [0.0, 15.0], [1.0, 20.0]],
        )
        rows = pred_entry['result']['rows']
        self.assertEqual(len(rows), 3)
        self.assertAlmostEqual(rows[0]['fit'], 60.5, places=5)
        self.assertAlmostEqual(rows[1]['fit'], 69.0, places=5)
        self.assertAlmostEqual(rows[2]['fit'], 80.5, places=5)

        # Column mode prediction
        p.worksheet.columns.append(Column('NewTemp', 'number', [-1.0, 1.0]))
        p.worksheet.columns.append(Column('NewPress', 'number', [10.0, 20.0]))
        col_pred = p.predict_model(
            fit_entry['recipe'],
            input_mode='columns',
            new_indices=[7, 8],
        )
        self.assertEqual(len(col_pred['result']['rows']), 2)
        self.assertAlmostEqual(col_pred['result']['rows'][1]['fit'], 80.5, places=5)

    def test_factorial_plots_across_all_five_families(self):
        p = self._build_presenter()
        reg = p.multiple_regression(4, [0, 1, 2])
        glm = p.general_linear_model(4, [3], [0, 1], terms=[[0], [1], [2], [0, 1]])
        rsm = p.analyze_response_surface(
            4,
            [0, 1],
            [{'low': 150.0, 'high': 200.0}, {'low': 10.0, 'high': 20.0}],
            terms=[[0], [1], [0, 1], [0, 0]],
        )
        log = p.fit_binary_logistic(5, [0, 1], [3])

        for entry in (reg, glm, rsm, log):
            fp_entry = p.factorial_plots(entry['recipe'], options={'terms_to_display': 'all'})
            res = fp_entry['result']
            self.assertEqual(res['analysis'], 'factorial_plots')
            self.assertTrue(len(res['main_effects']) >= 2)
            self.assertTrue(len(res['interactions']) >= 1)
            sec = sections(res)
            self.assertTrue(len(sec) >= 2)
            self.assertIn(res['response_name'], text_report(res))

        # Two-level factorial model
        p_doe = Presenter()
        p_doe.create_factorial(
            [{'name': 'Temp', 'low': 150.0, 'high': 200.0}, {'name': 'Pressure', 'low': 10.0, 'high': 20.0}],
            replicates=2,
            randomize=False,
        )
        p_doe.worksheet.columns.append(Column('Yield', 'number', [60.0, 72.0, 68.0, 84.0, 61.0, 71.0, 67.0, 85.0]))
        fac = p_doe.analyze_factorial(6, [4, 5], max_order=2)
        fp_fac = p_doe.factorial_plots(fac['recipe'])
        self.assertEqual(len(fp_fac['result']['main_effects']), 2)
        self.assertEqual(len(fp_fac['result']['interactions']), 1)

    def test_contour_and_surface_plots_and_hold_values(self):
        p = self._build_presenter()
        reg = p.multiple_regression(4, [0, 1, 2])

        bundle = _fit_model_bundle(p.worksheet, reg['recipe'])
        hold_row, hold_summary = resolve_hold_settings(
            p.worksheet,
            bundle,
            hold_continuous='min',
            hold_values=[{'index': 2, 'value': 50.0}],
        )
        self.assertEqual(hold_row[2], 50.0)
        self.assertEqual(hold_row[0], 150.0)
        self.assertEqual(hold_summary[2]['rule'], 'custom')

        cp_single = p.model_contour_plot(
            reg['recipe'],
            x_index=0,
            y_index=1,
            options={'hold_values': [{'index': 2, 'value': 45.0}], 'show_design_points': True},
        )
        c_res = cp_single['result']
        self.assertEqual(c_res['analysis'], 'model_contour_plot')
        self.assertEqual(len(c_res['panels']), 1)
        self.assertEqual(c_res['panels'][0]['held_predictors'][0]['value'], 45.0)
        self.assertTrue(len(c_res['panels'][0]['design_points']) >= 4)

        cp_all = p.model_contour_plot(
            reg['recipe'],
            options={'pair_mode': 'all'},
        )
        self.assertEqual(len(cp_all['result']['panels']), 3)

        sp = p.model_surface_plot(
            reg['recipe'],
            x_index=0,
            y_index=1,
            options={'surface_style': 'wireframe'},
        )
        s_res = sp['result']
        self.assertEqual(s_res['analysis'], 'model_surface_plot')
        self.assertEqual(len(s_res['panels'][0]['x_grid']), 25)
        self.assertEqual(s_res['options']['surface_style'], 'wireframe')

    def test_recipe_columns_and_remapping(self):
        p = self._build_presenter()
        reg = p.multiple_regression(4, [0, 1, 2])
        cp = p.model_contour_plot(
            reg['recipe'],
            x_index=0,
            y_index=1,
            options={'hold_values': [{'index': 2, 'value': 45.0}]},
        )
        fp = p.factorial_plots(
            reg['recipe'],
            selected_indices=[0, 1],
            options={'hold_values': [{'index': 2, 'value': 45.0}]},
        )

        self.assertEqual(columns(cp['recipe']), [0, 1, 2, 4])
        self.assertEqual(columns(fp['recipe']), [0, 1, 2, 4])

        mapping = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
        remapped_cp = remap_recipe(cp['recipe'], mapping)
        self.assertEqual(remapped_cp['parameters']['x_index'], 1)
        self.assertEqual(remapped_cp['parameters']['y_index'], 2)
        self.assertEqual(remapped_cp['parameters']['options']['hold_values'], [{'index': 3, 'value': 45.0}])

        remapped_fp = remap_recipe(fp['recipe'], mapping)
        self.assertEqual(remapped_fp['parameters']['selected_indices'], [1, 2])
        self.assertEqual(remapped_fp['parameters']['options']['hold_values'], [{'index': 3, 'value': 45.0}])


if __name__ == '__main__':
    unittest.main()
