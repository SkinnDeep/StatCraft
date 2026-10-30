import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter,format_entry
from statcraft._mpx_fixture import write_factorial_fixture


class FactorialIntegrationTests(unittest.TestCase):
    def test_creation_is_transactional_and_metadata_persists(self):
        p=Presenter(); before=p.worksheet
        with self.assertRaises(ValueError): p.create_factorial([dict(name='A',low=1,high=1)])
        self.assertIs(p.worksheet,before)
        factors=[dict(name='A',low=-1,high=1),dict(name='B',low=10,high=20)]
        entry=p.create_factorial(factors,replicates=2,seed=42)
        self.assertEqual(entry['result']['runs'],8)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'design.statcraft'; p.save(path); q=Presenter(); q.load(path)
            self.assertEqual(q.worksheet.metadata['doe'],p.worksheet.metadata['doe'])
            self.assertEqual(q.worksheet.columns,p.worksheet.columns)

    def test_mpx_factorial_effects_save_rerun_and_dependencies(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx'; write_factorial_fixture(source)
            original=source.read_bytes(); p=Presenter(); p.load(source)
            entry=p.analyze_factorial(2,[0,1],plot_residuals=False,show_factor_coding=False)
            self.assertEqual([round(r['effect'],8) for r in entry['result']['effects']],[4,-6,3])
            self.assertIn('Estimated Effects',format_entry(entry)); self.assertNotIn('Factor Coding',format_entry(entry))
            p.save(target); self.assertEqual(source.read_bytes(),original)
            q=Presenter(); q.load(target); entry=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_factorial')
            q.select_worksheet(0); fresh=q.rerun_result(entry)
            self.assertEqual(q.native_project.active_index,1); self.assertEqual(fresh['result'],entry['result'])
            q.set_cell(0,2,'12'); self.assertTrue(q.result_stale(fresh))
            self.assertFalse(q.result_stale(q.rerun_result(fresh)))

    def test_failed_analysis_does_not_add_result(self):
        p=Presenter()
        with self.assertRaises(ValueError): p.analyze_factorial(0,[0,1])
        self.assertEqual(p.history,[])

    def test_multiple_blocks_presenter_roundtrip_and_rerun(self):
        p = Presenter()
        factors = [dict(name='A', low=-1, high=1), dict(name='B', low=-1, high=1)]
        entry = p.create_factorial(factors, replicates=2, blocks=2, seed=123, randomize=False)
        self.assertEqual(entry['result']['blocks'], 2)
        # Add a response column with a block effect
        y = [10.0 + 2.0 * row[4] - 3.0 * row[5] + (4.0 if row[3] == 1 else -4.0) for row in (p.worksheet.row(i) for i in range(p.worksheet.row_count))]
        from statcraft.model import Column
        p.worksheet.columns.append(Column('Response', values=y))
        fit_entry = p.analyze_factorial(6, [4, 5], include_blocks=True)
        self.assertTrue(fit_entry['result']['include_blocks'])
        self.assertIn('Blocks', fit_entry['result']['terms'])
        # Save and reload
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'blocks_project.statcraft'
            p.save(path)
            q = Presenter()
            q.load(path)
            self.assertEqual(q.worksheet.metadata['doe']['blocks'], 2)
            rerun = q.rerun_result(fit_entry)
            self.assertEqual(rerun['result']['include_blocks'], True)

