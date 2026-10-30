"""Multiple-process capability source identity and transactional persistence."""
import copy
import math
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.app import Presenter,format_entry
from statcraft.model import Worksheet,Column
from statcraft.recipes import columns
from statcraft.modern_charts import supported


def presenter():
    p=Presenter()
    p.worksheet=Worksheet('Production',[
        Column('Length',values=[10+math.sin(i*.7)*.8+i*.001 for i in range(48)]),
        Column('Weight',values=[20+math.cos(i*.6)*1.2+i*.002 for i in range(48)]),
        Column('Machine','text',['A']*24+['B']*24),
        Column('Subgroups','text',[str(i//3) for i in range(48)])])
    return p

class MultipleCapabilityWorkflows(unittest.TestCase):
    def test_independent_columns_move_rename_mpx_and_rerun_both_methods(self):
        for method in ('normal','nonnormal'):
            with self.subTest(method=method),scratch() as tmp:
                p=presenter()
                entry=p.multiple_capability(method,[0,1],subgroup_sizes=[2,3] if method=='normal' else 1,
                    lower_specs=[7,16],upper_specs=[13,24],targets=[10,20],distribution='lognormal')
                expected=[s['result']['observations'] for s in entry['result']['series']]
                self.assertEqual(columns(entry['recipe']),[0,1])
                p.insert_columns(0)
                p.move_columns([2],'before_c1')
                p.rename_column(0,'Weight renamed');p.rename_column(2,'Length renamed')
                rerun=p.rerun_result(entry)
                self.assertEqual([s['result']['observations'] for s in rerun['result']['series']],expected)
                self.assertIn('renamed',format_entry(rerun))
                target=Path(tmp)/'multiple.mpx';p.save(target)
                q=Presenter();q.load(target)
                for saved in list(q.history):
                    self.assertEqual([s['result']['observations'] for s in q.rerun_result(saved)['result']['series']],expected)

    def test_group_and_subgroup_sources_follow_columns_then_delete_undo(self):
        p=presenter()
        entry=p.multiple_capability('normal',[0],by_indices=[2],subgroup_indices=[3],
                                    lower_specs=7,upper_specs=13)
        self.assertEqual(columns(entry['recipe']),[0,2,3])
        expected=[s['result']['observations'] for s in entry['result']['series']]
        p.move_columns([3],'before_c1')
        self.assertEqual(columns(entry['recipe']),[0,1,3])
        self.assertEqual([s['result']['observations'] for s in p.rerun_result(entry)['result']['series']],expected)
        p.delete_columns([0])
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(entry)
        p.undo()
        self.assertEqual([s['result']['observations'] for s in p.rerun_result(entry)['result']['series']],expected)

    def test_failed_group_analysis_does_not_record_partial_outputs(self):
        p=presenter();p.worksheet.columns[2].values=['A']*47+['B']
        before=list(p.history)
        with self.assertRaises(ValueError):p.multiple_capability('normal',[0],by_indices=[2],lower_specs=7,upper_specs=13)
        self.assertEqual(p.history,before)

    def test_recipe_rejects_boolean_fractional_duplicate_and_overlapping_sources(self):
        p=presenter();entry=p.multiple_capability('normal',[0,1],lower_specs=[7,16],upper_specs=[13,24])
        for references in ([True],[.5],[0,0],[-1]):
            r=copy.deepcopy(entry['recipe']);r['parameters']['variable_indices']=references
            with self.subTest(references=references),self.assertRaises(ValueError):columns(r)
        r=copy.deepcopy(entry['recipe']);r['parameters']['variable_indices']=[0];r['parameters']['by_indices']=[0]
        with self.assertRaises(ValueError):columns(r)

    def test_graph_suppression_is_preserved_on_rerun(self):
        p=presenter();entry=p.multiple_capability('normal',[0,1],lower_specs=[7,16],upper_specs=[13,24],options={'show_graphs':False})
        self.assertFalse(supported(entry))
        self.assertFalse(supported(p.rerun_result(entry)))
