import json
import math
from pathlib import Path
import tempfile
import unittest
import statistics
from statcraft.normality import normality, one_variance
from statcraft.app import Presenter
from statcraft.model import Worksheet, Column
from statcraft._mpx_fixture import write_blob_fixture

SAMPLE=[-1.5,-1,-.5,-.1,.1,.5,1,1.5]


class NormalityTests(unittest.TestCase):
    def test_ad_statistic_from_definition(self):
        r=normality(SAMPLE); n=len(SAMPLE); sd=statistics.stdev(SAMPLE)
        cdf=[.5*(1+math.erf(x/sd/math.sqrt(2))) for x in SAMPLE]
        expected=-n-sum((2*i-1)*(math.log(cdf[i-1])+math.log(1-cdf[n-i])) for i in range(1,n+1))/n
        self.assertAlmostEqual(r['anderson_darling'],expected,places=12)
        self.assertGreater(r['p_value'],.5); self.assertFalse(r['reject_at_5_percent'])

    def test_location_scale_and_permutation_invariance(self):
        a=normality(SAMPLE); b=normality([v*3+50 for v in reversed(SAMPLE)])
        self.assertAlmostEqual(a['anderson_darling'],b['anderson_darling'],places=11)
        self.assertAlmostEqual(a['p_value'],b['p_value'],places=10)

    def test_missing_and_plot_position_symmetry(self):
        r=normality(SAMPLE+[None,float('nan')]); d=r['graph_data']
        self.assertEqual((r['count'],r['missing']),(8,2))
        self.assertEqual(d['observed'],SAMPLE)
        for a,b in zip(d['normal_scores'],reversed(d['normal_scores'])): self.assertAlmostEqual(a,-b)
        self.assertAlmostEqual(d['reference_y'][0],SAMPLE[0]/statistics.stdev(SAMPLE))
        json.dumps(r,allow_nan=False)

    def test_heavy_tail_and_unsupported_p_range_are_explicit(self):
        r=normality([0]*99+[100])
        self.assertTrue(r['reject_at_5_percent']); self.assertIsNone(r['p_value'])
        self.assertTrue(any('supported range' in v for v in r['warnings']))
        json.dumps(r,allow_nan=False)

    def test_constant_short_and_nonnumeric_rejected(self):
        for sample in ([1]*10,[1,2,3],[None]*10,['1']*10,[True]*10):
            with self.assertRaises((ValueError,TypeError)): normality(sample)

    def test_ties_and_small_sample_notices(self):
        r=normality([0,0,1,1,2,2,3,3])
        self.assertTrue(any('Ties' in v for v in r['warnings']))
        self.assertTrue(any('Small' in v for v in r['warnings']))


class VarianceTests(unittest.TestCase):
    def test_chi_square_df_two_has_analytic_tail_and_interval(self):
        r=one_variance([1,2,3],1,.95)
        self.assertAlmostEqual(r['chi_square'],2)
        self.assertEqual(r['degrees_of_freedom'],2)
        self.assertAlmostEqual(r['p_value'],2/math.e)
        self.assertAlmostEqual(r['variance_ci_low'],2/(-2*math.log(.025)))
        self.assertAlmostEqual(r['variance_ci_high'],2/(-2*math.log(.975)))

    def test_missing_values_and_scale_behavior(self):
        a=one_variance([1,2,None,3]); b=one_variance([10,20,30],10)
        self.assertEqual((a['count'],a['missing']),(3,1))
        self.assertAlmostEqual(a['p_value'],b['p_value'])
        self.assertAlmostEqual(a['stdev_ci_high']*10,b['stdev_ci_high'])
        self.assertAlmostEqual(a['variance_ci_low']*100,b['variance_ci_low'])

    def test_invalid_null_and_confidence(self):
        for null in (0,-1,None,float('nan'),True):
            with self.assertRaises((ValueError,TypeError)): one_variance([1,2,3],null)
        for confidence in (0,1,-1):
            with self.assertRaises(ValueError): one_variance([1,2,3],confidence=confidence)

    def test_constant_empty_short_and_extreme_range(self):
        for sample in ([],[1],[None,1],[3,3],[1e308,-1e308]):
            with self.assertRaises((ValueError,OverflowError)): one_variance(sample)


class NormalityIntegrationTests(unittest.TestCase):
    def test_dependency_tracking_and_failed_rerun(self):
        p=Presenter(); p.worksheet=Worksheet('Data',[Column('X',values=SAMPLE[:])])
        original=p.normality(0); variance=p.one_variance(0)
        p.set_cell(0,0,'-2'); self.assertTrue(p.result_stale(original))
        self.assertFalse(p.result_stale(p.rerun_result(original)))
        self.assertFalse(p.result_stale(p.rerun_result(variance)))
        for row in range(8): p.set_cell(row,0,'1')
        history=len(p.history)
        with self.assertRaises(ValueError): p.rerun_result(original)
        self.assertEqual(len(p.history),history)

    def test_variance_recipe_mpx_roundtrip_uses_origin_sheet(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'source.mpx',Path(folder)/'copy.mpx'; write_blob_fixture(source)
            p=Presenter(); p.load(source); original=p.one_variance(0,2,.9); p.save(target)
            q=Presenter(); q.load(target); own=[e for e in q.history if e.get('origin')=='statcraft']
            self.assertEqual(own[0]['recipe'],original['recipe'])
            q.select_worksheet(0); rerun=q.rerun_result(own[0])
            self.assertEqual(rerun['result'],original['result']); self.assertEqual(q.native_project.active_index,1)
