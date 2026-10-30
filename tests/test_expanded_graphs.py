import json
import math
from statistics import NormalDist
import unittest
from statcraft.expanded_graphs import compute, LABELS, METHODS
from statcraft.model import Column, Worksheet


def sheet():
    return Worksheet('Graph Data',[Column('X',values=[0,1,0,1]),Column('Y',values=[0,0,1,1]),
        Column('Z',values=[1,2,3,4]),Column('Group','text',['A','A','B','B']),
        Column('When','date',[43831,43832,43833,43834])])


class ExpandedGraphTests(unittest.TestCase):
    def test_every_method_finite_snapshot_and_matching_registry(self):
        self.assertEqual(set(METHODS),set(LABELS))
        for method in LABELS:
            meta=METHODS[method]
            indices=[] if method=='distribution_plot' else [0,1,2] if meta['minimum']==3 else [0,2] if meta['minimum']==2 else [2]
            with self.subTest(method=method):
                result=compute(method,sheet(),indices)
                self.assertEqual(result['graph'],'expanded');self.assertEqual(result['method'],method)
                self.assertTrue(result['panels']);json.dumps(result,allow_nan=False)

    def test_binned_scatter_counts_and_bubble_sizes(self):
        p=compute('binned_scatter',sheet(),[0,1],bins=1)['panels'][0]
        self.assertEqual(p['series'][0]['points'],[[.5,.5,4]])
        p=compute('bubble',sheet(),[0,1,2])['panels'][0]
        self.assertEqual(p['series'][0]['points'][2],[0,1,3])
        w=sheet();w.columns[2].values[0]=-1
        with self.assertRaises(ValueError):compute('bubble',w,[0,1,2])

    def test_complete_row_alignment_grouping_and_original_time_axis(self):
        w=sheet();w.columns[0].values[1]=None;w.columns[2].values[2]=None
        p=compute('bubble',w,[0,1,2],group_index=3)['panels'][0]
        self.assertEqual([s['points'] for s in p['series']],[[[0,0,1]],[[1,1,4]]])
        p=compute('time_series',w,[2])['panels'][0]
        self.assertEqual(p['series'][0]['points'],[[1,1],[2,2],[4,4]])
        p=compute('time_series',w,[4,2])['panels'][0]
        self.assertEqual(p['x_label'],'When');self.assertEqual(p['series'][0]['points'],[[43831,1],[43832,2],[43834,4]])
        w.columns[3].values[0]=None
        p=compute('individual_value',w,[2],group_index=3)['panels'][0]
        self.assertEqual([s['points'] for s in p['series']],[[[1,2]],[[2,4]]])

    def test_matrix_correlation_marginals_and_heatmap(self):
        p=compute('matrix_plot',sheet(),[0,2])['panels'];self.assertEqual(len(p),2)
        p=compute('correlogram',sheet(),[0,2])['panels'][0]
        self.assertAlmostEqual(p['values'][0][1],1/math.sqrt(5));self.assertAlmostEqual(p['values'][1][1],1)
        p=compute('marginal',sheet(),[0,2],bins=2)['panels']
        self.assertEqual([sum(x['values']) for x in p[1:]],[4,4])
        p=compute('heatmap',sheet(),[0,2])['panels'][0];self.assertEqual(p['values'],[[0,1],[1,2],[0,3],[1,4]])
        p=compute('parallel_coordinates',sheet(),[0,2])['panels'][0];self.assertEqual(p['rows'][0],[0,1])

    def test_ecdf_dotplot_stem_leaf_probability(self):
        w=Worksheet(columns=[Column('V',values=[1,1,2,None])])
        points=compute('ecdf',w,[0])['panels'][0]['series'][0]['points']
        self.assertEqual(points,[[1,0],[1,2/3],[2,2/3],[2,1]])
        points=compute('dotplot',w,[0])['panels'][0]['series'][0]['points']
        self.assertEqual(points,[[1,1],[1,2],[2,1]])
        p=compute('stem_leaf',w,[0])['panels'][0]
        self.assertAlmostEqual(p['leaf_unit'],.1);self.assertEqual(p['lines'][1:],[ '1 | 0 0','2 | 0'])
        points=compute('probability_plot',w,[0])['panels'][0]['series'][0]['points']
        self.assertAlmostEqual(points[0][0],NormalDist().inv_cdf(.625/3.25));self.assertEqual(points[0][1],1)

    def test_distribution_parameterized_density_and_rejections(self):
        for distribution,parameters in [('Normal',{'mean':2,'stdev':3}),('Uniform',{'lower':2,'upper':6}),('Exponential',{'rate':2})]:
            p=compute('distribution_plot',sheet(),[],distribution=distribution,parameters=parameters)['panels'][0]
            self.assertEqual(len(p['series'][0]['points']),201)
            if distribution=='Uniform':self.assertTrue(all(abs(y-.25)<1e-14 for x,y in p['series'][0]['points']))
        invalid=[('Normal',{'stdev':0}),('Normal',{'oops':1}),('Uniform',{'lower':2,'upper':1}),('Exponential',{'rate':0}),('Unknown',{})]
        for distribution,parameters in invalid:
            with self.subTest(distribution=distribution,parameters=parameters),self.assertRaises(ValueError):
                compute('distribution_plot',sheet(),[],distribution=distribution,parameters=parameters)

    def test_t_interval_known_value_group_sample_size_and_constant_data(self):
        w=Worksheet(columns=[Column('V',values=[1,2,3,4])])
        item=compute('interval_plot',w,[0])['panels'][0]['items'][0]
        self.assertEqual(item['mean'],2.5);self.assertEqual(item['count'],4)
        self.assertAlmostEqual(item['lower'],.445739743239121,places=10)
        self.assertAlmostEqual(item['upper'],4.554260256760879,places=10)
        w.columns[0].values=[2,2];item=compute('interval_plot',w,[0])['panels'][0]['items'][0]
        self.assertEqual(item['lower'],2);self.assertEqual(item['upper'],2)
        with self.assertRaises(ValueError):compute('interval_plot',Worksheet(columns=[Column('X',values=[1])]),[0])

    def test_category_counts_numeric_text_missing_and_blank(self):
        w=Worksheet(columns=[Column('Category','text',['A','',None,'A'])])
        for method in ('bar_chart','pie_chart'):
            p=compute(method,w,[0])['panels'][0];self.assertEqual(p['categories'],['','A']);self.assertEqual(p['values'],[1,2])
        p=compute('bar_chart',sheet(),[0])['panels'][0];self.assertEqual(p['categories'],['0','1']);self.assertEqual(p['values'],[2,2])

    def test_line_area_and_3d_rectangular_grid(self):
        w=sheet()
        for method in ('line_plot','area_graph'):
            series=compute(method,w,[2])['panels'][0]['series'][0]
            self.assertTrue(series['connect']);self.assertEqual(series['points'],[[1,1],[2,2],[3,3],[4,4]])
            self.assertEqual(series['fill'],method=='area_graph')
        for method in ('contour','surface3d'):
            p=compute(method,w,[0,1,2])['panels'][0]
            self.assertEqual(p['x'],[0,1]);self.assertEqual(p['y'],[0,1]);self.assertEqual(p['z'],[[1,2],[3,4]])
            self.assertEqual(p['contour'],method=='contour')
        self.assertEqual(compute('scatter3d',w,[0,1,2])['panels'][0]['points'][0],[0,0,1])
        w.columns[2].values[0]=None
        with self.assertRaises(ValueError):compute('surface3d',w,[0,1,2])
        w=sheet();w.columns[0].values[1]=0
        with self.assertRaises(ValueError):compute('contour',w,[0,1,2])

    def test_limits_invalid_roles_missing_and_extreme_values(self):
        w=sheet()
        cases=[('bubble',[0,1]),('dotplot',[3]),('dotplot',[True]),('dotplot',[-1]),('dotplot',[0,0]),
               ('dotplot',list(range(9))),('time_series',[4]),('distribution_plot',[0])]
        for method,indices in cases:
            with self.subTest(method=method,indices=indices),self.assertRaises(ValueError):compute(method,w,indices)
        for kwargs in ({'bins':0},{'bins':True},{'confidence':1},{'group_index':True},{'group_index':4}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):compute('dotplot',w,[0],**kwargs)
        with self.assertRaises(ValueError):compute('heatmap',w,[0],group_index=3)
        big=Worksheet(columns=[Column('X',values=[1]*5001)])
        with self.assertRaises(ValueError):compute('dotplot',big,[0])
        big=Worksheet(columns=[Column('X',values=[None]*10001)])
        with self.assertRaises(ValueError):compute('dotplot',big,[0])
        for values in ([None,None],[float('inf')],[-1e308,1e308]):
            w=Worksheet(columns=[Column('X',values=[1,2])]);w.columns[0].values=values
            with self.assertRaises(ValueError):compute('interval_plot',w,[0])


if __name__=='__main__':unittest.main()
