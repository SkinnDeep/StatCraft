"""DOE planner orchestration, project transactions and source-preserving saved data."""
import copy
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.app import Presenter,format_entry
from statcraft.model import Worksheet,Column
from statcraft.doe_planner import build_plan

class DOEPlannerWorkflows(unittest.TestCase):
    def test_preserves_existing_project_and_unique_tabs_through_mpx(self):
        p=Presenter();p.worksheet=Worksheet('Original',[Column('Data',values=[1,2,3])]);old=p.describe_column(0)
        factors=[dict(name='A',low=-1,high=1),dict(name='B',low=2,high=4)]
        a=p.create_doe_plan(kind='full_factorial',factors=factors,name='Plan')
        b=p.create_doe_plan(kind='full_factorial',factors=factors,name='Plan')
        self.assertEqual([s.name for s in p.native_project.worksheets],['Original','Plan','Plan (2)'])
        self.assertEqual(p.rerun_result(old)['result']['count'],3)
        self.assertIn('Factorial',format_entry(a))
        with scratch() as temp:
            expected=[list(s.columns[0].values) for s in p.native_project.worksheets]
            path=Path(temp)/'plans.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual([s.columns[0].values for s in q.native_project.worksheets],expected)
            self.assertEqual(q.native_project.worksheets[1].metadata['doe']['planner_configuration']['kind'],'full_factorial')

    def test_invalid_design_does_not_reset_dirty_project_or_history(self):
        p=Presenter();p.worksheet.columns[0].values=[7,8];p.describe_column(0)
        before=(copy.deepcopy(p.worksheet),copy.deepcopy(p.history),p.dirty)
        with self.assertRaises(ValueError):p.create_doe_plan(kind='simplex_centroid',factors=[dict(name='A',low=.9,high=1),dict(name='B',low=.8,high=1)])
        self.assertEqual((p.worksheet,p.history,p.dirty),before)
        self.assertIsNone(p.native_project)

    def test_response_surface_centers_count_actual_replicates(self):
        p=Presenter();entry=p.create_doe_plan(kind='central_composite',factors=[dict(name='A',low=-1,high=1),dict(name='B',low=-1,high=1)],centers=2,replicates=3)
        self.assertEqual(entry['result']['center_runs'],6)
        self.assertEqual(sum(v==0 for v in p.worksheet.columns[2].values),6)

    def test_configuration_copied_and_block_restrictions_explicit(self):
        parameters=dict(kind='general_factorial',factors=[dict(name='A',kind='number',levels=[0,1,2]),dict(name='B',kind='text',levels=['X','Y'])])
        sheet=build_plan(**parameters);parameters['factors'][0]['levels'][0]=999
        self.assertEqual(sheet.metadata['doe']['planner_configuration']['factors'][0]['levels'][0],0)
        with self.assertRaises(ValueError):build_plan(**parameters,replicates=1,blocks=2)
