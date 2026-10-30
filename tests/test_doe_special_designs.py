"""Known mixture coordinates and independent finite-candidate optimality checks."""
import copy
import itertools
import math
import unittest
import numpy as np
from statcraft.doe_special_designs import create_design, model_matrix


def mixture(q=3, **bounds):
    return [dict(name=chr(65 + i), **bounds) for i in range(q)]


def points(sheet):
    return list(zip(*(column.values for column in sheet.columns[4:])))


def optimal_factors():
    return [{'name': 'A', 'kind': 'number', 'levels': [-1, 0, 1]},
            {'name': 'B', 'kind': 'number', 'levels': [-1, 0, 1]}]


class MixtureDesignTests(unittest.TestCase):
    def test_three_component_centroid_known_seven_points(self):
        sheet = create_design('simplex_centroid', mixture(), randomize=False)
        self.assertEqual(sheet.row_count, 7)
        expected = [(1,0,0),(0,1,0),(0,0,1),(.5,.5,0),(.5,0,.5),(0,.5,.5),(1/3,1/3,1/3)]
        np.testing.assert_allclose(points(sheet), expected)
        self.assertEqual(sheet.columns[0].values, list(range(1,8)))

    def test_four_component_centroid_count(self):
        sheet = create_design('simplex_centroid', mixture(4))
        self.assertEqual(sheet.row_count, 15)
        self.assertTrue(all(abs(sum(point)-1) < 1e-12 for point in points(sheet)))

    def test_lattice_known_six_points(self):
        sheet = create_design('simplex_lattice', mixture(), randomize=False, options={'degree':2})
        self.assertEqual(set(points(sheet)), {(1.,0.,0.),(.5,.5,0.),(.5,0.,.5),(0.,1.,0.),(0.,.5,.5),(0.,0.,1.)})

    def test_lattice_count_formula(self):
        for q, degree in [(2,4),(3,3),(4,2),(5,2)]:
            with self.subTest(q=q,degree=degree):
                sheet = create_design('simplex_lattice', mixture(q), options={'degree':degree})
                self.assertEqual(sheet.row_count, math.comb(q+degree-1,degree))

    def test_lower_bound_pseudocomponents_preserve_sum(self):
        sheet = create_design('simplex_centroid', mixture(low=.1, high=1.), randomize=False)
        np.testing.assert_allclose(points(sheet)[0], [.8,.1,.1])
        self.assertTrue(all(abs(sum(point)-1)<1e-12 and min(point)>=.1 for point in points(sheet)))

    def test_nonunit_mixture_total(self):
        sheet = create_design('simplex_lattice', mixture(high=100.), options={'total':100.,'degree':2})
        self.assertTrue(all(abs(sum(point)-100.)<1e-12 for point in points(sheet)))

    def test_constrained_hexagon_exact_vertices(self):
        factors = [{'name':'A','low':.1,'high':.6},{'name':'B','low':.2,'high':.7},{'name':'C','low':0.,'high':.5}]
        sheet = create_design('extreme_vertices', factors, randomize=False)
        actual = {tuple(round(value,10) for value in point) for point in points(sheet)}
        self.assertEqual(actual, {(.3,.2,.5),(.3,.7,0.),(.1,.4,.5),(.6,.4,0.),(.1,.7,.2),(.6,.2,.2)})
        self.assertEqual(sheet.metadata['doe']['diagnostics']['vertex_count'], 6)
        for point in points(sheet):
            self.assertAlmostEqual(sum(point),1)
            self.assertGreaterEqual(sum(abs(value-factor['low'])<1e-12 or abs(value-factor['high'])<1e-12 for value,factor in zip(point,factors)),2)

    def test_fixed_component_extreme_vertices(self):
        factors = [{'name':'A','low':.2,'high':.2},{'name':'B','low':0.,'high':.8},{'name':'C','low':0.,'high':.8}]
        sheet = create_design('extreme_vertices',factors)
        self.assertEqual({tuple(round(v,10) for v in point) for point in points(sheet)}, {(.2,0.,.8),(.2,.8,0.)})

    def test_upper_constraints_do_not_silently_filter_standard_points(self):
        for kind in ('simplex_centroid','simplex_lattice'):
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'extreme-vertices'):
                create_design(kind,mixture(high=.7))

    def test_empty_region_and_invalid_bounds_rejected(self):
        for factors in [mixture(low=.4,high=1.),mixture(high=.2),mixture(low=-.1,high=1.),mixture(low=.6,high=.5)]:
            with self.subTest(factors=factors),self.assertRaises(ValueError):
                create_design('extreme_vertices',factors)

    def test_centers_replicates_and_whole_replication_blocks(self):
        sheet = create_design('simplex_centroid',mixture(),replicates=6,blocks=3,centers=1,seed=71)
        self.assertEqual(sheet.row_count,45)
        self.assertEqual([sheet.columns[3].values.count(block) for block in (1,2,3)],[15,15,15])
        self.assertEqual(sheet.columns[2].values.count(0),3)
        self.assertEqual(sorted(sheet.columns[0].values),list(range(1,46)))
        self.assertTrue(all(abs(sum(point)-1)<1e-12 for point in points(sheet)))

    def test_invalid_blocking_and_extreme_augmentation_rejected(self):
        with self.assertRaisesRegex(ValueError,'divide'):
            create_design('simplex_lattice',mixture(),replicates=3,blocks=2)
        with self.assertRaisesRegex(ValueError,'vertices only'):
            create_design('extreme_vertices',mixture(),options={'degree':2})

    def test_randomization_is_reproducible_without_mutating_inputs(self):
        factors,options = mixture(),{'degree':3}
        before=copy.deepcopy((factors,options))
        a=create_design('simplex_lattice',factors,options=options,seed=99)
        b=create_design('simplex_lattice',factors,options=options,seed=99)
        self.assertEqual(a,b)
        self.assertEqual((factors,options),before)


