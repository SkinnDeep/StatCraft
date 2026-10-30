import copy
import json
import math
import unittest
from statistics import NormalDist, stdev

from statcraft.histogram_graphs import build_histograms, validate_parameters, validate_result
from statcraft.model import Column, Worksheet


class GroupedHistogramTests(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(columns=[Column('Response', values=[0, 1, None, 2, 3, 4, 8]),
            Column('Other', values=[10, None, 12, 13, 14, 15, 16]),
            Column('Group', 'text', ['B', 'B', 'A', 'A', 'A', None, 'B'])])

    def test_default_omits_only_response_missing(self):
        result = build_histograms(self.ws, [0])
        group = result['panels'][0]['series'][0]
        self.assertEqual(group['row_indices'], [1, 2, 4, 5, 6, 7])
        self.assertEqual(sum(group['counts']), 6)
        self.assertIs(validate_result(result), result)
        self.assertEqual(json.loads(json.dumps(result))['graph'], 'histogram_graphs')

    def test_groups_share_bins_and_keep_source_identity(self):
        result = build_histograms(self.ws, [0], 'groups', 2, settings={'bins': 2})
        a, b = result['panels'][0]['series']
        self.assertEqual((a['label'], b['label']), ('A', 'B'))
        self.assertEqual(a['edges'], b['edges'])
        self.assertEqual(a['edges'], [0., 4., 8.])
        self.assertEqual(a['counts'], [2, 0])
        self.assertEqual(b['counts'], [2, 1])
        self.assertEqual(a['row_indices'], [4, 5])
        self.assertEqual(b['row_indices'], [1, 2, 7])

    def test_multiple_responses_omit_pairs_independently(self):
        result = build_histograms(self.ws, [0, 1], 'groups', 2)
        self.assertEqual(len(result['panels']), 2)
        self.assertEqual([s['n'] for s in result['panels'][0]['series']], [2, 3])
        self.assertEqual([s['n'] for s in result['panels'][1]['series']], [3, 2])
        self.assertEqual(result['panels'][1]['series'][0]['row_indices'], [3, 4, 5])

    def test_group_percent_density_denominators(self):
        for scale in ('Percent', 'Density'):
            result = build_histograms(self.ws, [0], 'groups', 2, settings={'bins': 2, 'scale': scale})
            for series in result['panels'][0]['series']:
                expected = 100 if scale == 'Percent' else 1
                multiplier = 1 if scale == 'Percent' else 4
                self.assertAlmostEqual(sum(series['counts']) * multiplier, expected)
        result = build_histograms(self.ws, [0], 'groups', 2, settings={'scale':'Percent', 'cumulative':True})
        self.assertEqual([s['counts'][-1] for s in result['panels'][0]['series']], [100, 100])

    def test_fit_uses_each_groups_sample_statistics(self):
        result = build_histograms(self.ws, [0], 'fit_groups', 2, settings={'bins':2})
        a, b = result['panels'][0]['series']
        self.assertEqual(a['fit_parameters']['mean'], 2.5)
        self.assertAlmostEqual(a['fit_parameters']['stdev'], stdev([2,3]))
        self.assertEqual(b['fit_parameters']['n'], 3)
        normal = NormalDist(2.5, stdev([2,3]))
        x, y = a['curves'][0][1][80], a['curves'][0][2][80]
        self.assertAlmostEqual(y, normal.pdf(x) * 2 * 4)
        validate_result(result)

    def test_normal_fit_all_or_nothing_and_never_mutates_source(self):
        ws = Worksheet(columns=[Column('Y', values=[1,2,4,4]), Column('G','text',['A','A','B','B'])])
        original = copy.deepcopy(ws)
        with self.assertRaisesRegex(ValueError, 'positive sample'):
            build_histograms(ws,[0],'fit_groups',1)
        self.assertEqual(ws, original)
        ws.columns[0].values[-1] = None
        with self.assertRaisesRegex(ValueError, 'two observations'):
            build_histograms(ws,[0],'fit_groups',1)

    def test_separate_panels_preserve_shared_edges_and_order(self):
        self.ws.columns[2].metadata['value_order'] = dict(mode='custom', values=['B','A'])
        result = build_histograms(self.ws,[0,1],'groups',2,'panels')
        self.assertEqual(len(result['panels']),4)
        self.assertEqual([p['series'][0]['label'] for p in result['panels']],['B','A','B','A'])
        self.assertEqual(result['panels'][0]['edges'],result['panels'][1]['edges'])
        validate_result(result)

    def test_numeric_groups_sorted_numerically(self):
        ws = Worksheet(columns=[Column('Y',values=[1,2,3]),Column('G',values=[10,2,1])])
        result = build_histograms(ws,[0],'groups',1)
        self.assertEqual([s['label'] for s in result['panels'][0]['series']], ['1','2','10'])

    def test_invalid_parameter_combinations(self):
        cases = [dict(response_indices=[]),dict(response_indices=[True]),dict(response_indices=[0,0]),
                 dict(response_indices=[2]),dict(response_indices=[0],variant='unknown'),
                 dict(response_indices=[0],group_index=2),dict(response_indices=[0],variant='groups'),
                 dict(response_indices=[0],variant='groups',group_index=0),
                 dict(response_indices=[0],layout='stacked'),
                 dict(response_indices=[0],settings={'fit':'Normal'}),
                 dict(response_indices=[0],variant='fit',settings={'fit':None}),
                 dict(response_indices=[0],settings={'cumulative':True,'scale':'Density'})]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_parameters(self.ws,**case)

    def test_empty_groups_constant_and_limits(self):
        ws = Worksheet(columns=[Column('Y',values=[7]*17),Column('G','text',[str(i) for i in range(17)])])
        with self.assertRaisesRegex(ValueError,'16 response/group'):
            build_histograms(ws,[0],'groups',1)
        result=build_histograms(ws,[0])
        self.assertLess(result['panels'][0]['edges'][0],7)
        self.assertGreater(result['panels'][0]['edges'][-1],7)
        ws.columns[1].values=[None]*17
        with self.assertRaisesRegex(ValueError,'nonmissing'):
            build_histograms(ws,[0],'groups',1)

    def test_snapshot_detached_and_json_roundtrip(self):
        result=build_histograms(self.ws,[0],'groups',2)
        self.ws.columns[0].values[0]=999
        self.assertEqual(result['panels'][0]['series'][1]['source'][0],0)
        validate_result(json.loads(json.dumps(result)))

    def test_malformed_saved_data_rejected(self):
        base=build_histograms(self.ws,[0],'fit_groups',2)
        changes=[lambda r:r['panels'][0]['edges'].__setitem__(1,math.inf),
                 lambda r:r['panels'][0]['series'][0]['counts'].__setitem__(0,-1),
                 lambda r:r['panels'][0]['series'][0]['source'].__setitem__(0,math.nan),
                 lambda r:r['panels'][0]['series'][0]['row_indices'].__setitem__(0,True),
                 lambda r:r['panels'][0]['series'][0]['curves'][0][2].__setitem__(0,math.inf),
                 lambda r:r['panels'][0]['series'][0].__setitem__('n',999),
                 lambda r:r['panels'][0].__setitem__('series',[])]
        for change in changes:
            result=copy.deepcopy(base)
            change(result)
            with self.assertRaises(ValueError):validate_result(result)


if __name__=='__main__':unittest.main()
