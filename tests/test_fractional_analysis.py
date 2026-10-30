import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter,format_entry
from statcraft.doe import analyze_factorial
from statcraft.fractional import create_fractional
from statcraft.model import Column
from statcraft._mpx_fixture import write_fractional_fixture

FACTORS=[dict(name=letter,low=-1,high=1) for letter in 'ABCD']
MAIN=[[0],[1],[2],[3]]


def sample():
    sheet=create_fractional(FACTORS,{'D':'ABC'},replicates=2,randomize=False)
    y=[]
    for row in range(16):
        a,b,c,d=sheet.row(row)[4:]
        y.append(10+2*a-3*b+1.5*c+.5*d+(1 if row<8 else -1))
    sheet.columns.append(Column('Response',values=y)); return sheet


class FractionalAnalysisTests(unittest.TestCase):
    def test_known_main_effects_and_alias_table(self):
        result=analyze_factorial(sample(),8,[4,5,6,7],max_order=1)
        self.assertEqual([round(c['effect'],8) for c in result['coefficients'][1:]],[4,-6,3,1])
        self.assertAlmostEqual(result['ss_error'],16); self.assertEqual(result['df_error'],11)
        self.assertEqual(result['design_resolution'],4)
        self.assertTrue(any('AB = CD' in row['aliases'] for row in result['alias_structure']))

    def test_explicit_model_and_signed_confounding_failure(self):
        s=sample(); terms=MAIN+[[0,1]]
        result=analyze_factorial(s,8,[4,5,6,7],selected_terms=terms)
        self.assertEqual(result['terms'],['A','B','C','D','A*B'])
        with self.assertRaisesRegex(ValueError,'confounded'):
            analyze_factorial(s,8,[4,5,6,7],selected_terms=terms+[[2,3]])
        s.columns[7].values=[-v for v in s.columns[7].values]
        with self.assertRaisesRegex(ValueError,'confounded'):
            analyze_factorial(s,8,[4,5,6,7],selected_terms=terms+[[2,3]])

    def test_hierarchy_and_invalid_term_inputs(self):
        for terms in ([],[[0,1]],[[0],[0]],[[True]],[[0,0]],[[8]],'A'):
            with self.subTest(terms=terms),self.assertRaises(ValueError):
                analyze_factorial(sample(),8,[4,5,6,7],selected_terms=terms)

    def test_changed_saved_generators_are_rejected(self):
        s=sample(); s.columns[7].values=[-v for v in s.columns[7].values]
        with self.assertRaisesRegex(ValueError,'saved fractional generators'):
            analyze_factorial(s,8,[4,5,6,7],max_order=1)

    def test_mpx_selected_terms_save_and_rerun(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'input.mpx',Path(folder)/'copy.mpx'; write_fractional_fixture(source)
            original=source.read_bytes(); p=Presenter(); p.load(source)
            entry=p.analyze_factorial(4,[0,1,2,3],selected_terms=MAIN)
            self.assertEqual(entry['recipe']['action'],'analyze_factorial_terms')
            p.save(target); self.assertEqual(source.read_bytes(),original)
            q=Presenter(); q.load(target); entry=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_factorial_terms')
            self.assertEqual(q.rerun_result(entry)['result'],entry['result'])
            q.set_cell(0,4,'11'); self.assertTrue(q.result_stale(entry)); self.assertFalse(q.result_stale(q.rerun_result(entry)))

    def test_presenter_alias_text_and_statcraft_metadata(self):
        p=Presenter(); p.worksheet=sample(); entry=p.analyze_factorial(8,[4,5,6,7],selected_terms=MAIN)
        self.assertIn('Alias Structure',format_entry(entry))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'design.statcraft'; p.save(path); q=Presenter(); q.load(path)
            self.assertEqual(q.worksheet.metadata,p.worksheet.metadata)
            self.assertEqual(q.analyze_factorial(8,[4,5,6,7],selected_terms=MAIN)['result'],entry['result'])
