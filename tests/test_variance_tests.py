import math
import unittest
from scipy import stats
from statcraft.engine import MISSING_SENTINEL
from statcraft.variance_tests import equal_variances


class VarianceTests(unittest.TestCase):
    def test_hand_derived_median_deviation_anova(self):
        # Medians2,3; absolute deviations [1,0,1],[2,0,2].
        # Between SS2/3, withinSS10/3; DF1,4 -> F4/5.
        r=equal_variances([[1,2,3],[1,3,5]])
        self.assertAlmostEqual(r['test_statistic'],.8,places=14)
        self.assertEqual(r['df'],[1,4])
        # F(1,4) is t(4)^2; separate distribution identity validates tail.
        self.assertAlmostEqual(r['p_value'],float(2*stats.t.sf(math.sqrt(.8),4)),places=14)
        self.assertIn('Brown-Forsythe',r['method'])
        self.assertEqual([g['median'] for g in r['group_statistics']],[2,3])

    def test_hand_bartlett_and_chi_square_one_tail(self):
        # Sample variances1,4; pooled variance2.5 and correction1.25.
        t=(4*math.log(2.5)-2*math.log(4))/1.25
        r=equal_variances([[1,2,3],[1,3,5]],method='Bartlett')
        self.assertAlmostEqual(r['test_statistic'],t,places=14)
        self.assertAlmostEqual(r['p_value'],math.erfc(math.sqrt(t/2)),places=14)
        self.assertEqual(r['df'],1);self.assertIsNone(r['df_denominator'])

    def test_unequal_sizes_skewed_group_independent_scipy_fixtures(self):
        groups=[[float(v) for v in g] for g in [[0,1,1,9],[2,3,4,5,6],[1,2,4,8,16,32]]]
        for method,reference in [('Levene',stats.levene(*groups,center='median')),
                                 ('Bartlett',stats.bartlett(*groups))]:
            r=equal_variances(groups,method)
            self.assertAlmostEqual(r['test_statistic'],float(reference.statistic),places=12)
            self.assertAlmostEqual(r['p_value'],float(reference.pvalue),places=13)

    def test_equal_spreads_shifted_groups_and_scale_invariance(self):
        for method in ('Levene','Bartlett'):
            r=equal_variances([[1,2,3],[11,12,13]],method)
            self.assertEqual(r['test_statistic'],0);self.assertEqual(r['p_value'],1)
            a=equal_variances([[1,2,3],[1,3,5]],method)
            b=equal_variances([[1e100,2e100,3e100],[1e100,3e100,5e100]],method)
            self.assertAlmostEqual(a['test_statistic'],b['test_statistic'],places=12)

    def test_missing_independent_by_group_and_summary(self):
        r=equal_variances([[1,None,2,3,MISSING_SENTINEL],[1,math.inf,3,5,math.nan]])
        self.assertEqual((r['count'],r['missing']),(6,4))
        self.assertEqual([(g['count'],g['missing']) for g in r['group_statistics']],[(3,2),(3,2)])
        self.assertAlmostEqual(r['test_statistic'],.8,places=14)

    def test_degenerate_residuals_and_zero_variances(self):
        for groups in ([[1,1,1],[2,2,2]],[[1,3],[1,5]]):
            with self.assertRaises(ValueError):equal_variances(groups)
        for groups in ([[1,1,1],[1,2,3]],[[1,1,1],[1,1,1]]):
            with self.assertRaises(ValueError):equal_variances(groups,'Bartlett')
        # One constant group is valid for Brown-Forsythe when denominator >0.
        self.assertTrue(math.isfinite(equal_variances([[1,1,1],[1,2,3]])['test_statistic']))

    def test_validation_method_and_finite_arithmetic(self):
        for groups in ([],[[1,2,3]],[[1],[1,2]],[[None,1],[1,2]]):
            with self.assertRaises(ValueError):equal_variances(groups)
        for method in ('Bonett','mean',None):
            with self.assertRaises(ValueError):equal_variances([[1,2,3],[1,3,5]],method)
        with self.assertRaises(TypeError):equal_variances([[True,2],[1,3]])
        with self.assertRaises(ValueError):equal_variances([[-1e308,1e308],[1,2,3]])
        a=equal_variances([[1,2,3],[1,3,5]],'Brown-Forsythe')
        self.assertAlmostEqual(a['test_statistic'],.8,places=14)


if __name__=='__main__':unittest.main()
