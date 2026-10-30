import copy
import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.recipes import run
from statcraft import session,io


def document():
    p=Presenter();p.worksheet=Worksheet('Data',[Column('Strength',values=[1,2,3,4,5,6])])
    entry=run(p,{'action':'graph','parameters':{'method':'histogram','indices':[0],'bins':3}})
    return p,entry


class GraphAppearanceTests(unittest.TestCase):
    def test_style_and_histogram_options_leave_results_and_recipe_unchanged(self):
        p,entry=document();before=copy.deepcopy(entry['result']);recipe=copy.deepcopy(entry['recipe'])
        p.update_graph_styles(entry,{'p0:bars':{'fill':'#0088aa','opacity':.5}})
        p.update_histogram_settings(entry,{'bins':6,'scale':'Percent','fit':'Normal'})
        self.assertEqual(entry['result'],before);self.assertEqual(entry['recipe'],recipe)
        self.assertEqual(entry['result']['histogram_source'],[1,2,3,4,5,6])

    def test_style_and_histogram_undo_redo_together(self):
        p,entry=document();p.update_graph_styles(entry,{'p0:bars':{'fill':'#0088aa'}})
        p.update_histogram_settings(entry,{'bins':5})
        p.undo();self.assertNotIn('histogram_settings',entry)
        p.undo();self.assertNotIn('graph_styles',entry)
        p.redo();self.assertEqual(entry['graph_styles']['p0:bars']['fill'],'#0088aa')
        p.redo();self.assertEqual(entry['histogram_settings']['bins'],5)

    def test_annotation_edits_are_undoable(self):
        p,entry=document();p.update_graph_presentation(entry,{'title':'Edited'})
        p.undo();self.assertNotIn('graph_presentation',entry)
        p.redo();self.assertEqual(entry['graph_presentation']['title'],'Edited')

    def test_invalid_edits_are_atomic(self):
        p,entry=document();before=copy.deepcopy(entry)
        for operation in (lambda:p.update_graph_styles(entry,{'p0:s0':{'color':'bad'}}),
            lambda:p.update_histogram_settings(entry,{'bins':1}),
            lambda:p.update_histogram_settings(entry,{'scale':'Density','cumulative':True})):
            with self.assertRaises(ValueError):operation()
            self.assertEqual(entry,before);self.assertFalse(p.can_undo)
        with self.assertRaises(ValueError):p.update_graph_styles(copy.deepcopy(entry),{})

    def test_legacy_histogram_does_not_invent_source(self):
        p,entry=document();entry['result'].pop('histogram_source')
        with self.assertRaises(ValueError):p.update_histogram_settings(entry,{'bins':4,'fit':'Normal'})
        self.assertNotIn('histogram_settings',entry)
        renewed=p.rerun_result(entry);self.assertEqual(renewed['result']['histogram_source'],[1,2,3,4,5,6])

    def test_mpx_reopen_and_rerun_keep_appearance(self):
        p,entry=document();p.update_graph_styles(entry,{'p0:bars':{'fill':'#0088aa'},'p0:fit0':{'line_style':'dash'}})
        p.update_histogram_settings(entry,{'bins':5,'scale':'Density','fit':'Normal'})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'appearance.mpx';p.save(path);q=Presenter();q.load(path)
            saved=next(e for e in q.history if 'histogram_settings' in e);rerun=q.rerun_result(saved)
            self.assertEqual(saved['graph_styles'],entry['graph_styles']);self.assertEqual(rerun['graph_styles'],entry['graph_styles'])
            self.assertEqual(rerun['histogram_settings'],entry['histogram_settings'])

    def test_invalid_normal_refit_does_not_leave_partial_result(self):
        p,entry=document();p.update_histogram_settings(entry,{'fit':'Normal'})
        for row in range(6):p.set_cell(row,0,'5')
        before=list(p.history)
        with self.assertRaises(ValueError):p.rerun_result(entry)
        self.assertEqual(p.history,before)

    def test_invalid_persisted_appearance_rejected(self):
        p,entry=document();entry['worksheet_id']='sheet'
        entry['graph_styles']={'p0:s0':{'marker_size':float('inf')}}
        with self.assertRaises(io.FormatError):session.validate([entry],['sheet'])
        entry.pop('graph_styles');entry['histogram_settings']={'bins':1}
        with self.assertRaises(io.FormatError):session.validate([entry],['sheet'])


if __name__=='__main__':unittest.main()
