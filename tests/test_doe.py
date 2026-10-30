import itertools
import math
import unittest
from statcraft.doe import create_factorial, analyze_factorial
from statcraft.model import Column, Worksheet


FACTORS=[dict(name='A',low=10,high=20),dict(name='B',low=100,high=200)]


class FactorialDesignTests(unittest.TestCase):
    def test_nist_standard_order_three_factors_and_units(self):
        sheet=create_factorial(FACTORS+[dict(name='C',low=-2,high=2)],randomize=False)
        self.assertEqual(sheet.headers,['StdOrder','RunOrder','PtType','Blocks','A','B','C'])
        self.assertEqual([sheet.row(i)[4:] for i in range(8)],
            [[10,100,-2],[20,100,-2],[10,200,-2],[20,200,-2],
             [10,100,2],[20,100,2],[10,200,2],[20,200,2]])
        self.assertEqual(sheet.columns[0].values,list(range(1,9)))
        self.assertEqual(sheet.metadata['doe']['factors'][0]['center'],15)

    def test_replicates_centers_and_randomization_reproducible(self):
        a=create_factorial(FACTORS,replicates=3,centers=2,seed=42)
        b=create_factorial(FACTORS,replicates=3,centers=2,seed=42)
        c=create_factorial(FACTORS,replicates=3,centers=2,seed=43)
        self.assertEqual(a,b);self.assertNotEqual(a.columns[0].values,c.columns[0].values)
        self.assertEqual(a.row_count,14);self.assertEqual(a.columns[1].values,list(range(1,15)))
        points=[tuple(a.row(i)[4:]) for i in range(14)]
        for corner in itertools.product((10,20),(100,200)):self.assertEqual(points.count(corner),3)
        self.assertEqual(points.count((15,150)),2)
        self.assertEqual(a.columns[2].values.count(0),2)
        self.assertEqual(set(a.columns[3].values),{1})

    def test_creation_domain_and_run_cap(self):
        for kwargs in [dict(replicates=0),dict(replicates=21),dict(centers=-1),dict(centers=21),
                       dict(randomize='yes'),dict(seed=True)]:
            with self.assertRaises(ValueError):create_factorial(FACTORS,**kwargs)
        for fs in [FACTORS[:1],FACTORS*5,[dict(name='A',low=1,high=1),FACTORS[1]],
                   [dict(name='A',low=-1e308,high=1e308),FACTORS[1]],
                   [dict(name='A',low=0,high=math.inf),FACTORS[1]],
                   [dict(name='Blocks',low=0,high=1),FACTORS[1]],
                   [FACTORS[0],FACTORS[0]]]:
            with self.assertRaises(ValueError):create_factorial(fs)
        eight=[dict(name='F'+str(i),low=-1,high=1) for i in range(8)]
        self.assertEqual(create_factorial(eight,replicates=16,randomize=False).row_count,4096)
        with self.assertRaises(ValueError):create_factorial(eight,replicates=17)


