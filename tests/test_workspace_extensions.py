import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter, format_entry, chart_segments
from statcraft.model import Column, Worksheet
from statcraft._mpx_fixture import write_fixture


class WorkspaceExtensions(unittest.TestCase):
    def test_undo_redo_and_saved_revision(self):
        p=Presenter(); p.set_cell(0,0,'1'); p.set_cell(0,0,'2')
        self.assertTrue(p.undo()); self.assertEqual(p.worksheet.columns[0].values,[1])
        self.assertTrue(p.redo()); self.assertEqual(p.worksheet.columns[0].values,[2])
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            p.save(Path(folder)/'data.statcraft')
            self.assertFalse(p.dirty)
            p.undo(); self.assertTrue(p.dirty)
            p.redo(); self.assertFalse(p.dirty)
        p.undo(); p.set_cell(0,0,'3'); self.assertFalse(p.can_redo)

    def test_undo_native_sheet_keeps_project_alias_and_selects_target(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source=Path(folder)/'source.mpx'; write_fixture(source)
            p=Presenter(); p.load(source)
            sheet=p.worksheet
            p.set_cell(0,0,'9'); p.select_worksheet(0)
            p.undo()
            self.assertIs(p.worksheet,sheet)
            self.assertIs(p.native_project.worksheets[1],sheet)
            self.assertEqual(sheet.columns[0].values,[1,2,3])
            self.assertFalse(p.dirty)
            p.redo(); self.assertEqual(sheet.columns[0].values,[9,2,3])

    def test_failed_paste_has_no_undo_entry(self):
        p=Presenter(); p.set_cell(0,0,'1'); count=len(p._undo_stack)
        with self.assertRaises(ValueError): p.paste(0,0,'2\ninvalid')
        self.assertEqual(len(p._undo_stack),count)
        self.assertEqual(p.worksheet.columns[0].values,[1])

    def test_new_regression_and_quality_presenter_reports(self):
        p=Presenter(); p.worksheet=Worksheet('Data',[
            Column('X1',values=[-1,-1,-1,-1,1,1,1,1]),
            Column('X2',values=[-1,-1,1,1,-1,-1,1,1]),
            Column('Y',values=[11.5,10.5,5.5,4.5,15.5,14.5,9.5,8.5])])
        report=format_entry(p.multiple_regression(2,[0,1]))
        self.assertIn('R-sq(adj)',report); self.assertIn('VIF',report)
        self.assertIn('Regression',report)
        report=format_entry(p.individuals_moving_range(2))
        self.assertIn('Signal rows',report)
        report=format_entry(p.normal_capability(2,0,20,10))
        self.assertIn('Cpk',report); self.assertIn('parts per million',report)

    def test_chart_segments_preserve_missing_gaps(self):
        self.assertEqual(chart_segments([1,None,2,3,None,4]),[[(1,1)],[(3,2),(4,3)],[(6,4)]])
