import math
import unittest
from statcraft.engine import MISSING_SENTINEL
from statcraft.attribute_quality import p_chart, u_chart


class AttributeQualityTests(unittest.TestCase):
    def test_p_weighted_center_and_variable_limits_closed_form(self):
        r=p_chart([10,40],[100,200])
        self.assertAlmostEqual(r['center'],1/6,places=14)
        self.assertNotAlmostEqual(r['center'],(.1+.2)/2)
        for i,n in enumerate([100,200]):
            d=3*math.sqrt(5/(36*n))
            self.assertAlmostEqual(r['lcl'][i],1/6-d,places=14)
            self.assertAlmostEqual(r['ucl'][i],1/6+d,places=14)
        self.assertEqual(r['observations'],[.1,.2]); self.assertEqual(r['signals'],[])

    def test_u_weighted_center_fractional_exposure(self):
        r=u_chart([2,12],[.5,3.5])
        self.assertEqual(r['center'],3.5)
        self.assertEqual(r['observations'],[4,12/3.5])
        self.assertEqual(r['lcl'][0],0)
        self.assertAlmostEqual(r['ucl'][0],3.5+3*math.sqrt(7),places=14)
        self.assertAlmostEqual(r['lcl'][1],.5,places=14)
        self.assertAlmostEqual(r['ucl'][1],6.5,places=14)
        self.assertEqual(r['total_count'],14)

    def test_p_clipping_and_test_one_original_row_numbers(self):
        r=p_chart([0]*9+[100],[100]*10)
        self.assertEqual(r['signals'],[1,2,3,4,5,6,7,8,9,10])
        # Sparse proportions clip LCL to zero; small denominators can clip UCL.
        r=p_chart([0,1],[1,1])
        self.assertEqual(r['lcl'],[0,0]);self.assertEqual(r['ucl'],[1,1])
        self.assertEqual(r['signals'],[])

    def test_u_counts_can_exceed_exposure_and_test_one_signals(self):
        r=u_chart([0]*9+[100],[1]*10)
        self.assertEqual(r['center'],10)
        self.assertEqual(r['signals'],list(range(1,11)))
        self.assertGreater(r['ucl'][0],1)

    def test_aligned_missing_pairs_preserve_plot_gaps(self):
        for fn in (p_chart,u_chart):
            r=fn([1,None,3,4,math.nan,MISSING_SENTINEL],[10,20,None,40,50,60])
            self.assertEqual((r['count'],r['missing'],r['row_indices']),(2,4,[0,3]))
            self.assertEqual(r['center'],.1)
            for key in ['counts','sample_sizes','observations','center_line','lcl','ucl','signal_flags']:
                self.assertEqual(len(r[key]),6)
                for i in [1,2,4,5]:self.assertIsNone(r[key][i])

    def test_zero_all_defective_and_single_subgroup_policies(self):
        for fn in (p_chart,u_chart):
            r=fn([0,0],[10,20]);self.assertEqual(r['center'],0)
            self.assertEqual(r['lcl'],[0,0]);self.assertEqual(r['ucl'],[0,0])
            self.assertEqual(r['signals'],[]);self.assertTrue(r['warnings'])
        r=p_chart([10,20],[10,20]);self.assertEqual(r['center'],1)
        self.assertEqual(r['lcl'],[1,1]);self.assertEqual(r['ucl'],[1,1])
        self.assertTrue(p_chart([1],[10])['warnings'])

    def test_strict_count_trials_and_pair_validation(self):
        for fn in (p_chart,u_chart):
            for counts,sizes in [([],[]),([None],[10]),([1],[None]),([1,2],[10]),
                                 ([-1],[10]),([.5],[10]),([2**54],[10]),([2**53+1],[10]),
                                 ([1],[0]),([1],[-2]),([None],[-1])]:
                with self.assertRaises(ValueError):fn(counts,sizes)
            for counts,sizes in [([True],[10]),([1],['10'])]:
                with self.assertRaises(TypeError):fn(counts,sizes)
        for counts,sizes in [([2],[1]),([1],[1.5]),([1],[2**54])]:
            with self.assertRaises(ValueError):p_chart(counts,sizes)

    def test_finite_domain_overflow_has_helpful_failure(self):
        with self.assertRaises(ValueError):u_chart([1,2],[1e308,1e308])
        with self.assertRaises(ValueError):u_chart([1],[1e-320])

    def test_limits_equal_observation_are_not_signals(self):
        # Center 9 and exposure1 gives LCL0/UCL18: observations on limits.
        r=u_chart([0,18],[1,1])
        self.assertEqual(r['lcl'],[0,0]);self.assertEqual(r['ucl'],[18,18])
        self.assertEqual(r['signals'],[]);self.assertEqual(r['signal_flags'],[False,False])


if __name__=='__main__':unittest.main()
