import copy,math,tempfile,unittest
from pathlib import Path
import numpy as np
from scipy import stats
from statcraft.response_surface import create,fit,full_terms,validate_terms
from statcraft.model import Column,Worksheet
from statcraft.app import Presenter,format_entry
from statcraft.glm import settings
from statcraft.recipes import run


def factors(k):return [dict(name=chr(65+i),low=-1.,high=1.) for i in range(k)]


def measured():
    s=create(factors(2),centers=5,alpha_mode='face',randomize=False)
    y=[]
    for i,(a,b) in enumerate(zip(s.columns[4].values,s.columns[5].values)):
        y.append(10+2*a-3*b+4*a*a+5*b*b+1.5*a*b+([-.2,.1,.2,-.1,0][i-8] if i>=8 else 0))
    s.columns.append(Column('Yield',values=y));return s


class ResponseSurfaceTests(unittest.TestCase):
    def test_ccd_count_coordinates_and_rotatable_alpha(self):
        s=create(factors(3),centers=6,randomize=False);self.assertEqual(s.row_count,20)
        self.assertAlmostEqual(s.metadata['doe']['alpha'],8**.25)
        points=list(zip(*(c.values for c in s.columns[4:])))
        self.assertEqual(points[:8],[(a,b,c) for c in [-1.,1.] for b in [-1.,1.] for a in [-1.,1.]])
        self.assertEqual(s.columns[2].values.count(-1),6);self.assertEqual(points[-1],(0.,0.,0.))

    def test_all_supported_ccd_factor_counts_fit_quadratic_models(self):
        for k in range(2,6):
            s=create(factors(k),randomize=False);points=np.column_stack([c.values for c in s.columns[4:]])
            s.columns.append(Column('Y',values=[float(5+sum(row)+sum(row*row)+.03*(i%3)) for i,row in enumerate(points)]))
            r=fit(s,4+k,list(range(4,4+k)));self.assertEqual(len(r['coefficients']),1+k+k+k*(k-1)//2)

    def test_face_centered_and_axial_defined_ranges(self):
        s=create([dict(name='Heat',low=10.,high=30.),dict(name='Time',low=2.,high=4.)],centers=3,alpha_mode='custom',alpha=2,levels_define='axial',randomize=False)
        self.assertEqual(min(s.columns[4].values),10);self.assertEqual(max(s.columns[4].values),30)
        self.assertEqual(s.columns[4].metadata['rsm_coding'],dict(low=15.,high=25.))
        s=create(factors(2),alpha_mode='face');self.assertEqual(set(s.columns[4].values),{-1.,0.,1.})

    def test_box_behnken_three_four_factor_geometry_and_rank(self):
        for k,expected in [(3,15),(4,27)]:
            s=create(factors(k),kind='box_behnken',centers=3,randomize=False);self.assertEqual(s.row_count,expected)
            points=np.column_stack([c.values for c in s.columns[4:]])
            self.assertTrue(all(np.count_nonzero(row)==2 for row in points[:-3]));self.assertTrue(np.all(points[-3:]==0))
            s.columns.append(Column('Y',values=[float(1+sum(row)+sum(row*row)+i*.01) for i,row in enumerate(points)]));r=fit(s,4+k,list(range(4,4+k)))
            self.assertEqual(len(r['coefficients']),1+k+k+k*(k-1)//2)

    def test_randomized_replicates_preserve_plan_and_seed(self):
        a=create(factors(2),centers=3,replicates=2,seed=12);b=create(factors(2),centers=3,replicates=2,seed=12);c=create(factors(2),centers=3,replicates=2,randomize=False)
        self.assertEqual(a,b);self.assertEqual(a.row_count,22);self.assertEqual(sorted(a.columns[0].values),list(range(1,23)))
        self.assertEqual(sorted(zip(a.columns[4].values,a.columns[5].values)),sorted(zip(c.columns[4].values,c.columns[5].values)))

    def test_quadratic_coefficients_recover_known_polynomial(self):
        s=measured();r=fit(s,6,[4,5]);np.testing.assert_allclose([c['estimate'] for c in r['coefficients']],[10,2,-3,4,5,1.5],atol=1e-10)
        self.assertEqual(r['count'],13);self.assertAlmostEqual(r['ss_error'],.1,10)

    def test_lack_of_fit_decomposition_matches_replicate_means(self):
        s=measured();s.columns[6].values[0]+=2;r=fit(s,6,[4,5]);groups={}
        for a,b,y in zip(s.columns[4].values,s.columns[5].values,s.columns[6].values):groups.setdefault((a,b),[]).append(y)
        pure=sum(sum((y-sum(g)/len(g))**2 for y in g) for g in groups.values())
        self.assertAlmostEqual(r['pure_error']['ss'],pure,12);self.assertEqual(r['pure_error']['df'],4);self.assertEqual(r['lack_of_fit']['df'],3)
        self.assertAlmostEqual(r['lack_of_fit']['ss']+pure,r['ss_error'],12)
        expected=(r['lack_of_fit']['ss']/3)/(pure/4);self.assertAlmostEqual(r['lack_of_fit']['p_value'],stats.f.sf(expected,3,4),12)

    def test_terms_adjusted_f_equals_coefficient_t_squared(self):
        r=fit(measured(),6,[4,5])
        for a,c in zip(r['anova_terms'],r['coefficients'][1:]):self.assertAlmostEqual(a['f'],c['t']**2,9)
        self.assertAlmostEqual(sum(a['seq_ss'] for a in r['anova_terms']),r['ss_regression'],9)

    def test_missing_rows_and_zero_pure_error_guard(self):
        s=measured();s.columns[6].values[1]=None;r=fit(s,6,[4,5]);self.assertEqual(r['missing'],1);self.assertNotIn(1,r['row_indices'])
        for i in range(8,13):s.columns[6].values[i]=10
        r=fit(s,6,[4,5]);self.assertIsNone(r['lack_of_fit']['f'])

    def test_invalid_design_and_model_parameters(self):
        for kw in [dict(kind='box_behnken'),dict(centers=0),dict(alpha_mode='bad'),dict(alpha_mode='custom',alpha=.5),dict(randomize=1)]:
            with self.assertRaises(ValueError):create(factors(2),**kw)
        with self.assertRaises(ValueError):create([dict(name='A',low=1,high=1),dict(name='B',low=-1,high=1)])
        for terms in [[[0,0],[1]],[[0],[1],[1,0]],[[0],[1],[0,0],[0,0]],[]]:
            with self.assertRaises(ValueError):validate_terms(terms,2)

    def test_custom_worksheet_requires_valid_coding_and_numeric_roles(self):
        s=measured()
        with self.assertRaises(ValueError):fit(s,6,[4,5],coding=[dict(low=0,high=0)]*2)
        with self.assertRaises(ValueError):fit(s,4,[4,5])
        s.columns[4]=Column('Text','text',['x']*s.row_count)
        with self.assertRaises(ValueError):fit(s,6,[4,5])

    def test_creation_preserves_source_and_failed_destination_is_atomic(self):
        p=Presenter();before=copy.deepcopy(p.worksheet);target,e=p.create_response_surface(factors(2));self.assertIs(target,p);self.assertEqual(p.native_project.worksheets[0],before);self.assertEqual(p.worksheet.metadata['doe']['schema'],'statcraft-response-surface-v1')
        p=Presenter()
        with self.assertRaises(ValueError):p.create_response_surface(factors(2),display='bad')
        self.assertIsNone(p.native_project);self.assertEqual(p.history,[])

    def test_mpx_metadata_recipe_column_moves_and_undo(self):
        p=Presenter();p.worksheet=measured();e=p.analyze_response_surface(6,[4,5]);original=e['result']['fitted'];p.move_columns([5],'before_column',0)
        np.testing.assert_allclose(run(p,e['recipe'])['result']['fitted'],original)
        self.assertEqual(p.worksheet.columns[0].metadata['rsm_coding'],dict(low=-1.,high=1.));p.undo()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'rsm.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual(q.worksheet.metadata['doe']['schema'],'statcraft-response-surface-v1');self.assertFalse(q.result_stale(q.history[0]));np.testing.assert_allclose(run(q,q.history[0]['recipe'])['result']['fitted'],original)
            self.assertIn('Lack-of-Fit',format_entry(q.history[0]));self.assertIn('Factor Coding',format_entry(q.history[0]))


if __name__=='__main__':unittest.main()
