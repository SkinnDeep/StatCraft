"""Regression: pooled and unbiased capability estimates must work beyond gamma overflow."""
import math
import unittest
from statcraft.capability_engine import c4,run_normal_capability,compute_ppm_and_z

class LargeCapabilitySamples(unittest.TestCase):
    def test_unbiasing_constant_large_sample_is_finite_and_approaches_one(self):
        values=[c4(n) for n in (100,1000,1200,10000)]
        self.assertEqual(values,sorted(values))
        for n in (1000,1200,10000):
            self.assertTrue(0<c4(n)<1)
            self.assertAlmostEqual(c4(n),1-1/(4*(n-1)),delta=1e-7)

    def test_large_pooled_and_unbiased_overall_estimates_do_not_overflow(self):
        data=[10+math.sin(i*.71)+math.cos(i*.21)*.4 for i in range(1200)]
        result=run_normal_capability(data,subgroup_spec=5,lsl=6,usl=14,
                                     unbiased_within=True,unbiased_overall=True)
        self.assertEqual(result['sample_n'],1200)
        for key in ('stdev_within','stdev_overall','cp','cpk','pp','ppk'):
            self.assertTrue(math.isfinite(result[key]))
            self.assertGreater(result[key],0)

    def test_small_fitted_tail_probability_produces_finite_benchmark_z(self):
        result=compute_ppm_and_z([-1,0,1],0,1,lsl=-10,usl=10)
        self.assertGreater(result['expected_total'],0)
        self.assertTrue(math.isfinite(result['z_bench']))
        self.assertAlmostEqual(result['z_bench'],9.93112595805722,places=10)

    def test_rounded_tail_endpoints_are_unavailable_instead_of_arbitrary_five(self):
        self.assertIsNone(compute_ppm_and_z([-1,0,1],0,1,-40,40)['z_bench'])
        self.assertIsNone(compute_ppm_and_z([-1,0,1],0,1,40,50)['z_bench'])
