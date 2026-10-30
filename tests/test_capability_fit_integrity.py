"""Independent fitted-CDF and selected-model integrity regressions."""
import json
import unittest
import numpy as np
from scipy import stats
from statcraft.capability_nonnormal_engine import fit_nonnormal_distribution, run_nonnormal_capability, fitted_anderson_darling
from statcraft.capability_automated_engine import run_automated_capability_tournament


def direct_ad(values, distribution):
    ordered=np.sort(values)
    cdf=distribution.cdf(ordered)
    n=len(ordered)
    return float(-n-np.sum((2*np.arange(1,n+1)-1)*(np.log(cdf)+np.log1p(-cdf[::-1])))/n)


class CapabilityFitIntegrityTests(unittest.TestCase):
    def test_ad_uses_each_actual_fitted_family(self):
        data=np.array([.5,.8,1.2,1.9,2.1,3,4,5,7,10.])
        scores=[]
        for family in ('weibull','lognormal','gamma','exponential','normal'):
            with self.subTest(family=family):
                result=fit_nonnormal_distribution(data,family)
                p=result['parameters']
                if family=='weibull':d=stats.weibull_min(p['shape'],scale=p['scale'])
                elif family=='lognormal':d=stats.lognorm(p['scale_sigma'],scale=np.exp(p['location_mu']))
                elif family=='gamma':d=stats.gamma(p['shape'],scale=p['scale'])
                elif family=='exponential':d=stats.expon(scale=p['scale_mean'])
                else:d=stats.norm(loc=p['mean'],scale=p['stdev'])
                self.assertAlmostEqual(result['ad_stat'],direct_ad(data,d),places=10)
                self.assertIsNone(result['p_value'])
                self.assertIn('No calibrated p-value',result['goodness_of_fit_note'])
                scores.append(result['ad_stat'])
        self.assertGreater(len(set(round(v,8) for v in scores)),3)

    def test_positive_normal_winner_runs_normal_capability(self):
        data=np.random.default_rng(0).normal(10,1,40)
        result=run_automated_capability_tournament(data,lsl=5,usl=15)
        self.assertEqual(result['best_fit']['distribution'],'Normal')
        self.assertEqual(result['method'],'normal')
        self.assertEqual(result['fit_info']['dist_name'],'normal')
        p=result['fit_info']['parameters']
        self.assertAlmostEqual(p['mean'],np.mean(data))
        self.assertAlmostEqual(p['stdev'],np.std(data))
        self.assertAlmostEqual(result['expected_ppm']['below'],stats.norm.cdf(5,loc=np.mean(data),scale=np.std(data))*1e6)
        self.assertNotIn('shape',p)
        json.dumps(result,allow_nan=False)

    def test_negative_normal_data_does_not_fall_back_to_empirical(self):
        data=np.array([-3,-2,-1,-.5,0,.5,1,2,3])
        result=run_automated_capability_tournament(data,lsl=-4,usl=4)
        self.assertEqual(result['method'],'normal')
        self.assertEqual(result['best_fit']['distribution'],'Normal')
        self.assertIn('expected_ppm',result)
        self.assertAlmostEqual(result['p_lower'],stats.norm.ppf(.00135,loc=np.mean(data),scale=np.std(data)))

    def test_box_cox_winner_carries_the_same_transform(self):
        data=np.exp(stats.norm.ppf((np.arange(40)+.5)/40))
        result=run_automated_capability_tournament(data,lsl=.05,usl=50)
        self.assertEqual(result['best_fit']['method'],'box_cox')
        self.assertEqual(result['method'],'box_cox')
        self.assertEqual(result['fit_info']['lambda'],result['best_fit']['lambda'])
        fit=result['fit_info']
        expected=direct_ad(fit['transformed'],stats.norm(loc=fit['mean_trans'],scale=fit['std_trans']))
        self.assertAlmostEqual(result['best_fit']['ad_stat'],expected,places=9)
        self.assertAlmostEqual(result['fit_info']['ad_stat'],expected,places=9)

    def test_no_invented_p_values_or_fallback_scores(self):
        data=[1,2,3,4,5,7,9,12,15]
        result=run_automated_capability_tournament(data,lsl=.1,usl=20)
        for row in result['tournament']:
            self.assertIsNone(row['p_val'])
            self.assertTrue(row['diagnostic_note'])
        self.assertEqual(result['best_fit']['ad_stat'],min(row['ad_stat'] for row in result['tournament'] if row['eligible']))
        self.assertTrue(result['warnings'])
        json.dumps(result,allow_nan=False)

    def test_box_cox_domain_is_not_serialized_as_infinite_indices(self):
        with self.assertRaisesRegex(ValueError,'positive specification'):
            run_nonnormal_capability([1,2,3,4,5],dist_or_transform='box_cox',lsl=0,usl=10)
        result=run_automated_capability_tournament([1,2,3,4,5],lsl=0,usl=10)
        box_cox=[row for row in result['tournament'] if row['method']=='box_cox'][0]
        self.assertFalse(box_cox['eligible'])
        self.assertNotEqual(result['method'],'box_cox')
        json.dumps(result,allow_nan=False)

    def test_ad_unavailable_is_none(self):
        class BrokenCDF:
            def logcdf(self,x):return np.full(len(x),-np.inf)
            def logsf(self,x):return np.full(len(x),-np.inf)
        self.assertIsNone(fitted_anderson_darling([1,2,3],BrokenCDF()))

    def test_invalid_nonnormal_inputs_fail_explicitly(self):
        for data in ([1,1,1],[1,float('nan'),3],[1,float('inf'),3],[True,2,3]):
            with self.subTest(data=data),self.assertRaises(ValueError):
                run_nonnormal_capability(data,lsl=.1,usl=5)
        for params in ({'lsl':5,'usl':1},{'lsl':float('nan'),'usl':5},{'lsl':1,'usl':5,'confidence_level':1}):
            with self.subTest(params=params),self.assertRaises(ValueError):
                run_nonnormal_capability([1,2,3,4],**params)


if __name__=='__main__':unittest.main()
