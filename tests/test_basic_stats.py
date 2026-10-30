import json
import math
from pathlib import Path
import tempfile
import unittest
from statcraft.basic_stats import correlation, one_proportion, two_proportions
from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet
from statcraft._mpx_fixture import write_subgroup_fixture
from statcraft.recipes import columns


class CorrelationTests(unittest.TestCase):
    def test_perfect_positive_and_negative_and_fisher_bounds(self):
        r = correlation([[1,2,3,4],[2,4,6,8],[8,6,4,2]],['A','B','C'])
        self.assertEqual(len(r['correlations']),3)
        for record in r['correlations']:
            self.assertAlmostEqual(abs(record['correlation']),1)
            self.assertAlmostEqual(record['p_value'],0)
            self.assertAlmostEqual(record['ci_low'],record['correlation'])
            self.assertAlmostEqual(record['ci_high'],record['correlation'])

    def test_tied_spearman_published_scipy_example(self):
        row=correlation([[1,2,3,4,5],[5,6,7,8,7]],['X','Y'],'Spearman')['correlations'][0]
        self.assertAlmostEqual(row['correlation'],.8207826816681233)
        self.assertAlmostEqual(row['p_value'],.08858700531354381)
        self.assertNotIn('ci_low',row)

    def test_pairwise_listwise_different_n_and_ragged_alignment(self):
        values=[[1,2,3,4,5],[2,None,6,8],[9,8,None,6,5]]
        pair=correlation(values,['A','B','C'])['correlations']
        whole=correlation(values,['A','B','C'],missing='Listwise')['correlations']
        self.assertEqual([r['count'] for r in pair],[3,4,2])
        self.assertEqual([r['count'] for r in whole],[2,2,2])
        self.assertEqual(pair[0]['missing'],2)
        self.assertIsNone(whole[0]['correlation'])

    def test_constant_and_short_pairs_are_missing_with_explanation(self):
        result=correlation([[1,1,1],[2,3,4]],['constant','other'])
        self.assertIsNone(result['correlations'][0]['p_value'])
        self.assertTrue(any('constant' in s for s in result['warnings']))
        json.dumps(result,allow_nan=False)

    def test_three_pairs_have_full_fisher_interval(self):
        row=correlation([[1,2,3],[2,4,3]],['A','B'])['correlations'][0]
        self.assertEqual((row['ci_low'],row['ci_high']),(-1,1))

    def test_spearman_small_sample_limitation_reported(self):
        result=correlation([[1,2,3],[3,2,1]],['A','B'],'Spearman')
        self.assertTrue(any('permutation' in s for s in result['warnings']))

    def test_invalid_configuration_rejected(self):
        for kwargs in ({'confidence':1},{'method':'eval'},{'missing':'Drop anything'}):
            with self.assertRaises(ValueError): correlation([[1,2,3],[3,2,1]],['A','B'],**kwargs)


