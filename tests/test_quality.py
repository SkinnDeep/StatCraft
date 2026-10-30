import math
import unittest
from statcraft.quality import individuals_moving_range, normal_capability, D2, D3


class QualityTests(unittest.TestCase):
    def test_hand_calculated_span_two_limits(self):
        result = individuals_moving_range([1,2,3,4,5])
        self.assertEqual(result['mean'], 3)
        self.assertEqual(result['moving_ranges'], [None,1,1,1,1])
        self.assertAlmostEqual(result['within_stdev'], math.sqrt(math.pi)/2)
        self.assertAlmostEqual(result['i_ucl'], 3 + 3*math.sqrt(math.pi)/2)
        self.assertAlmostEqual(result['mr_ucl'], 1 + 3*D3/D2)
        self.assertEqual(result['mr_lcl'], 0)

    def test_missing_preserves_row_numbers_and_breaks_pairs(self):
        result = individuals_moving_range([1,None,3,4,None,5])
        self.assertEqual(result['moving_ranges'], [None,None,None,1,None,None])
        self.assertEqual(result['count'], 4)
        self.assertEqual(result['missing'], 2)
        with self.assertRaises(ValueError): individuals_moving_range([1,None,2])

    def test_signal_indices_and_constants(self):
        result = individuals_moving_range([0]*20 + [10] + [0]*20)
        self.assertEqual(result['i_signals'], [21])
        self.assertEqual(result['mr_signals'], [21,22])
        self.assertEqual(individuals_moving_range([7,7,7])['within_stdev'], 0)
        with self.assertRaises(ValueError): normal_capability([7,7,7],0,10)

    def test_hand_calculated_capability_and_target(self):
        result = normal_capability([1,2,3,4,5],0,6,3)
        self.assertAlmostEqual(result['cp'], 2/math.sqrt(math.pi))
        self.assertAlmostEqual(result['cpk'], result['cp'])
        self.assertAlmostEqual(result['pp'], 1/math.sqrt(2.5))
        self.assertAlmostEqual(result['cpm'], 1/math.sqrt(2))
        self.assertEqual(result['observed_ppm_total'], 0)
        self.assertAlmostEqual(result['expected_overall_ppm_below'], result['expected_overall_ppm_above'])
        shifted = normal_capability([1,2,3,4,5],0,6,2)
        self.assertAlmostEqual(shifted['cpm'], 2/(3*math.sqrt(3)))
        one_sided = normal_capability([1,2,3,4,5],usl=6,target=3)
        self.assertAlmostEqual(one_sided['cpm'], 1/math.sqrt(2))

    def test_one_sided_and_outside_limits(self):
        result = normal_capability([1,2,3,4,5],usl=2)
        self.assertIsNone(result['cp']); self.assertIsNone(result['cpl'])
        self.assertLess(result['cpk'], 0)
        self.assertEqual(result['observed_ppm_above'], 600000)
        self.assertGreater(result['expected_overall_ppm_total'], 500000)

    def test_invalid_inputs_and_overflow(self):
        for values, lower, upper in [([1],0,2),([1,2],3,2),([1,2],None,None),([1,2],math.inf,3),([-1e308,1e308],0,10)]:
            with self.assertRaises((ValueError, OverflowError)): normal_capability(values,lower,upper)
