import unittest
from statcraft.graph_layouts import build_layout, layout_eligible


def graph(index=1):
    return dict(id=str(index), title='Histogram '+str(index), worksheet_name='Sheet 1',
                result={'graph':'histogram','graph_data':[[0,1],[2]]},
                graph_presentation={'title':{'text':'Original'}},
                graph_styles={'color':'blue'}, histogram_settings={'bins':10})


class GraphLayoutTests(unittest.TestCase):
    def test_snapshot_detaches_data_and_all_styles(self):
        entry=graph(); result=build_layout([entry], title='Layout')
        self.assertEqual(result['graphs'][0],entry)
        entry['graph_presentation']['title']['text']='Changed'
        entry['result']['graph_data'][1][0]=99
        entry['histogram_settings']['bins']=5
        self.assertEqual(result['graphs'][0]['graph_presentation']['title']['text'],'Original')
        self.assertEqual(result['graphs'][0]['result']['graph_data'][1],[2])
        self.assertEqual(result['graphs'][0]['histogram_settings']['bins'],10)
        result['graphs'][0]['graph_styles']['color']='red'
        self.assertEqual(entry['graph_styles']['color'],'blue')

    def test_grid_bounds_empty_cells_and_title(self):
        for rows,columns in ((1,1),(9,9)):
            self.assertEqual(build_layout([graph()],rows,columns)['rows'],rows)
        self.assertEqual(build_layout([graph()],9,9,title='x'*145)['title'],'x'*145)
        for params in ({'rows':0},{'columns':10},{'rows':True},{'columns':2.0},{'title':'x'*146}):
            with self.subTest(params=params),self.assertRaises(ValueError):build_layout([graph()],**params)

    def test_capacity_and_sixteen_graph_limit(self):
        for entries,rows,columns in (([],2,2),([graph(1),graph(2)],1,1),([graph(i) for i in range(17)],9,9)):
            with self.assertRaises(ValueError):build_layout(entries,rows,columns)
        self.assertEqual(len(build_layout([graph(i) for i in range(16)],4,4)['graphs']),16)

    def test_duplicates_and_nested_graphs(self):
        entry=graph()
        with self.assertRaises(ValueError):build_layout([entry,entry])
        with self.assertRaises(ValueError):build_layout([entry,graph()])
        for kind in ('graph_layout','panel_graph','panelled'):
            with self.assertRaises(ValueError):build_layout([{'result':{'graph':kind}}])

    def test_ordinary_multi_panel_graph_is_one_layout_source(self):
        entry={'result':{'graph':'expanded','method':'matrixplot','panels':[{'kind':'xy'},{'kind':'xy'}]}}
        self.assertTrue(layout_eligible(entry))
        self.assertEqual(len(build_layout([entry],1,1)['graphs']),1)

    def test_nested_compositions_are_rejected_recursively(self):
        for kind in ('graph_layout','panel_graph','panelled'):
            entry={'result':{'graph':'expanded','panels':[{'child':{'graph':kind}}]}}
            self.assertFalse(layout_eligible(entry))
            with self.assertRaises(ValueError):build_layout([entry])

    def test_quality_graphs_without_graph_marker(self):
        for result in ({'i_center':0},{'xbar_center':0},{'within_stdev':1},{'chart':'P'},
                       {'chart':'U'},{'fitted':[1],'residuals':[0]}):
            self.assertEqual(build_layout([{'result':result}])['graphs'][0]['result'],result)


if __name__=='__main__':unittest.main()
