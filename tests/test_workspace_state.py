import copy,json,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile
from statcraft import workspace_state as ws,io
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.mpx import load_mpx,save_mpx
from test_mpx import fixture


def state():
    s=ws.empty();s.update(open_ids=['result-a',ws.REPORT],active=ws.REPORT,closed_ids=['result-b'],report_pad='Conclusion\nMean = 12.5\nΩ <literal>')
    s['views']={'result-a':{'view':'Graph','zoom':{'Graph':150},'scroll':{'Graph':[120,90]},'editor':True}}
    return s


class WorkspaceTests(unittest.TestCase):
    def test_roundtrip_detaches_views_and_literal_report_text(self):
        s=state();saved=ws.decode(ws.encode(s));self.assertEqual(saved,s)
        saved['views']['result-a']['zoom']['Graph']=50;self.assertEqual(s['views']['result-a']['zoom']['Graph'],150)

    def test_prune_removes_deleted_results_without_losing_report(self):
        saved=ws.prune(state(),[])
        self.assertEqual(saved['open_ids'],[ws.REPORT]);self.assertFalse(saved['views']);self.assertFalse(saved['closed_ids'])
        self.assertEqual(saved['active'],ws.REPORT);self.assertIn('Mean = 12.5',saved['report_pad'])

    def test_invalid_keys_id_duplicates_and_inactive_selection_rejected(self):
        for mutate in [lambda s:s.update(extra=True),lambda s:s['open_ids'].append('result-a'),lambda s:s.update(active='missing')]:
            s=state();mutate(s)
            with self.assertRaises(io.FormatError):ws.validate(s)

    def test_invalid_view_zoom_scroll_and_boolean_types_rejected(self):
        for field,value in [('view','__import__'),('zoom',{'Graph':True}),('zoom',{'Graph':501}),('scroll',{'Graph':[-1,0]}),('editor','yes')]:
            s=state();s['views']['result-a'][field]=value
            with self.assertRaises(io.FormatError):ws.validate(s)

    def test_limits_and_unsupported_schema_rejected(self):
        s=state();s['report_pad']='x'*1000001
        with self.assertRaises(io.FormatError):ws.encode(s)
        with self.assertRaises(io.FormatError):ws.decode(b'{"schema":"other","version":1,"workspace":{}}')

    def test_owned_mpx_workspace_and_report_survive_repeated_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Presenter();p.worksheet=Worksheet('Measurements',[Column('Strength',values=[1,2,3])]);p.describe_columns([0]);p.workspace=state()
            path=Path(folder)/'workspace.mpx';p.save(path);loaded=Presenter();loaded.load(path)
            self.assertTrue(loaded.native_project.statcraft_owned);self.assertEqual(loaded.workspace,p.workspace)
            loaded.workspace['report_pad']+='\nEdited';loaded.save(path)
            loaded.load(path);self.assertTrue(loaded.workspace['report_pad'].endswith('Edited'))

    def test_imported_mpx_adds_only_workspace_and_leaves_native_members_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'native.mpx';destination=Path(folder)/'copy.mpx';fixture(source)
            original=source.read_bytes();project=load_mpx(source);project.workspace=state();save_mpx(project,destination)
            self.assertEqual(source.read_bytes(),original)
            with ZipFile(source) as a,ZipFile(destination) as b:
                for name in a.namelist():self.assertEqual(a.read(name),b.read(name),name)
                self.assertEqual(set(b.namelist())-set(a.namelist()),{ws.MEMBER})
            reopened=load_mpx(destination);self.assertEqual(reopened.workspace,state())
            exact=Path(folder)/'exact.mpx';save_mpx(reopened,exact);self.assertEqual(exact.read_bytes(),destination.read_bytes())

    def test_no_workspace_retains_untouched_native_byte_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'native.mpx';copy_path=Path(folder)/'copy.mpx';fixture(source)
            p=load_mpx(source);self.assertIsNone(p.workspace);save_mpx(p,copy_path)
            self.assertEqual(source.read_bytes(),copy_path.read_bytes())

    def test_statcraft_worksheet_preserves_report_pad(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Presenter();p.workspace=state();path=Path(folder)/'notes.statcraft';p.save(path)
            loaded=Presenter();loaded.load(path);self.assertEqual(loaded.workspace['report_pad'],p.workspace['report_pad'])