class ProportionTests(unittest.TestCase):
    def test_exact_zero_events_reference_and_interval(self):
        r=one_proportion([0]*10)
        self.assertAlmostEqual(r['p_value'],2/1024)
        self.assertEqual(r['ci_low'],0)
        self.assertAlmostEqual(r['ci_high'],1-.025**.1)

    def test_one_sided_bound_and_test(self):
        r=one_proportion([0]*10,alternative='less')
        self.assertAlmostEqual(r['p_value'],1/1024)
        self.assertAlmostEqual(r['ci_high'],1-.05**.1)
        self.assertEqual(one_proportion([1]*10,alternative='greater')['ci_high'],1)

    def test_binary_missing_count_and_fraction(self):
        r=one_proportion([1,0,None,1,float('nan')])
        self.assertEqual((r['count'],r['missing'],r['events']),(3,2,2))
        self.assertAlmostEqual(r['proportion'],2/3)

    def test_binary_invalid_and_empty_samples_rejected(self):
        for sample in ([2,0],[.1,1],[],[None],['1',0],[True,False]):
            with self.assertRaises((ValueError,TypeError)): one_proportion(sample)

    def test_null_endpoints_supported(self):
        self.assertEqual(one_proportion([1],null_proportion=0)['p_value'],0)
        self.assertEqual(one_proportion([1],null_proportion=1)['p_value'],1)
        for p in (-.1,1.1,None,float('nan')):
            with self.assertRaises(ValueError): one_proportion([1],null_proportion=p)

    def test_fisher_exact_known_two_by_two(self):
        r=two_proportions([1]+[0]*9,[1]*11+[0]*3)
        self.assertAlmostEqual(r['fisher_exact_p_value'],.0027594561852200836)
        self.assertAlmostEqual(r['difference'],.1-11/14)
        self.assertLess(r['ci_low'],r['difference']); self.assertLess(r['difference'],r['ci_high'])

    def test_newcombe_zero_samples_not_zero_width(self):
        r=two_proportions([0]*10,[0]*10)
        self.assertEqual(r['difference'],0)
        self.assertEqual(r['fisher_exact_p_value'],1)
        self.assertIsNone(r['z']); self.assertIsNone(r['pooled_z_p_value'])
        self.assertLess(r['ci_low'],0); self.assertGreater(r['ci_high'],0)
        self.assertAlmostEqual(r['ci_low'],-r['ci_high'])
        json.dumps(r,allow_nan=False)

    def test_sample_swap_negates_difference_interval_and_z(self):
        a,b=[1,1,1,0,0,None],[1,0,0,0,None,None]
        r,s=two_proportions(a,b),two_proportions(b,a)
        self.assertAlmostEqual(r['ci_low'],-s['ci_high'])
        self.assertAlmostEqual(r['ci_high'],-s['ci_low'])
        self.assertAlmostEqual(r['z'],-s['z'])
        self.assertAlmostEqual(r['fisher_exact_p_value'],s['fisher_exact_p_value'])
        self.assertEqual([x['missing'] for x in r['samples']],[1,2])

    def test_pooled_z_hand_calculation(self):
        r=two_proportions([1]*60+[0]*40,[1]*40+[0]*60)
        self.assertAlmostEqual(r['z'],.2/math.sqrt(.5*.5*.02))
        self.assertAlmostEqual(r['pooled_z_p_value'],.004677734981047266)


class BasicIntegrationTests(unittest.TestCase):
    def presenter(self):
        p=Presenter(); p.worksheet=Worksheet('Samples',[Column('First',values=[1,0,1,0]),Column('Second',values=[0,0,1,0])])
        return p

    def test_all_new_recipes_can_rerun_and_track_inputs(self):
        p=self.presenter()
        entries=[p.correlation([0,1]),p.one_proportion(0),p.two_proportions(0,1)]
        for entry in entries:
            self.assertFalse(p.result_stale(entry))
            self.assertIn(entry['title'],format_entry(entry))
        p.set_cell(0,0,'0')
        for entry in entries:
            self.assertTrue(p.result_stale(entry))
            rerun=p.rerun_result(entry)
            self.assertFalse(p.result_stale(rerun))
            json.dumps(rerun,allow_nan=False)

    def test_invalid_columns_are_transactional(self):
        p=self.presenter()
        for callback in (lambda:p.correlation([0,0]),lambda:p.two_proportions(0,0),lambda:p.one_proportion(-1),lambda:p.correlation([0,9])):
            with self.assertRaises(ValueError): callback()
        self.assertEqual(p.history,[])

    def test_failed_rerun_does_not_add_result(self):
        p=self.presenter(); entry=p.one_proportion(0); p.set_cell(0,0,'3')
        with self.assertRaises(ValueError): p.rerun_result(entry)
        self.assertEqual(len(p.history),1)

    def test_new_result_recipes_survive_mpx_save_copy(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx'
            write_subgroup_fixture(source); data=source.read_bytes(); p=Presenter(); p.load(source)
            for col in range(2):
                for row,value in enumerate([0,1,1,0,1,0]): p.set_cell(row,col,str(value))
            entries=[p.correlation([0,1],method='Spearman'),p.one_proportion(0),p.two_proportions(0,1)]
            p.save(target); self.assertEqual(source.read_bytes(),data)
            q=Presenter(); q.load(target)
            own=[e for e in q.history if e.get('origin')=='statcraft']
            self.assertEqual([e['recipe'] for e in own],[e['recipe'] for e in entries])
            for entry in own: self.assertFalse(q.result_stale(q.rerun_result(entry)))

    def test_recipe_options_fail_closed(self):
        for action,params in [('correlation',{'indices':[0,1],'method':'eval','missing':'Pairwise','confidence':.95}),
                             ('one_proportion',{'index':0,'null_proportion':.5,'confidence':.95,'alternative':'exec'})]:
            with self.assertRaises(ValueError): columns({'action':action,'parameters':params})
