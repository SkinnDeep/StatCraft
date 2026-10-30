import copy
import json
from pathlib import Path
import unittest
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft.graph_presentation import graph_presentation
from statcraft.recipes import run
from statcraft import session
from test_mpx import scratch


class GraphPresentationAppTests(unittest.TestCase):
    def make_graph(self):
        p=Presenter();p.worksheet=Worksheet('Measurements',[Column('Strength (N)',values=[552,560,565,568,571,579,590])])
        return p,run(p,{'action':'graph','parameters':{'method':'histogram','indices':[0],'bins':4}})

    def test_annotation_changes_are_separate_from_result_and_recipe(self):
        p,entry=self.make_graph();before=copy.deepcopy(entry)
        settings=graph_presentation(entry);settings.update(title='Edited strength',subtitle='Normal',subtitle_enabled=True,footnote='Checked',footnote_enabled=True,x_position='high')
        p._results_dirty=False;p.update_graph_presentation(entry,settings)
        self.assertEqual(entry['result'],before['result']);self.assertEqual(entry['recipe'],before['recipe'])
        self.assertFalse(p.result_stale(entry));self.assertTrue(p.dirty)
        settings['title']='Detached';self.assertEqual(entry['graph_presentation']['title'],'Edited strength')

    def test_annotations_survive_mpx_reopen_and_rerun(self):
        p,entry=self.make_graph();settings=graph_presentation(entry)
        settings.update(title_enabled=False,subtitle='Normal',subtitle_enabled=True,x_label='Force',x_position='high',x_min=500,x_max=650,grid_enabled=False)
        p.update_graph_presentation(entry,settings)
        with scratch() as folder:
            path=Path(folder)/'edited.mpx';p.save(path);q=Presenter();q.load(path)
            reopened=q.history[0];self.assertEqual(reopened['graph_presentation'],settings)
            self.assertEqual(q.rerun_result(reopened)['graph_presentation'],settings)
            self.assertEqual(q.history[0]['result'],json.loads(json.dumps(entry['result'])))

    def test_invalid_edits_leave_last_valid_presentation(self):
        p,entry=self.make_graph();settings=graph_presentation(entry);p.update_graph_presentation(entry,settings)
        for patch in ({'x_min':4},{'x_min':5,'x_max':2},{'title':'x'*146},{'grid_enabled':'yes'}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):p.update_graph_presentation(entry,{**settings,**patch})
            self.assertEqual(entry['graph_presentation'],settings)
        with self.assertRaises(ValueError):p.update_graph_presentation(copy.deepcopy(entry),settings)

    def test_invalid_saved_presentation_is_rejected(self):
        p,entry=self.make_graph();entry['worksheet_id']='worksheet'
        entry['graph_presentation']={'x_min':5,'x_max':2}
        with self.assertRaises(ValueError):session.validate([entry],['worksheet'])