class FactorialAnalysisTests(unittest.TestCase):
    def known_design(self,randomize=False,centers=0):
        s=create_factorial(FACTORS,replicates=2,centers=centers,randomize=randomize,seed=25)
        y=[]
        for i in range(s.row_count):
            a=(s.columns[4].values[i]-15)/5;b=(s.columns[5].values[i]-150)/50
            # Replicate1 errors +1, replicate2 -1: orthogonal to every term.
            noise=1 if s.columns[0].values[i]<=4 else -1
            y.append(10+2*a-3*b+1.5*a*b+noise)
        s.columns.append(Column('Y',values=y))
        return s

    def test_orthogonal_analytic_main_interaction_effects_anova(self):
        s=self.known_design();r=analyze_factorial(s,6,[4,5])
        self.assertEqual(r['terms'],['A','B','A*B'])
        for c,estimate,effect in zip(r['coefficients'],[10,2,-3,1.5],[None,4,-6,3]):
            self.assertAlmostEqual(c['estimate'],estimate,places=12)
            if effect is None:self.assertIsNone(c['effect'])
            else:self.assertAlmostEqual(c['effect'],effect,places=12)
            # X'X = 8I, SSE8, residualDF4: all SE sqrt(2/8)=.5.
            self.assertAlmostEqual(c['standard_error'],.5,places=12)
        self.assertEqual((r['df_regression'],r['df_error']),(3,4))
        self.assertAlmostEqual(r['ss_error'],8,places=12)
        self.assertAlmostEqual(r['ss_regression'],122,places=11)
        self.assertAlmostEqual(r['ss_total'],130,places=11)
        self.assertAlmostEqual(r['f'],61/3,places=11)
        self.assertAlmostEqual(r['r_squared'],61/65,places=12)
        self.assertAlmostEqual(r['coefficients'][1]['effect_se'],1,places=12)
        self.assertFalse(r['native_parity'])

    def test_random_order_and_observed_level_inference(self):
        standard=analyze_factorial(self.known_design(),6,[4,5])
        s=self.known_design(True);s.metadata={}
        randomized=analyze_factorial(s,6,[4,5])
        for a,b in zip(standard['coefficients'],randomized['coefficients']):
            self.assertAlmostEqual(a['estimate'],b['estimate'],places=12)
            self.assertAlmostEqual(a['standard_error'],b['standard_error'],places=12)
        self.assertEqual(randomized['factor_coding'][0]['source'],'Observed levels')

    def test_center_runs_and_missing_response_alignment(self):
        s=self.known_design(centers=2);s.columns[6].values[1]=None
        r=analyze_factorial(s,6,[4,5])
        self.assertEqual((r['count'],r['missing']),(9,1))
        self.assertEqual(r['used_rows'],[0,2,3,4,5,6,7,8,9])
        self.assertEqual(r['coded_factors'][-1],[0,0])
        self.assertTrue(any('curvature' in w for w in r['warnings']))
        self.assertEqual(len(r['residuals']),9)

    def test_saturated_rank_invalid_settings_and_selections(self):
        s=create_factorial(FACTORS,randomize=False);s.columns.append(Column('Y',values=[1,4,2,8]))
        with self.assertRaises(ValueError):analyze_factorial(s,6,[4,5])
        s=self.known_design();s.columns[5].values=list(s.columns[4].values);s.metadata={}
        with self.assertRaisesRegex(ValueError,'rank'):analyze_factorial(s,6,[4,5],max_order=1)
        for response,factors,order in [(6,[4,4],2),(4,[4,5],2),(6,[4,5],4),(6,[4,5],0)]:
            with self.assertRaises(ValueError):analyze_factorial(self.known_design(),response,factors,order)
        s=self.known_design();s.columns[4].values[0]=17
        with self.assertRaises(ValueError):analyze_factorial(s,6,[4,5])
        s=self.known_design();s.columns[4].values[0]=15
        with self.assertRaisesRegex(ValueError,'center run'):analyze_factorial(s,6,[4,5])

    def test_three_way_hierarchy_analytic_effect(self):
        fs=[dict(name=n,low=-1,high=1) for n in 'ABC']
        s=create_factorial(fs,replicates=2,randomize=False)
        y=[5+a+2*b+3*c+4*a*b*c+(1 if i<8 else -1)
           for i,(a,b,c) in enumerate(zip(*(col.values for col in s.columns[4:])))]
        s.columns.append(Column('Y',values=y))
        r=analyze_factorial(s,7,[4,5,6],max_order=3)
        self.assertEqual(len(r['terms']),7)
        self.assertAlmostEqual(r['coefficients'][-1]['effect'],8,places=11)
        self.assertEqual(r['df_error'],8)

    def test_multiple_blocks_creation_and_blocking_on_replicates(self):
        # 2 factors (4 corners), 2 replicates, 2 blocks (block on replicates), 1 center per block
        sheet = create_factorial(FACTORS, replicates=2, centers=1, blocks=2, randomize=False)
        self.assertEqual(sheet.metadata['doe']['blocks'], 2)
        # Total runs = (4 * 2) + (1 * 2) = 10
        self.assertEqual(sheet.row_count, 10)
        blocks_col = sheet.columns[3].values
        self.assertEqual(blocks_col.count(1), 5)
        self.assertEqual(blocks_col.count(2), 5)
        pt_type = sheet.columns[2].values
        # Block 1: 4 corners (pt_type 1) then 1 center (pt_type 0)
        self.assertEqual(pt_type[:5], [1, 1, 1, 1, 0])
        # Block 2: 4 corners (pt_type 1) then 1 center (pt_type 0)
        self.assertEqual(pt_type[5:], [1, 1, 1, 1, 0])

    def test_multiple_blocks_confounding_single_replicate(self):
        # 3 factors (8 corners), 1 replicate, 2 blocks
        fs = [dict(name=n, low=-1, high=1) for n in 'ABC']
        sheet = create_factorial(fs, replicates=1, centers=0, blocks=2, randomize=False)
        self.assertEqual(sheet.metadata['doe']['blocks'], 2)
        self.assertEqual(sheet.row_count, 8)
        blocks_col = sheet.columns[3].values
        self.assertEqual(blocks_col.count(1), 4)
        self.assertEqual(blocks_col.count(2), 4)

    def test_multiple_blocks_analysis_separates_block_variation(self):
        # Known design with block effect: Replicate 1 gets +5, Replicate 2 gets -5
        s = create_factorial(FACTORS, replicates=2, centers=0, blocks=2, randomize=False)
        y = []
        for i in range(s.row_count):
            a = (s.columns[4].values[i] - 15) / 5
            b = (s.columns[5].values[i] - 150) / 50
            block = s.columns[3].values[i]
            block_noise = 5.0 if block == 1 else -5.0
            y.append(20.0 + 3.0 * a - 4.0 * b + block_noise)
        s.columns.append(Column('Y', values=y))
        # With include_blocks=True (default when multiple blocks present)
        r = analyze_factorial(s, 6, [4, 5], include_blocks=True)
        self.assertTrue(r['include_blocks'])
        self.assertIn('Blocks', r['terms'])
        # Factor estimates should match exactly
        coef_map = {c['name']: c for c in r['coefficients']}
        self.assertAlmostEqual(coef_map['A']['estimate'], 3.0, places=10)
        self.assertAlmostEqual(coef_map['B']['estimate'], -4.0, places=10)
        self.assertAlmostEqual(coef_map['A']['effect'], 6.0, places=10)
        self.assertAlmostEqual(coef_map['B']['effect'], -8.0, places=10)
        # Residual error should be 0 (exact fit)
        self.assertAlmostEqual(r['ss_error'], 0.0, places=10)

    def test_fractional_multiple_blocks(self):
        from statcraft.fractional import create_fractional
        fs = [dict(name=n, low=-1, high=1) for n in 'ABCD']
        sheet = create_fractional(fs, {'D': 'ABC'}, replicates=2, centers=1, blocks=2, randomize=False)
        self.assertEqual(sheet.metadata['doe']['blocks'], 2)
        # Total runs = (8 * 2) + (1 * 2) = 18
        self.assertEqual(sheet.row_count, 18)
        blocks_col = sheet.columns[3].values
        self.assertEqual(blocks_col.count(1), 9)
        self.assertEqual(blocks_col.count(2), 9)

    def test_multiple_blocks_domain_errors(self):
        # 3 corners cannot be split into 2 blocks
        with self.assertRaises(ValueError):
            create_factorial(FACTORS, replicates=1, blocks=3)
        with self.assertRaises(ValueError):
            create_factorial(FACTORS, replicates=1, blocks=0)


if __name__=='__main__':unittest.main()
