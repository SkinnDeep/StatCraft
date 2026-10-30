import json
import math
import unittest

from statcraft.histograms import compute
from statcraft.model import Column, Worksheet


class HistogramTests(unittest.TestCase):
    def sheet(self):
        return Worksheet('Data',[Column('Y',values=[0,1,2,3,4]),Column('Z',values=[10,11,12,13,14]),
                                 Column('Batch',kind='text',values=['A','A','B',None,''])])

    def test_equal_width_counts_and_inclusive_last_edge(self):
        result=compute(self.sheet(),[0],bins=2)
        series=result['panels'][0]['series'][0]
        self.assertEqual(series['edges'],[0,2,4])
        self.assertEqual(series['counts'],[2,3])
        self.assertEqual(series['curve_x'],[])
        self.assertFalse(result['fit_normal'])
        self.assertEqual(result['graph'],'histogram_configurable')

    def test_group_alignment_omits_missing_preserves_empty_label(self):
        result=compute(self.sheet(),[0],group_index=2,bins=2)
        self.assertEqual(result['count'],4)
        self.assertEqual(result['omitted_missing_group'],1)
        items=[p['series'][0] for p in result['panels']]
        self.assertEqual([s['count'] for s in items],[2,1,1])
        self.assertEqual([s['mean'] for s in items],[0.5,2,4])
        self.assertTrue(items[-1]['label'].endswith('= ""'))

    def test_overlay_shares_bins_and_one_panel(self):
        result=compute(self.sheet(),[0,1],bins=2,display='Overlay')
        self.assertEqual(len(result['panels']),1)
        items=result['panels'][0]['series']
        self.assertEqual(items[0]['edges'],items[1]['edges'])
        self.assertEqual(items[0]['counts'],[5,0])
        self.assertEqual(items[1]['counts'],[0,5])

    def test_separate_x_bounds_are_independent_unless_requested(self):
        first=compute(self.sheet(),[0,1],bins=2)
        shared=compute(self.sheet(),[0,1],bins=2,same_x=True)
        self.assertNotEqual(first['panels'][0]['x_bounds'],first['panels'][1]['x_bounds'])
        self.assertEqual(shared['panels'][0]['x_bounds'],shared['panels'][1]['x_bounds'])
        self.assertEqual(shared['panels'][0]['series'][0]['edges'],shared['panels'][1]['series'][0]['edges'])

    def test_shared_y_scale_and_transposed_area_only(self):
        result=compute(self.sheet(),[0],group_index=2,bins=2,same_y=True,bars=False,area=True,transpose=True)
        self.assertEqual(len({p['y_max'] for p in result['panels']}),1)
        self.assertTrue(all(p['transpose'] and p['area'] and not p['bars'] for p in result['panels']))

    def test_normal_curve_uses_sample_sd_and_frequency_scaling(self):
        sheet=Worksheet('Data',[Column('Y',values=[-1,0,1])])
        result=compute(sheet,[0],bins=2,fit_normal=True,bars=False)
        series=result['panels'][0]['series'][0]
        self.assertEqual(series['mean'],0)
        self.assertEqual(series['stdev'],1)
        self.assertEqual(len(series['curve_x']),201)
        self.assertAlmostEqual(series['curve_x'][100],0)
        self.assertAlmostEqual(series['curve_y'][100],3/math.sqrt(2*math.pi))
        json.dumps(result,allow_nan=False)

    def test_dates_and_numeric_groups(self):
        sheet=Worksheet('Data',[Column('When',kind='date',values=[45000,45001,45002]),
                                Column('Group',values=[1,1,2])])
        result=compute(sheet,[0],group_index=1,bins=1)
        self.assertEqual([p['series'][0]['count'] for p in result['panels']],[2,1])

    def test_single_constant_series_has_finite_bins_without_fit(self):
        for value in (0,5,1e308,-1e308):
            result=compute(Worksheet('Data',[Column('Y',values=[value,value])]),[0],bins=5)
            self.assertEqual(sum(result['panels'][0]['series'][0]['counts']),2)
            json.dumps(result,allow_nan=False)
        with self.assertRaises(ValueError): compute(Worksheet('Data',[Column('Y',values=[1,1])]),[0],fit_normal=True)

    def test_invalid_options_and_indices(self):
        for options in ({'indices':[]},{'indices':[0,0]},{'indices':[True]},{'indices':[3]},
                        {'indices':[2]},{'indices':[0],'bins':0},{'indices':[0],'bins':201},
                        {'indices':[0],'bins':True},{'indices':[0],'display':'Other'},
                        {'indices':[0],'bars':False},{'indices':[0],'area':1},
                        {'indices':[0],'group_index':0},{'indices':[0],'group_index':False}):
            with self.subTest(options=options), self.assertRaises(ValueError): compute(self.sheet(),**options)

    def test_input_bounds(self):
        wide=Worksheet('Data',[Column(str(i),values=[i]) for i in range(9)])
        with self.assertRaises(ValueError): compute(wide,list(range(9)))
        many=Worksheet('Data',[Column('Y',values=list(range(5001)))])
        with self.assertRaises(ValueError): compute(many,[0])
        source=Worksheet('Data',[Column('Y',values=[None]*10001)])
        with self.assertRaises(ValueError): compute(source,[0])
        groups=Worksheet('Data',[Column('Y',values=list(range(21))),Column('G',values=list(range(21)))])
        with self.assertRaises(ValueError): compute(groups,[0],group_index=1)

    def test_missing_data_and_short_group_column(self):
        sheet=Worksheet('Data',[Column('Y',values=[1,None,3,4]),Column('G',kind='text',values=['A','B','B'])])
        result=compute(sheet,[0],group_index=1,bins=2)
        self.assertEqual(result['count'],2)
        self.assertEqual(result['omitted_missing_group'],1)
        with self.assertRaises(ValueError): compute(Worksheet('Data',[Column('Y',values=[None])]),[0])

    def test_extreme_span_and_unrepresentable_narrow_bins_rejected(self):
        for values in ([-1e308,1e308],[1e308,math.nextafter(1e308,math.inf)]):
            with self.assertRaises(ValueError): compute(Worksheet('Data',[Column('Y',values=values)]),[0],bins=200)
        safe=compute(Worksheet('Data',[Column('Y',values=[1e300,1.1e300,1.2e300])]),[0],bins=2,fit_normal=True)
        json.dumps(safe,allow_nan=False)


if __name__=='__main__': unittest.main()
