"""Analytic reliability fixtures replacing hardcoded inference placeholders."""
import json
import math
import unittest
import numpy as np
from scipy import stats
from statcraft.reliability_engine import run_reliability_analysis, fit_parametric_reliability, fit_kaplan_meier


class ReliabilityInferenceTests(unittest.TestCase):
    def test_exponential_censored_mle_information(self):
        r=run_reliability_analysis([1,2,3,4], [1,1,0,1], dist_name='exponential')
        theta=10/3
        self.assertAlmostEqual(r['parameters']['scale_mean'],theta)
        self.assertAlmostEqual(r['log_likelihood'],-3*math.log(theta)-3)
        self.assertAlmostEqual(r['parameter_se']['scale_mean'],theta/math.sqrt(3),places=5)
        self.assertIsNone(r['ad_stat'])
        self.assertTrue(any('goodness-of-fit' in note for note in r['warnings']))
        json.dumps(r,allow_nan=False)

    def test_confidence_interval_changes_with_sample_size(self):
        small=run_reliability_analysis([1,2,3,4,5],dist_name='exponential')
        large=run_reliability_analysis([1,2,3,4,5]*20,dist_name='exponential')
        a=small['percentile_table'][4]; b=large['percentile_table'][4]
        self.assertAlmostEqual(a['estimate'],b['estimate'])
        self.assertLess(b['upper']-b['lower'],a['upper']-a['lower'])
        self.assertAlmostEqual(large['parameter_se']['scale_mean']/small['parameter_se']['scale_mean'],1/math.sqrt(20),places=5)

    def test_confidence_level_changes_bounds(self):
        a=run_reliability_analysis([1,2,3,5,8,13],dist_name='exponential',confidence_level=.8)
        b=run_reliability_analysis([1,2,3,5,8,13],dist_name='exponential',confidence_level=.99)
        self.assertLess(a['percentile_table'][0]['upper'],b['percentile_table'][0]['upper'])
        self.assertGreater(a['percentile_table'][0]['lower'],b['percentile_table'][0]['lower'])

    def test_ad_matches_direct_uncensored_definition_and_varies_with_data(self):
        times=np.array([1.,2,3,5,8,13])
        r=run_reliability_analysis(times,dist_name='exponential')
        fitted=stats.expon(scale=np.mean(times))
        n=len(times); i=np.arange(1,n+1)
        expected=-n-np.sum((2*i-1)*(fitted.logcdf(times)+fitted.logsf(times[::-1])))/n
        self.assertAlmostEqual(r['ad_stat'],expected)
        other=run_reliability_analysis([1,1,1,1,1,20],dist_name='exponential')
        self.assertNotAlmostEqual(r['ad_stat'],other['ad_stat'])

    def test_lognormal_mle_matches_uncensored_analytic_solution(self):
        times=np.exp(np.array([1.,1.1,1.6,1.8,2,2.2,2.5,3]))
        r=run_reliability_analysis(times,dist_name='lognormal')
        self.assertAlmostEqual(r['parameters']['location'],np.mean(np.log(times)),places=5)
        self.assertAlmostEqual(r['parameters']['scale'],np.std(np.log(times)),places=5)
        self.assertTrue(all(row['lower']<row['estimate']<row['upper'] for row in r['percentile_table']))
        json.dumps(r,allow_nan=False)

    def test_normal_mle_and_negative_lower_tail_are_preserved(self):
        times=[.1,.2,.3,.5,1,2,3,5]
        r=run_reliability_analysis(times,dist_name='normal')
        self.assertAlmostEqual(r['parameters']['mean'],np.mean(times),places=5)
        self.assertAlmostEqual(r['parameters']['stdev'],np.std(times),places=5)
        self.assertLess(r['percentile_table'][0]['estimate'],0)
        self.assertLess(r['percentile_table'][0]['lower'],0)

    def test_weibull_uncensored_matches_scipy_fit(self):
        times=[2,3,5,7,11,13,17,19,23,29]
        r=run_reliability_analysis(times,dist_name='weibull')
        shape,_,scale=stats.weibull_min.fit(times,floc=0)
        self.assertAlmostEqual(r['parameters']['shape'],shape,places=4)
        self.assertAlmostEqual(r['parameters']['scale'],scale,places=3)
        json.dumps(r,allow_nan=False)

    def test_missing_time_and_censor_are_omitted_together(self):
        r=run_reliability_analysis([1,None,3,4,5,6],[1,0,0,1,None,1],dist_name='exponential')
        self.assertEqual(r['times'],[1,3,4,6])
        self.assertEqual(r['events'],[1,0,1,1])
        self.assertEqual(r['used_rows'],[1,3,4,6])
        self.assertEqual(r['missing_rows'],[2,5])
        self.assertAlmostEqual(r['mttf'],14/3)

    def test_custom_censor_label(self):
        r=run_reliability_analysis([1,2,3,4],['Failed','Censored','Failed','Failed'],censor_value='Censored',dist_name='exponential')
        self.assertEqual(r['events'],[1,0,1,1])

    def test_kaplan_meier_ties_and_terminal_zero_are_json_safe(self):
        r=fit_kaplan_meier([1,1,2,3],[1,0,1,1])
        self.assertEqual(r['n_at_risk'],[4,2,1])
        self.assertEqual(r['survival'],[.75,.375,0])
        self.assertEqual(r['cum_hazard'][-1],None)
        json.dumps(r,allow_nan=False)

    def test_unidentifiable_information_is_explicit_and_json_safe(self):
        from unittest.mock import patch
        with patch('statcraft.reliability_engine._observed_covariance',return_value=None):
            r=run_reliability_analysis([1,2,3,4],dist_name='exponential')
        self.assertEqual(r['parameter_ci']['scale_mean'],[None,None])
        self.assertIsNone(r['percentile_table'][0]['lower'])
        self.assertTrue(any('unavailable' in note for note in r['warnings']))
        json.dumps(r,allow_nan=False)

    def test_failed_optimizers_do_not_publish_fit(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        failed=SimpleNamespace(success=False,x=np.array([0.,1.]))
        with patch('statcraft.reliability_engine.minimize',return_value=failed):
            with self.assertRaisesRegex(ValueError,'converge'):
                run_reliability_analysis([1,2,3,4],dist_name='weibull')

    def test_unbounded_scale_fit_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'finite scale'):
            run_reliability_analysis([2,2,1],[1,1,0],dist_name='normal')

    def test_invalid_inputs_reject_instead_of_silently_fitting(self):
        for times in ([0,1,2],[-1,2,3],[float('nan'),2,3],[float('inf'),2,3],[True,2,3]):
            with self.subTest(times=times),self.assertRaises(ValueError):
                run_reliability_analysis(times,dist_name='exponential')
        for level in (0,1,-1,float('nan'),True,95):
            with self.subTest(level=level),self.assertRaises(ValueError):
                run_reliability_analysis([1,2,3],confidence_level=level)
        with self.assertRaises(ValueError):run_reliability_analysis([1,2,3],[1,0])
        with self.assertRaises(ValueError):run_reliability_analysis([1,2,3],[1,2,1])
        with self.assertRaises(ValueError):run_reliability_analysis([1,2,3],[0,0,0])
        with self.assertRaises(ValueError):run_reliability_analysis([1,1,1],dist_name='weibull')


if __name__=='__main__': unittest.main()

