import copy,math,tempfile,unittest
from pathlib import Path
import numpy as np
from statcraft.model import Column
from statcraft.response_surface import create
from statcraft.response_surface_blocked import fit
from statcraft.glm import settings


def measured(blocks=2):
    s=create([dict(name='Temperature',low=-1.,high=1.),dict(name='Velocity',low=-1.,high=1.)],replicates=blocks,randomize=False)
    n=s.row_count//blocks
    s.columns[3]=Column('Batch',kind='text',values=['batch'+str(i//n+1) for i in range(s.row_count)])
    x=s.columns[4].values;y=s.columns[5].values
    s.columns.append(Column('Yield',values=[20+2*a-b+.7*a*a-.4*b*b+.2*a*b+5*(i//n)+.1*math.sin(i+1) for i,(a,b) in enumerate(zip(x,y))]))
    return s


class BlockedResponseSurfaceTests(unittest.TestCase):
    def test_matches_independent_full_rank_ols(self):
        s=measured(3);r=fit(s,6,[4,5],block_index=3)
        x=np.asarray(s.columns[4].values);y=np.asarray(s.columns[5].values);b=s.columns[3].values
        m=np.column_stack([np.ones(len(x)),[1 if v=='batch1' else -1 if v=='batch3' else 0 for v in b],[1 if v=='batch2' else -1 if v=='batch3' else 0 for v in b],x,y,x*x,y*y,x*y])
        coef=np.linalg.lstsq(m,s.columns[6].values,rcond=None)[0]
        np.testing.assert_allclose(r['fitted'],m@coef,atol=1e-10)
        self.assertEqual(r['anova_terms'][0]['df'],2);self.assertEqual(r['df_error'],s.row_count-m.shape[1])
        self.assertEqual(r['surface_terms'],[[0],[1],[0,0],[1,1],[0,1]])
    def test_pure_error_keeps_blocks_separate(self):
        s=measured();r=fit(s,6,[4,5],block_index=3)
        self.assertLess(r['pure_error']['ss'],.2)
        self.assertEqual(r['pure_error']['df'],10)
    def test_joint_missing_rows_and_reference_coding(self):
        s=measured();s.columns[3].values[0]=None;s.columns[4].values[1]=None
        r=fit(s,6,[4,5],block_index=3,options=settings()|{'coding':'reference'})
        self.assertEqual(r['missing'],2);self.assertEqual(r['row_indices'][0],2)
        self.assertTrue(all(math.isfinite(v) for v in r['fitted']))
    def test_rejects_bad_block_roles_and_unknown_observed_levels(self):
        s=measured()
        for i in [None,True,6,4,-1,99]:
            with self.assertRaises(ValueError):fit(s,6,[4,5],block_index=i)
        s.columns[3].values=['one']*s.row_count
        with self.assertRaisesRegex(ValueError,'2–32'):fit(s,6,[4,5],block_index=3)
    def test_source_and_saved_options_are_not_mutated(self):
        s=measured();before=copy.deepcopy(s);o=settings();original=copy.deepcopy(o);fit(s,6,[4,5],block_index=3,options=o)
        self.assertEqual(s,before);self.assertEqual(o,original)
    def test_report_coding_only_contains_continuous_factors(self):
        from statcraft.response_surface_report import sections
        r=fit(measured(),6,[4,5],block_index=3)
        tables=sections(r);coding=next(rows for title,headers,rows in tables if title=='Factor Coding')
        self.assertEqual([row[0] for row in coding],['Temperature','Velocity'])
        self.assertTrue(any(title=='Factor Information' for title,_,_ in tables))


class BlockedSurfaceWorkflows(unittest.TestCase):
    def document(self):
        from statcraft.app import Presenter
        p=Presenter();p.worksheet=measured();e=p.analyze_response_surface(6,[4,5],block_index=3)
        return p,e
    def test_prediction_uses_explicit_block_and_original_continuous_terms(self):
        from statcraft.prediction import predict,model_spec
        p,e=self.document();spec=model_spec(p.worksheet,e['recipe'])
        self.assertEqual(spec['predictor_indices'],[3,4,5]);self.assertEqual(spec['predictors'][0]['role'],'factor')
        r=predict(p.worksheet,e['recipe'],values=[['batch1',0.,0.],['batch2',0.,0.]])
        self.assertAlmostEqual(r['rows'][1]['fit']-r['rows'][0]['fit'],5.,delta=.04)
        with self.assertRaises(ValueError):predict(p.worksheet,e['recipe'],values=[['unknown',0.,0.]])
        saved=p.predict_model(e['recipe'],values=[['batch1',0.,0.],['batch2',0.,0.]])
        self.assertEqual(saved['recipe']['parameters']['values'][1][0],'batch2')
        p.rerun_result(saved)
    def test_model_contour_and_surface_keep_block_hold(self):
        from statcraft.model_plots import model_contour_plot,model_surface_plot
        p,e=self.document()
        for fn in (model_contour_plot,model_surface_plot):
            r=fn(p.worksheet,e['recipe'],4,5)
            self.assertTrue(r['panels'])
            self.assertTrue(any(h['name']=='Batch' and h['value']=='batch1' for h in r['hold_summary']))
    def test_column_moves_and_mpx_preserve_block_identity(self):
        from statcraft.app import Presenter
        from statcraft.recipes import columns,run
        p,e=self.document();original=e['result']['fitted'];self.assertEqual(columns(e['recipe']),[3,4,5,6])
        p.move_columns([3],'before_column',0)
        self.assertEqual(e['recipe']['parameters']['block_index'],0)
        np.testing.assert_allclose(run(p,e['recipe'])['result']['fitted'],original)
        p.undo()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'blocked.mpx';p.save(path);q=Presenter();q.load(path)
            saved=next(a for a in q.history if a.get('recipe',{}).get('action')=='analyze_response_surface')
            self.assertFalse(q.result_stale(saved));self.assertEqual(saved['recipe']['parameters']['block_index'],3)
            np.testing.assert_allclose(q.rerun_result(saved)['result']['fitted'],original)
    def test_deleted_block_rejects_rerun_and_undo_restores(self):
        p,e=self.document();p.delete_columns([3])
        with self.assertRaises(ValueError):p.rerun_result(e)
        p.undo();p.rerun_result(e)

if __name__=='__main__':unittest.main()

