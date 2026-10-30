import copy,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.recipes import columns
from statcraft.compositions import validate_composition


def document():
    p=Presenter();p.worksheet=Worksheet('Groups',[Column('Strength',values=[1,2,3,4,7,9]),
        Column('Other',values=[2,4,6,8,10,12]),Column('Batch','text',['A','A','A','B','B','B'])])
    return p


class HistogramWorkflowTests(unittest.TestCase):
    def test_recipe_column_identity_mpx_and_rerun(self):
        p=document();entry=p.histogram_graphs([0,1],'fit_groups',2,settings={'bins':4,'scale':'Percent'})
        self.assertEqual(columns(entry['recipe']),[0,1,2]);original=copy.deepcopy(entry['result'])
        p.insert_columns(0);self.assertEqual(entry['recipe']['parameters']['response_indices'],[1,2])
        self.assertFalse(p.result_stale(entry));self.assertEqual([panel['series'] for panel in p.rerun_result(entry)['result']['panels']],[panel['series'] for panel in original['panels']])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'groups.mpx';p.save(path);q=Presenter();q.load(path)
            saved=q.history[0];self.assertFalse(q.result_stale(saved));self.assertEqual(len(q.rerun_result(saved)['result']['panels']),2)
            q.delete_columns([1]);self.assertTrue(q.result_stale(saved))
            with self.assertRaisesRegex(ValueError,'deleted'):q.rerun_result(saved)

    def test_failure_does_not_record_partial_graphs(self):
        p=document();p.worksheet.columns[0].values=[1,2,3,4,4,4]
        history=list(p.history);before=copy.deepcopy(p.worksheet)
        with self.assertRaises(ValueError):p.histogram_graphs([1,0],'fit_groups',2)
        self.assertEqual(p.history,history);self.assertEqual(p.worksheet,before)

    def test_layout_detaches_histogram_groups_and_styles(self):
        p=document();entry=p.histogram_graphs([0],'groups',2)
        p.update_graph_styles(entry,{'p0:s1':{'fill':'#d000a4'}})
        layout=p.graph_layout([entry],1,2);validate_composition(layout['result'])
        p.update_graph_styles(entry,{'p0:s1':{'fill':'#000000'}})
        self.assertEqual(layout['result']['graphs'][0]['graph_styles']['p0:s1']['fill'],'#d000a4')

    def test_group_color_identity_survives_separate_panels(self):
        p=document();entry=p.histogram_graphs([0],'groups',2,layout='panels')
        self.assertEqual([panel['series'][0]['color_index'] for panel in entry['result']['panels']],[0,1])


if __name__=='__main__':unittest.main()
