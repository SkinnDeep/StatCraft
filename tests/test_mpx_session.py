import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from statcraft.app import Presenter
from statcraft._mpx_fixture import write_fixture
from statcraft.mpx import load_mpx, save_mpx
from statcraft.session import MEMBER, decode
from statcraft.io import FormatError, UnsupportedFormatError


class MpxSessionTests(unittest.TestCase):
    def scratch(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def test_analysis_save_reopen_and_all_native_bytes_preserved(self):
        with self.scratch() as folder:
            original, target = Path(folder)/'original.mpx', Path(folder)/'copy.mpx'
            write_fixture(original)
            p = Presenter(); p.load(original)
            entry = p.describe_column(0)
            self.assertTrue(p.dirty)
            p.save(target)
            self.assertFalse(p.dirty)
            with zipfile.ZipFile(original) as a, zipfile.ZipFile(target) as b:
                for name in a.namelist(): self.assertEqual(a.read(name), b.read(name))
                self.assertIn(MEMBER, b.namelist())
            reopened = Presenter(); reopened.load(target)
            self.assertFalse(reopened.dirty)
            own = [e for e in reopened.history if e['origin'] == 'statcraft']
            self.assertEqual(own, [entry])
            self.assertEqual(own[0]['result']['mean'], 2)
            self.assertEqual(own[0]['worksheet_id'], p.native_project.worksheet_ids[1])
            # Loaded analysis is an inert snapshot, not re-run against later data.
            reopened.set_cell(0, 0, '100')
            self.assertEqual(own[0]['result']['mean'], 2)
            untouched = Path(folder)/'untouched.mpx'
            save_mpx(load_mpx(target), untouched)
            self.assertEqual(untouched.read_bytes(), target.read_bytes())

    def test_two_worksheets_and_repeated_save_do_not_duplicate_history(self):
        with self.scratch() as folder:
            original, target = Path(folder)/'original.mpx', Path(folder)/'copy.mpx'
            write_fixture(original)
            p = Presenter(); p.load(original); p.describe_column(0)
            p.select_worksheet(0); p.describe_column(0); p.save(target); p.save(target)
            q = Presenter(); q.load(target)
            own = [e for e in q.history if e['origin'] == 'statcraft']
            self.assertEqual([e['result']['mean'] for e in own], [2, 3])
            self.assertEqual(len({e['worksheet_id'] for e in own}), 2)

    def test_undo_does_not_hide_unsaved_analysis_and_failed_save_is_atomic(self):
        with self.scratch() as folder:
            original, target = Path(folder)/'original.mpx', Path(folder)/'copy.mpx'
            write_fixture(original)
            p = Presenter(); p.load(original); p.set_cell(0,0,'9'); p.describe_column(0)
            p.undo(); self.assertTrue(p.dirty)
            target.write_bytes(b'existing destination')
            with patch('statcraft.mpx.os.replace', side_effect=OSError('Publication failed')):
                with self.assertRaises(OSError): p.save(target)
            self.assertTrue(p.dirty)
            self.assertEqual(target.read_bytes(), b'existing destination')
            self.assertFalse(list(Path(folder).glob('.statcraft-mpx-*')))

    def test_graph_payload_snapshot_and_no_execution_of_saved_commands(self):
        with self.scratch() as folder:
            original, target = Path(folder)/'original.mpx', Path(folder)/'copy.mpx'
            write_fixture(original)
            p = Presenter(); p.load(original)
            data = [[0, 1, 2], [2, 3]]
            p._record('Histogram', {'graph':'histogram','graph_data':data})
            data[1][0] = 99
            p._record('Text', {'command':'arbitrary text is never executed'})
            p.save(target)
            with patch.object(Presenter, 'describe_column', side_effect=AssertionError('Must not execute')):
                q = Presenter(); q.load(target)
            own = [e for e in q.history if e['origin'] == 'statcraft']
            self.assertEqual(own[0]['result']['graph_data'], [[0,1,2],[2,3]])
            self.assertEqual(own[1]['result']['command'], 'arbitrary text is never executed')

    def test_invalid_extension_is_rejected_without_replacing_document(self):
        with self.scratch() as folder:
            path = Path(folder)/'bad.mpx'; write_fixture(path)
            with zipfile.ZipFile(path,'a') as archive:
                archive.writestr(MEMBER, json.dumps({'schema':'statcraft-session','version':2,'results':[]}))
            p = Presenter(); p.set_cell(0,0,'7'); current=p.worksheet
            with self.assertRaises(UnsupportedFormatError): p.load(path)
            self.assertIs(p.worksheet, current)
            self.assertTrue(p.dirty)
            with self.assertRaises(FormatError): decode(b'{"schema":"statcraft-session","version":1,"results":[{}]}', ['a'])

    def test_project_switch_clears_saved_result_history(self):
        with self.scratch() as folder:
            original = Path(folder)/'original.mpx'; write_fixture(original)
            p=Presenter(); p.load(original); p.describe_column(0)
            p.load(original)
            self.assertFalse(any(e['origin']=='statcraft' for e in p.history))
            self.assertFalse(p.dirty)
            p.describe_column(0); p.new()
            self.assertEqual(p.history, [])
            self.assertFalse(p.dirty)
