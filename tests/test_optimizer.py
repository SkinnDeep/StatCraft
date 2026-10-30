"""Mathematical and contract tests for Derringer-Suich Response Optimizer."""
import copy
import itertools
import json
import math
import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.optimizer import (
    settings, individual_desirability, composite_desirability,
    default_desirability, normalize_model_recipe, normalize_response_spec,
    discover_models, optimize,
)
from statcraft.glm import settings as glm_settings
from statcraft.response_surface import full_terms
from statcraft.logistic import settings as logistic_settings


class OptimizerMathTests(unittest.TestCase):
    def test_individual_desirability_formulas_all_goals_and_weights(self):
        # Minimize: Target=10, Upper=30
        self.assertEqual(individual_desirability(5.0, 'minimize', None, 10.0, 30.0, 1.0), 1.0)
        self.assertEqual(individual_desirability(10.0, 'minimize', None, 10.0, 30.0, 1.0), 1.0)
        self.assertAlmostEqual(individual_desirability(15.0, 'minimize', None, 10.0, 30.0, 1.0), 0.75)
        self.assertAlmostEqual(individual_desirability(15.0, 'minimize', None, 10.0, 30.0, 2.0), 0.75 ** 2)
        self.assertAlmostEqual(individual_desirability(15.0, 'minimize', None, 10.0, 30.0, 0.5), 0.75 ** 0.5)
        self.assertEqual(individual_desirability(30.0, 'minimize', None, 10.0, 30.0, 1.0), 0.0)
        self.assertEqual(individual_desirability(35.0, 'minimize', None, 10.0, 30.0, 1.0), 0.0)

        # Maximize: Lower=20, Target=60
        self.assertEqual(individual_desirability(15.0, 'maximize', 20.0, 60.0, None, 1.0), 0.0)
        self.assertEqual(individual_desirability(20.0, 'maximize', 20.0, 60.0, None, 1.0), 0.0)
        self.assertAlmostEqual(individual_desirability(30.0, 'maximize', 20.0, 60.0, None, 1.0), 0.25)
        self.assertAlmostEqual(individual_desirability(30.0, 'maximize', 20.0, 60.0, None, 3.0), 0.25 ** 3)
        self.assertEqual(individual_desirability(60.0, 'maximize', 20.0, 60.0, None, 1.0), 1.0)
        self.assertEqual(individual_desirability(80.0, 'maximize', 20.0, 60.0, None, 1.0), 1.0)

        # Target: Lower=10, Target=20, Upper=40
        self.assertEqual(individual_desirability(10.0, 'target', 10.0, 20.0, 40.0, 1.0), 0.0)
        self.assertAlmostEqual(individual_desirability(15.0, 'target', 10.0, 20.0, 40.0, 2.0), 0.25)
        self.assertEqual(individual_desirability(20.0, 'target', 10.0, 20.0, 40.0, 2.0), 1.0)
        self.assertAlmostEqual(individual_desirability(30.0, 'target', 10.0, 20.0, 40.0, 2.0), 0.25)
        self.assertEqual(individual_desirability(40.0, 'target', 10.0, 20.0, 40.0, 2.0), 0.0)

    def test_composite_desirability_weighted_geometric_mean(self):
        d = [0.81, 0.64, 0.49]
        w = [1.0, 2.0, 1.0]
        expected = (0.81 ** 0.25) * (0.64 ** 0.5) * (0.49 ** 0.25)
        self.assertAlmostEqual(composite_desirability(d, w), expected, places=12)
        self.assertEqual(composite_desirability([0.9, 0.0, 0.8], [1.0, 0.5, 2.0]), 0.0)

    def rsm_sheet_and_recipes(self):
        # 2-factor central-composite-like grid on Temp in [100, 200], Time in [20, 60]
        # Coded a = (Temp - 150)/50 in [-1, 1], b = (Time - 40)/20 in [-1, 1]
        # Yield peaks at a = 0.2 (Temp = 160), b = -0.25 (Time = 35):
        # Yield = 90 - 8*(a - 0.2)^2 - 6*(b + 0.25)^2
        # Cost increases with Temp and Time:
        # Cost = 50 + 6*a + 4*b + (a - b)^2
        coords = list(itertools.product([-1.0, -0.5, 0.0, 0.5, 1.0], repeat=2))
        temps = [150.0 + 50.0 * a for a, _ in coords]
        times = [40.0 + 20.0 * b for _, b in coords]
        yields = [90.0 - 8.0 * (a - 0.2) ** 2 - 6.0 * (b + 0.25) ** 2 + (0.05 if i % 2 == 0 else -0.05) for i, (a, b) in enumerate(coords)]
        costs = [50.0 + 6.0 * a + 4.0 * b + (a - b) ** 2 + (0.04 if i % 3 == 0 else -0.02) for i, (a, b) in enumerate(coords)]
        sheet = Worksheet('rsm_opt', [
            Column('Temp', values=temps),
            Column('Time', values=times),
            Column('Yield', values=yields),
            Column('Cost', values=costs),
        ])
        coding = [dict(low=100.0, high=200.0), dict(low=20.0, high=60.0)]
        yield_recipe = dict(
            action='analyze_response_surface',
            parameters=dict(response_index=2, factor_indices=[0, 1], coding=coding, terms=full_terms(2), options=glm_settings()),
        )
        cost_recipe = dict(
            action='analyze_response_surface',
            parameters=dict(response_index=3, factor_indices=[0, 1], coding=coding, terms=full_terms(2), options=glm_settings()),
        )
        return sheet, yield_recipe, cost_recipe

    def test_single_response_rsm_peak_recovery(self):
        sheet, yield_recipe, _ = self.rsm_sheet_and_recipes()
        res = optimize(sheet, [dict(
            model_recipe=yield_recipe,
            goal='maximize',
            lower=70.0,
            target=90.0,
            upper=None,
            weight=1.0,
            importance=1.0,
        )])
        opt_temp, opt_time = res['optimal_settings']
        self.assertAlmostEqual(opt_temp, 160.0, delta=0.6)
        self.assertAlmostEqual(opt_time, 35.0, delta=0.4)
        self.assertGreater(res['optimal_composite_desirability'], 0.995)
        pred = res['predictions'][0]
        self.assertAlmostEqual(pred['fit'], 90.0, delta=0.05)
        self.assertIsNotNone(pred['se_fit'])
        self.assertLess(pred['ci_low'], pred['fit'])
        self.assertGreater(pred['ci_high'], pred['fit'])
        self.assertLess(pred['pi_low'], pred['ci_low'])
        self.assertGreater(pred['pi_high'], pred['ci_high'])

    def test_multi_response_rsm_tradeoff_and_importance(self):
        sheet, yield_recipe, cost_recipe = self.rsm_sheet_and_recipes()
        equal_res = optimize(sheet, [
            dict(model_recipe=yield_recipe, goal='maximize', lower=75.0, target=90.0, upper=None, weight=1.0, importance=1.0),
            dict(model_recipe=cost_recipe, goal='minimize', lower=None, target=40.0, upper=60.0, weight=1.0, importance=1.0),
        ])
        cost_heavy_res = optimize(sheet, [
            dict(model_recipe=yield_recipe, goal='maximize', lower=75.0, target=90.0, upper=None, weight=1.0, importance=0.2),
            dict(model_recipe=cost_recipe, goal='minimize', lower=None, target=40.0, upper=60.0, weight=1.0, importance=5.0),
        ])
        # Higher importance on minimizing Cost must pull optimal Cost fit lower
        self.assertLess(cost_heavy_res['predictions'][1]['fit'], equal_res['predictions'][1]['fit'])
        self.assertGreater(equal_res['predictions'][0]['fit'], cost_heavy_res['predictions'][0]['fit'])

    def test_constraints_hold_and_region_and_starting_values(self):
        sheet, yield_recipe, _ = self.rsm_sheet_and_recipes()
        opts = settings(dict(
            settings(),
            constraints=[
                dict(index=0, mode='hold', value=140.0, lower=None, upper=None),
                dict(index=1, mode='region', value=None, lower=42.0, upper=55.0),
            ],
            starting_values=[
                dict(index=0, value=140.0),
                dict(index=1, value=50.0),
            ],
            max_solutions=3,
        ))
        res = optimize(sheet, [
            dict(model_recipe=yield_recipe, goal='maximize', lower=70.0, target=90.0, upper=None, weight=1.0, importance=1.0),
        ], options=opts)
        self.assertAlmostEqual(res['optimal_settings'][0], 140.0, places=9)
        # Since unconstrained optimum for Time is 35.0 and region is [42, 55], optimal Time must hit boundary 42.0
        self.assertAlmostEqual(res['optimal_settings'][1], 42.0, delta=1e-3)
        self.assertEqual(res['starting_point']['settings'], [140.0, 50.0])

    def test_glm_mixed_categorical_and_continuous_optimization(self):
        rows = list(itertools.product(['CatalystA', 'CatalystB', 'CatalystC'], [10.0, 20.0, 30.0, 40.0], [0, 1]))
        # CatalystB has highest intercept (+8), slope -0.3*(x - 25)^2 simulated via linear terms or GLM main+interaction
        y = [
            50.0 + {'CatalystA': 0.0, 'CatalystB': 12.0, 'CatalystC': 5.0}[cat]
            + ({'CatalystA': 0.4, 'CatalystB': 0.8, 'CatalystC': -0.5}[cat]) * x
            + (0.2 if rep else -0.2)
            for cat, x, rep in rows
        ]
        sheet = Worksheet('glm_opt', [
            Column('Conversion', values=y),
            Column('Catalyst', kind='text', values=[r[0] for r in rows]),
            Column('Dose', values=[r[1] for r in rows]),
        ])
        recipe = dict(
            action='general_linear_model',
            parameters=dict(response_index=0, factor_indices=[1], covariate_indices=[2], terms=[[0], [1], [0, 1]], options=glm_settings()),
        )
        opts = settings(dict(settings(), max_solutions=3))
        res = optimize(sheet, [
            dict(model_recipe=recipe, goal='maximize', lower=55.0, target=95.0, upper=None, weight=1.0, importance=1.0),
        ], options=opts)
        self.assertEqual(res['optimal_settings'][0], 'CatalystB')
        self.assertAlmostEqual(res['optimal_settings'][1], 40.0, delta=1e-4)
        self.assertGreaterEqual(len(res['solutions']), 2)

        # Now hold Catalyst at CatalystC (where slope is negative, so Dose=10 maximizes Conversion)
        hold_opts = settings(dict(
            settings(),
            constraints=[dict(index=1, mode='hold', value='CatalystC', lower=None, upper=None)],
        ))
        res_held = optimize(sheet, [
            dict(model_recipe=recipe, goal='maximize', lower=40.0, target=60.0, upper=None, weight=1.0, importance=1.0),
        ], options=hold_opts)
        self.assertEqual(res_held['optimal_settings'][0], 'CatalystC')
        self.assertAlmostEqual(res_held['optimal_settings'][1], 10.0, delta=1e-4)

    def test_factorial_and_binary_logistic_models_supported(self):
        # Two-level factorial with 2 replicates
        corners = list(itertools.product([-1.0, 1.0], repeat=2)) * 2
        f1 = [20.0 + 10.0 * a for a, _ in corners]
        f2 = [50.0 + 25.0 * b for _, b in corners]
        strength = [100.0 + 8.0 * a - 5.0 * b + 6.0 * a * b + (0.5 if i < 4 else -0.5) for i, (a, b) in enumerate(corners)]
        # Also grouped binary logistic DefectEvents / Trials on the same factors
        events = [2 if (a > 0 and b < 0) else 8 if (a < 0 and b > 0) else 4 for a, b in corners]
        trials = [20] * len(corners)
        sheet = Worksheet('doe_log', [
            Column('Press', values=f1),
            Column('Cure', values=f2),
            Column('Strength', values=strength),
            Column('Defects', values=events),
            Column('Trials', values=trials),
        ])
        fact_recipe = dict(
            action='analyze_factorial',
            parameters=dict(response_index=2, factor_indices=[0, 1], max_order=2, confidence=0.95, plot_residuals=False, show_factor_coding=True),
        )
        log_recipe = dict(
            action='fit_binary_logistic',
            parameters=dict(response_index=3, continuous_indices=[0, 1], categorical_indices=[], event=None, trials_index=4, terms=[[0], [1]], options=logistic_settings()),
        )
        res = optimize(sheet, [
            dict(model_recipe=fact_recipe, goal='maximize', lower=85.0, target=115.0, upper=None, weight=1.0, importance=1.0),
            dict(model_recipe=log_recipe, goal='minimize', lower=None, target=0.08, upper=0.45, weight=1.0, importance=1.0),
        ])
        self.assertEqual(len(res['predictions']), 2)
        self.assertFalse(res['predictions'][0]['is_probability'])
        self.assertIsNotNone(res['predictions'][0]['pi_low'])
        self.assertTrue(res['predictions'][1]['is_probability'])
        self.assertIsNone(res['predictions'][1]['pi_low'])
        self.assertTrue(0.0 < res['predictions'][1]['fit'] < 1.0)
        json.dumps(res, allow_nan=False)

    def test_validation_and_immutability_guards(self):
        sheet, yield_recipe, _ = self.rsm_sheet_and_recipes()
        snap = copy.deepcopy(sheet)
        rcopy = copy.deepcopy(yield_recipe)
        res = optimize(sheet, [dict(model_recipe=yield_recipe, goal='target', lower=75.0, target=85.0, upper=92.0, weight=1.5, importance=2.0)])
        self.assertEqual(sheet, snap)
        self.assertEqual(yield_recipe, rcopy)
        json.dumps(res, allow_nan=False)

        # Overlapping response and predictor across models must fail (DoResponsesAndPredictorsOverlap)
        bad_recipe = dict(action='multiple_regression', parameters=dict(response_index=0, predictor_indices=[1], confidence=0.95))
        with self.assertRaisesRegex(ValueError, 'cannot also be a predictor'):
            optimize(sheet, [
                dict(model_recipe=yield_recipe, goal='maximize', lower=75.0, target=90.0, upper=None, weight=1.0, importance=1.0),
                dict(model_recipe=bad_recipe, goal='minimize', lower=None, target=100.0, upper=200.0, weight=1.0, importance=1.0),
            ])

        # Invalid desirability bounds
        with self.assertRaisesRegex(ValueError, 'Lower < Target < Upper|strictly between'):
            optimize(sheet, [dict(model_recipe=yield_recipe, goal='target', lower=88.0, target=85.0, upper=92.0, weight=1.0, importance=1.0)])
        with self.assertRaisesRegex(ValueError, '0.1 and 10'):
            optimize(sheet, [dict(model_recipe=yield_recipe, goal='maximize', lower=75.0, target=90.0, upper=None, weight=15.0, importance=1.0)])


if __name__ == '__main__':
    unittest.main()
