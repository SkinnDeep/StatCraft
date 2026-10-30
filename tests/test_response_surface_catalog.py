"""Functional response-surface catalog, fractions, blocks and actual geometry."""
import itertools, math, tempfile, unittest
from pathlib import Path
import numpy as np
from statcraft.response_surface import create,fit,design_summary,full_terms,validate_terms
from statcraft.response_surface_catalog import catalog,column_masks
from statcraft.model import Column


def factors(k):return [dict(name=chr(65+i),low=-1.,high=1.) for i in range(k)]
def build(spec,**options):
    values={key:spec[key] for key in ('kind','fraction','blocks','centers','center_cube','center_axial')}
    values.update(alpha_mode='default',randomize=False);values.update(options)
    return create(factors(spec['factors']),**values)
def matrix(sheet):
    x=np.column_stack([c.values for c in sheet.columns[4:]])
    return np.column_stack([np.ones(sheet.row_count)]+[x[:,i] for i in range(x.shape[1])]+[x[:,i]**2 for i in range(x.shape[1])]+[x[:,i]*x[:,j] for i,j in itertools.combinations(range(x.shape[1]),2)])


class ResponseSurfaceCatalogTests(unittest.TestCase):
    def test_every_catalog_cell_generates_the_advertised_design(self):
        self.assertGreaterEqual(len(catalog()),50)
        for spec in catalog():
            with self.subTest(spec=spec):
                sheet=build(spec)
                self.assertEqual(sheet.row_count,spec['runs'])
                self.assertEqual(set(sheet.columns[3].values),set(range(1,spec['blocks']+1)))
                self.assertEqual(sheet.metadata['doe']['centers'],spec['centers'])
                self.assertEqual(sheet.columns[2].values.count(0),spec['centers'])
                self.assertAlmostEqual(sheet.metadata['doe']['alpha'],spec['alpha'])
    def test_all_catalog_quadratic_models_and_blocks_are_estimable(self):
        for spec in catalog():
            with self.subTest(spec=spec):
                sheet=build(spec);x=matrix(sheet);b=np.asarray(sheet.columns[3].values)
                augmented=np.column_stack([x]+[(b==level).astype(float) for level in range(2,spec['blocks']+1)])
                self.assertEqual(np.linalg.matrix_rank(augmented),augmented.shape[1])
    def test_default_blocks_are_orthogonal_to_all_quadratic_terms(self):
        for spec in catalog():
            if spec['blocks']==1:continue
            with self.subTest(spec=spec):
                sheet=build(spec);x=matrix(sheet);b=np.asarray(sheet.columns[3].values)
                means=[x[b==level].mean(axis=0) for level in sorted(set(b))]
                for mean in means[1:]:np.testing.assert_allclose(mean,means[0],atol=2e-15)
                self.assertTrue(sheet.metadata['doe']['orthogonal_blocks'])
    def test_fractions_are_actual_subsets_and_resolution_five_or_better(self):
        for k,fraction in ((5,2),(6,2),(7,2),(8,2),(8,4),(9,4),(10,8)):
            masks=column_masks(k,fraction)
            effects=list(masks)+[a^b for a,b in itertools.combinations(masks,2)]
            self.assertEqual(len(effects),len(set(effects)))
            spec=next(s for s in catalog() if(s['kind'],s['factors'],s['fraction'],s['blocks'])==('central_composite',k,fraction,1))
            sheet=build(spec);cube=[row for row in zip(*(c.values for c in sheet.columns[4:])) if all(abs(x)==1 for x in row)]
            self.assertEqual(len(cube),2**k//fraction)
            self.assertEqual(len(set(cube)),len(cube))
    def test_two_factor_blocked_catalog_has_three_centers_in_each_block(self):
        spec=next(s for s in catalog() if(s['kind'],s['factors'],s['blocks'])==('central_composite',2,2))
        sheet=build(spec);self.assertEqual(sheet.row_count,14)
        for block in (1,2):self.assertEqual(sum(t==0 and b==block for t,b in zip(sheet.columns[2].values,sheet.columns[3].values)),3)
    def test_custom_centers_change_actual_runs_and_orthogonality_warning(self):
        sheet=create(factors(3),blocks=3,center_cube=3,center_axial=1,alpha_mode='default',randomize=False)
        self.assertEqual(sheet.row_count,18);self.assertFalse(sheet.metadata['doe']['orthogonal_blocks']);self.assertTrue(sheet.metadata['doe']['warnings'])
    def test_custom_center_total_is_respected_when_no_split_is_given(self):
        sheet=create(factors(5),blocks=2,centers=6,alpha_mode='default')
        self.assertEqual(sheet.row_count,48);self.assertEqual(sheet.columns[2].values.count(0),6)
    def test_replicate_blocks_have_distinct_labels_and_real_runs(self):
        sheet=create(factors(2),blocks=2,center_cube=3,center_axial=3,replicates=3,block_replicates=True,alpha_mode='default',seed=7)
        self.assertEqual(sheet.row_count,42);self.assertEqual(set(sheet.columns[3].values),set(range(1,7)))
        self.assertEqual(sheet.metadata['doe']['base_blocks'],2);self.assertEqual(sheet.metadata['doe']['blocks'],6)
        self.assertEqual(sorted(sheet.columns[0].values),list(range(1,43)))
    def test_randomization_stays_inside_blocks_and_is_reproducible(self):
        kw=dict(blocks=2,center_cube=3,center_axial=3,replicates=2,block_replicates=True,alpha_mode='default',seed=12)
        a=create(factors(2),**kw);b=create(factors(2),**kw);self.assertEqual(a,b)
        self.assertEqual(a.columns[3].values,sorted(a.columns[3].values))
    def test_no_replicate_blocking_reuses_base_block_labels(self):
        sheet=create(factors(2),blocks=2,center_cube=3,center_axial=3,replicates=3)
        self.assertEqual(sheet.row_count,42);self.assertEqual(set(sheet.columns[3].values),{1,2})
    def test_box_behnken_larger_designs_are_three_level_no_corner_designs(self):
        for k in (5,6,7,9,10):
            spec=next(s for s in catalog() if(s['kind'],s['factors'],s['blocks'])==('box_behnken',k,1))
            sheet=build(spec);x=np.column_stack([c.values for c in sheet.columns[4:]])
            self.assertTrue(set(x.ravel())<={-1.,0.,1.})
            self.assertTrue(np.all(np.sum(x!=0,axis=1)<k))
            np.testing.assert_allclose(x.sum(axis=0),0)
            np.testing.assert_allclose(np.square(x).sum(axis=0),np.square(x).sum(axis=0)[0])
    def test_invalid_blank_catalog_cells_do_not_generate_fake_designs(self):
        for kwargs in (dict(kind='box_behnken'),dict(fraction=4),dict(blocks=5)):
            with self.assertRaises(ValueError):create(factors(2),**kwargs)
        with self.assertRaises(ValueError):create(factors(8),kind='box_behnken')
        with self.assertRaises(ValueError):create(factors(10),fraction=1)
    def test_rank_deficient_custom_settings_rejected(self):
        with self.assertRaises(ValueError):create(factors(2),center_cube=0,center_axial=0,alpha_mode='rotatable')
    def test_unsupported_center_role_and_bad_options_rejected(self):
        for kwargs in (dict(center_cube=-1),dict(center_axial=2),dict(block_replicates=1),dict(fraction=3),dict(alpha_mode='custom',alpha=6)):
            with self.assertRaises(ValueError):create(factors(2),**kwargs)
    def test_total_runs_bounded_before_expansion(self):
        with self.assertRaises(ValueError):create(factors(7),centers=1000,replicates=10)
    def test_axial_defined_ranges_and_custom_alpha_for_fraction(self):
        sheet=create(factors(8),fraction=4,centers=10,alpha_mode='custom',alpha=3,levels_define='axial',randomize=False)
        for col in sheet.columns[4:]:self.assertEqual((min(col.values),max(col.values)),(-1.,1.))
        self.assertEqual(sheet.row_count,90)
    def test_expanded_unblocked_fit_recovers_ten_factor_quadratic(self):
        spec=next(s for s in catalog() if(s['kind'],s['factors'],s['blocks'])==('box_behnken',10,1));sheet=build(spec)
        x=matrix(sheet);beta=np.arange(1,x.shape[1]+1)/100
        sheet.columns.append(Column('Response',values=(x@beta).tolist()))
        result=fit(sheet,14,list(range(4,14)))
        np.testing.assert_allclose([c['estimate'] for c in result['coefficients']],beta,atol=1e-12)
        self.assertEqual(len(result['terms']),65)
    def test_design_summary_reports_actual_fraction_and_blocks(self):
        spec=next(s for s in catalog() if(s['factors'],s['fraction'],s['blocks'])==(8,4,5));sheet=build(spec)
        result=design_summary(sheet,'full')
        self.assertEqual((result['runs'],result['blocks'],result['fraction']),(90,5,4))
        self.assertEqual((result['cube_center_points'],result['axial_center_points']),(8,2))
        self.assertEqual(len(result['design_table']),90)
    def test_mpx_roundtrip_retains_block_and_fraction_metadata(self):
        from statcraft.app import Presenter
        spec=next(s for s in catalog() if(s['factors'],s['fraction'],s['blocks'])==(8,4,5));p=Presenter();p.worksheet=build(spec)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fractional.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual(q.worksheet.metadata['doe'],p.worksheet.metadata['doe'])
            self.assertEqual(q.worksheet.columns[3].values,p.worksheet.columns[3].values)

if __name__=='__main__':unittest.main()
