from pathlib import Path
import unittest
from statcraft.app import Presenter
from statcraft.expanded_graphs import METHODS,LABELS
from statcraft.graph_catalog import MENU
from statcraft.recipes import columns
from test_expanded_graphs import sheet
from test_mpx import scratch


class ExpandedGraphAppTests(unittest.TestCase):
    def test_menu_inventory_has_working_backend_for_every_choice(self):
        items=[item for item in MENU if item]
        self.assertEqual(len(items),27)
        self.assertEqual({method for title,method in items},set(LABELS)|{'builder','histogram','scatter','boxplot','symmetry_plot'})

    def test_every_expanded_recipe_roundtrips_and_reruns(self):
        p=Presenter();p.worksheet=sheet()
        for method,meta in METHODS.items():
            indices=[] if method=='distribution_plot' else [0,1,2] if meta['minimum']==3 else [0,2] if meta['minimum']==2 else [2]
            p.expanded_graph(method,indices)
        with scratch() as folder:
            path=Path(folder)/'all-graphs.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual(len(q.history),22)
            for entry in list(q.history):
                with self.subTest(method=entry['result']['method']):
                    self.assertFalse(q.result_stale(entry));self.assertEqual(q.rerun_result(entry)['result'],entry['result'])

    def test_grouped_dependencies_and_distribution_parameter_validation(self):
        p=Presenter();p.worksheet=sheet();entry=p.expanded_graph('individual_value',[2],3)
        self.assertEqual(columns(entry['recipe']),[2,3]);p.set_cell(0,3,'Changed');self.assertTrue(p.result_stale(entry))
        p.undo();self.assertFalse(p.result_stale(entry))
        entry=p.expanded_graph('distribution_plot',[],distribution='Exponential',parameters={'rate':2})
        self.assertEqual(columns(entry['recipe']),[])
        self.assertEqual(p.rerun_result(entry)['result'],entry['result'])
        bad={'action':'expanded_graph','parameters':{**entry['recipe']['parameters'],'parameters':{'rate':float('nan')}}}
        with self.assertRaises(ValueError):columns(bad)
