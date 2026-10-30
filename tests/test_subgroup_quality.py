import math
import unittest
from statcraft.engine import MISSING_SENTINEL
from statcraft.subgroup_quality import xbar_r


class SubgroupQualityTests(unittest.TestCase):
    def test_size_two_hand_calculation_and_both_tail_mean_signals(self):
        r=xbar_r([[0,2],[4,6],[8,10]])
        self.assertEqual(r['means'],[1,5,9]);self.assertEqual(r['ranges'],[2,2,2])
        self.assertEqual((r['count'],r['subgroup_size'],r['xbar_center'],r['r_center']),(3,2,5,2))
        self.assertAlmostEqual(r['within_stdev'],250/141,places=13)
        width=750/(141*math.sqrt(2))
        self.assertAlmostEqual(r['xbar_lcl'],5-width,places=13)
        self.assertAlmostEqual(r['xbar_ucl'],5+width,places=13)
        self.assertEqual(r['r_lcl'],0)
        self.assertAlmostEqual(r['r_ucl'],2+3*.8525*(250/141),places=13)
        self.assertEqual(r['xbar_signals'],[1,3]);self.assertEqual(r['r_signals'],[])

    def test_size_five_means_and_average_range(self):
        r=xbar_r([[1,2,3,4,5],[2,3,4,5,6],[3,4,5,6,7]])
        self.assertEqual(r['means'],[3,4,5]);self.assertEqual(r['ranges'],[4,4,4])
        self.assertEqual(r['xbar_center'],4)
        self.assertAlmostEqual(r['within_stdev'],2000/1163,places=13)
        self.assertAlmostEqual(r['r_ucl'],4+3*.8641*2000/1163,places=13)
        self.assertEqual(r['xbar_signals'],[])

    def test_size_ten_positive_range_lower_limit(self):
        groups=[list(range(10))]*9+[[4.5]*10]
        r=xbar_r(groups)
        self.assertAlmostEqual(r['r_center'],8.1,places=13)
        self.assertGreater(r['r_lcl'],0)
        self.assertEqual(r['r_signals'],[10]);self.assertEqual(r['xbar_signals'],[])

    def test_isolated_range_excursion(self):
        r=xbar_r([[-1,1]]*9+[[-100,100]])
        self.assertAlmostEqual(r['r_center'],21.8,places=13)
        self.assertEqual(r['r_signals'],[10]);self.assertEqual(r['xbar_signals'],[])

    def test_wholly_missing_gaps_original_subgroup_signals(self):
        r=xbar_r([[0,2],[None,MISSING_SENTINEL],[4,6],[8,10]])
        self.assertEqual(r['means'],[1,None,5,9]);self.assertEqual(r['ranges'],[2,None,2,2])
        self.assertEqual((r['count'],r['missing'],r['row_indices']),(3,1,[0,2,3]))
        self.assertEqual(r['xbar_signals'],[1,4])

    def test_missing_ragged_and_size_domain(self):
        for groups in ([],[[None,None]],[[1,None]],[[1,2],[None]],[[1,2],[3,4,5]],
                       [[1]], [list(range(11))], [[]]):
            with self.assertRaises(ValueError):xbar_r(groups)

    def test_nonfinite_bool_and_text_policy(self):
        for value in (math.nan,math.inf,-math.inf):
            with self.assertRaisesRegex(ValueError,'finite'):xbar_r([[value,value]])
        for value in (True,'2',complex(1,2)):
            with self.assertRaises(TypeError):xbar_r([[1,value]])

    def test_zero_range_equality_and_single_subgroup_warnings(self):
        r=xbar_r([[7,7],[7,7]])
        self.assertEqual((r['within_stdev'],r['xbar_lcl'],r['xbar_ucl']),(0,7,7))
        self.assertEqual(r['xbar_signals'],[]);self.assertEqual(r['r_signals'],[])
        self.assertTrue(r['warnings'])
        r=xbar_r([[1,3]])
        self.assertTrue(r['warnings']);self.assertEqual(r['count'],1)

    def test_translation_scale_preserves_signals(self):
        groups=[[0,2],[4,6],[8,10]]
        a=xbar_r(groups); b=xbar_r([[100+3*v for v in g] for g in groups])
        self.assertEqual(a['xbar_signals'],b['xbar_signals'])
        self.assertEqual(a['r_signals'],b['r_signals'])
        self.assertAlmostEqual(b['within_stdev'],3*a['within_stdev'],places=12)
        self.assertAlmostEqual(b['xbar_lcl'],100+3*a['xbar_lcl'],places=12)

    def test_overflow_is_explicit_and_large_stable_mean(self):
        with self.assertRaises(ValueError):xbar_r([[-1e308,1e308]])
        r=xbar_r([[1e308,1e308],[1e308,1e308]])
        self.assertEqual(r['xbar_center'],1e308);self.assertEqual(r['r_center'],0)


if __name__=='__main__':unittest.main()