class OptimalDesignTests(unittest.TestCase):
    def matrix(self,sheet):
        info=sheet.metadata['doe']
        return model_matrix(points(sheet),info['factors'],info['diagnostics']['model'])[0]

    def test_custom_run_budgets_above_sixteen_need_not_be_powers_of_two(self):
        factors=[{'name':name,'levels':[-1,0,1]} for name in 'ABC']
        for criterion in ('D','I'):
            for runs in (17,19,24,27):
                with self.subTest(criterion=criterion,runs=runs):
                    sheet=create_design('custom_optimal',factors,randomize=False,
                        options={'runs':runs,'criterion':criterion,'model':'full_quadratic'})
                    matrix=self.matrix(sheet)
                    diagnostics=sheet.metadata['doe']['diagnostics']
                    self.assertEqual(sheet.row_count,runs)
                    self.assertEqual(len(set(points(sheet))),runs)
                    self.assertEqual(matrix.shape,(runs,10))
                    self.assertEqual(np.linalg.matrix_rank(matrix),10)
                    self.assertEqual(len(diagnostics['selected_candidate_indices']),runs)
                    self.assertEqual(sheet.columns[1].values,list(range(1,runs+1)))
                    self.assertTrue(math.isfinite(diagnostics['objective']))

    def test_custom_thirty_two_runs_and_replicated_nonstandard_budget(self):
        factors=[{'name':name,'levels':[-1,0,1]} for name in 'ABCD']
        sheet=create_design('custom_optimal',factors,options={'runs':32,'model':'interactions'})
        self.assertEqual(sheet.row_count,32)
        self.assertEqual(np.linalg.matrix_rank(self.matrix(sheet)),11)
        repeated=create_design('custom_optimal',factors,replicates=2,blocks=2,
            options={'runs':19,'model':'interactions'})
        self.assertEqual(repeated.row_count,38)
        self.assertEqual(len(set(points(repeated))),19)
        self.assertEqual([repeated.columns[3].values.count(b) for b in (1,2)],[19,19])

    def test_d_objective_improves_over_poor_full_rank_design(self):
        sheet=create_design('custom_optimal',optimal_factors(),randomize=False,options={'runs':5,'criterion':'D'})
        matrix=self.matrix(sheet)
        baseline=np.array([[1,-1,-1],[1,-1,0],[1,0,-1],[1,0,0],[1,1,1]],dtype=float)
        objective=float(np.linalg.slogdet(matrix.T@matrix)[1])
        self.assertGreater(objective,float(np.linalg.slogdet(baseline.T@baseline)[1]))
        diagnostics=sheet.metadata['doe']['diagnostics']
        self.assertAlmostEqual(objective,diagnostics['objective'])
        self.assertGreaterEqual(diagnostics['log_determinant']+1e-10,diagnostics['initial_log_determinant'])
        self.assertFalse(diagnostics['global_optimum_verified'])

    def test_i_objective_against_independent_candidate_average(self):
        sheet=create_design('custom_optimal',optimal_factors(),randomize=False,options={'runs':5,'criterion':'I'})
        matrix=self.matrix(sheet)
        candidates=np.array([[1,a,b] for a,b in itertools.product((-1,0,1),repeat=2)],dtype=float)
        predictions=np.einsum('ij,ij->i',candidates@np.linalg.inv(matrix.T@matrix),candidates)
        objective=float(np.mean(predictions))
        self.assertAlmostEqual(objective,sheet.metadata['doe']['diagnostics']['objective'])
        baseline=np.array([[1,-1,-1],[1,-1,0],[1,0,-1],[1,0,0],[1,1,1]],dtype=float)
        poor=float(np.mean(np.einsum('ij,ij->i',candidates@np.linalg.inv(baseline.T@baseline),candidates)))
        self.assertLess(objective,poor)
        self.assertLessEqual(objective,sheet.metadata['doe']['diagnostics']['initial_average_prediction_variance']+1e-10)

    def test_converged_exchange_has_no_improving_single_swap(self):
        factors=[{'name':'A','levels':[-1,-.5,0,.5,1]},{'name':'B','levels':[-1,-.5,0,.5,1]}]
        candidates=np.array([[1,a,b,a*b,a*a,b*b] for a,b in itertools.product((-1,-.5,0,.5,1),repeat=2)])
        moment=candidates.T@candidates/len(candidates)
        for criterion,runs in [('D',10),('I',8)]:
            with self.subTest(criterion=criterion):
                sheet=create_design('custom_optimal',factors,options={'runs':runs,'criterion':criterion,'model':'full_quadratic'})
                diagnostics=sheet.metadata['doe']['diagnostics']
                self.assertTrue(diagnostics['converged'])
                self.assertGreater(diagnostics['exchanges'],0)
                selected=diagnostics['selected_candidate_indices']
                for position in range(runs):
                    for replacement in set(range(len(candidates)))-set(selected):
                        trial=list(selected);trial[position]=replacement
                        information=candidates[trial].T@candidates[trial]
                        sign,logdet=np.linalg.slogdet(information)
                        if sign<=0 or np.linalg.matrix_rank(information)<6:
                            continue
                        if criterion=='D':
                            self.assertLessEqual(logdet,diagnostics['objective']+1e-8)
                        else:
                            objective=float(np.trace(np.linalg.inv(information)@moment))
                            self.assertGreaterEqual(objective,diagnostics['objective']-1e-8)

    def test_one_factor_candidate_design_is_supported(self):
        sheet=create_design('custom_optimal',[{'name':'Dose','levels':[0,5,10]}],options={'runs':3,'model':'quadratic'})
        self.assertEqual(self.matrix(sheet).shape,(3,3))
        self.assertEqual(set(sheet.columns[4].values),{0,5,10})

    def test_forbidden_partial_and_complete_combinations_excluded(self):
        options={'runs':4,'forbidden':[{'A':-1,'B':-1},{'B':1}]}
        sheet=create_design('custom_optimal',optimal_factors(),options=options)
        self.assertTrue(all(not(a==-1 and b==-1) and b!=1 for a,b in points(sheet)))
        self.assertEqual(sheet.metadata['doe']['diagnostics']['candidate_count'],5)

    def test_forbidden_region_rank_deficiency_rejected(self):
        with self.assertRaisesRegex(ValueError,'full rank'):
            create_design('custom_optimal',optimal_factors(),options={'forbidden':[{'A':-1},{'A':1}]})

    def test_categorical_levels_dummy_coding_interactions(self):
        factors=[{'name':'Temperature','kind':'number','levels':[10,20,30]},
                 {'name':'Catalyst','kind':'text','levels':['red','green','blue']}]
        sheet=create_design('custom_optimal',factors,options={'runs':8,'model':'full_quadratic'})
        matrix=self.matrix(sheet)
        self.assertEqual(matrix.shape,(8,7))
        self.assertEqual(np.linalg.matrix_rank(matrix),7)
        self.assertEqual(sheet.columns[5].kind,'text')
        self.assertTrue(set(sheet.columns[5].values)<= {'red','green','blue'})

    def test_model_term_counts(self):
        for model,count in [('main_effects',3),('interactions',4),('quadratic',5),('full_quadratic',6)]:
            with self.subTest(model=model):
                sheet=create_design('custom_optimal',optimal_factors(),options={'model':model,'runs':8})
                self.assertEqual(self.matrix(sheet).shape[1],count)

    def test_quadratic_with_two_numeric_levels_rejected_as_aliased(self):
        factors=[{'name':'A','levels':[-1,1]},{'name':'B','levels':[-1,1]}]
        with self.assertRaisesRegex(ValueError,'full rank'):
            create_design('custom_optimal',factors,options={'model':'quadratic'})

    def test_saturated_full_rank_and_no_repeated_support(self):
        sheet=create_design('custom_optimal',optimal_factors(),options={'runs':3})
        self.assertEqual(np.linalg.matrix_rank(self.matrix(sheet)),3)
        self.assertEqual(len(set(points(sheet))),3)

    def test_whole_design_replication_blocks(self):
        sheet=create_design('custom_optimal',optimal_factors(),replicates=4,blocks=2,options={'runs':5})
        self.assertEqual(sheet.row_count,20)
        self.assertEqual(sheet.columns[3].values.count(1),10)
        self.assertEqual(sheet.columns[3].values.count(2),10)
        self.assertEqual(len(set(points(sheet))),5)

    def test_invalid_options_and_levels_rejected(self):
        badoptions=[{'criterion':'G'},{'runs':2},{'runs':10},{'max_iterations':0},{'forbidden':[{}]},
                    {'forbidden':[{'Unknown':1}]},{'forbidden':[{'A':99}]},{'model':'mystery'}]
        for options in badoptions:
            with self.subTest(options=options),self.assertRaises(ValueError):
                create_design('custom_optimal',optimal_factors(),options=options)
        for levels in ([1,'2'],[1,True],[1,float('nan')],[1,1]):
            with self.subTest(levels=levels),self.assertRaises(ValueError):
                create_design('custom_optimal',[{'name':'A','levels':levels},{'name':'B','levels':[0,1]}])
        with self.assertRaisesRegex(ValueError,'center'):
            create_design('custom_optimal',optimal_factors(),centers=1)

    def test_candidate_and_run_cost_limits(self):
        with self.assertRaisesRegex(ValueError,'4096'):
            create_design('custom_optimal',[{'name':f'F{i}','levels':list(range(10))} for i in range(4)])
        with self.assertRaisesRegex(ValueError,'4096'):
            create_design('simplex_lattice',mixture(8),options={'degree':8})

    def test_deterministic_search_and_randomized_run_order(self):
        factors=optimal_factors()
        a=create_design('custom_optimal',factors,options={'runs':5},seed=123)
        b=create_design('custom_optimal',factors,options={'runs':5},seed=123)
        self.assertEqual(a,b)
        self.assertEqual(a.metadata['doe']['diagnostics']['rank'],3)


if __name__=='__main__':
    unittest.main()
