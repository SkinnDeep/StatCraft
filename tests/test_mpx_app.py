import tempfile
import unittest
from pathlib import Path
from statcraft._mpx_fixture import write_fixture
from statcraft.app import Presenter
from statcraft.io import UnsupportedFormatError
from statcraft.mpx import load_mpx


class MpxWorkflowTests(unittest.TestCase):
    def test_open_select_analyze_edit_save_copy_keeps_all_sheets(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            original, copy = Path(folder)/'original.mpx', Path(folder)/'copy.mpx'
            write_fixture(original)
            original_bytes = original.read_bytes()
            p = Presenter()
            p.load(original)
            self.assertEqual([s.name for s in p.native_project.worksheets], ['Second', 'First'])
            self.assertEqual(p.worksheet.name, 'First')
            self.assertEqual(p.describe_column(0)['result']['mean'], 2)
            p.set_cell(0, 0, '7')
            p.select_worksheet(0)
            self.assertEqual(p.worksheet.columns[0].values, [2,3,4])
            p.save(copy)
            loaded = load_mpx(copy)
            self.assertEqual(loaded.active_index, 0)
            self.assertEqual(loaded.worksheets[1].columns[0].values, [7,2,3])
            self.assertEqual(loaded.retained_members['/unknown/retained.bin'], b'Original synthetic opaque payload\x00\xff')
            self.assertEqual(original.read_bytes(), original_bytes)
            self.assertFalse(p.dirty)

    def test_save_failure_keeps_dirty_and_original(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            original = Path(folder)/'original.mpx'
            write_fixture(original)
            p = Presenter(); p.load(original); p.set_cell(0,0,'8')
            with self.assertRaises(UnsupportedFormatError): p.save(original)
            self.assertTrue(p.dirty)
            with self.assertRaises(UnsupportedFormatError): p.save(Path(folder)/'wrong.statcraft')
            self.assertTrue(p.dirty)

    def test_bad_project_open_preserves_current_document(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            bad = Path(folder)/'bad.mpx'; bad.write_bytes(b'not a project')
            p = Presenter(); p.set_cell(0,0,'10'); current=p.worksheet
            with self.assertRaises(ValueError): p.load(bad)
            self.assertIs(p.worksheet,current)
            self.assertTrue(p.dirty)
