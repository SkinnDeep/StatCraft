import json
import math
import unittest
from statcraft.fractional import alias_structure,create_fractional


def factors(k):return [dict(name=chr(65+i),low=-1,high=1) for i in range(k)]
def row_for(structure,term):return next(r for r in structure['rows'] if r['term']==term)
def aliases(structure,term):return {a['term']:a['sign'] for a in row_for(structure,term)['aliases']}


class FractionalTests(unittest.TestCase):
    def test_resolution_four_hand_aliases(self):
        a=alias_structure({'D':'ABC'},4)
        self.assertEqual(a['resolution'],4)
        self.assertEqual({w['term']:w['sign'] for w in a['defining_relation']},{'I':1,'ABCD':1})
        self.assertEqual(aliases(a,'AB'),{'AB':1,'CD':1})
        self.assertEqual(aliases(a,'A'),{'A':1,'BCD':1})
        self.assertEqual(aliases(a,'AC'),{'AC':1,'BD':1})
        self.assertEqual(aliases(a,'AD'),{'AD':1,'BC':1})
        self.assertEqual(json.loads(json.dumps(a)),a)

    def test_negative_generator_alias_signs_and_complement_fraction(self):
        a=alias_structure({'D':'-ABC'},4)
        self.assertEqual(a['resolution'],4)
        self.assertEqual(aliases(a,'A'),{'A':1,'BCD':-1})
        self.assertEqual(aliases(a,'AB'),{'AB':1,'CD':-1})
        pos=create_fractional(factors(4),{'D':'ABC'},randomize=False)
        neg=create_fractional(factors(4),{'D':'-ABC'},randomize=False)
        self.assertEqual(neg.columns[7].values,[-v for v in pos.columns[7].values])

    def test_two_generator_signed_group_closure_hand_calculation(self):
        # D=AB, E=-AC -> I=ABD=-ACE=-BCDE; shortest word3.
        a=alias_structure({'D':'AB','E':'-AC'},5)
        self.assertEqual(a['resolution'],3)
        self.assertEqual({w['term']:w['sign'] for w in a['defining_relation']},
                         {'I':1,'ABD':1,'ACE':-1,'BCDE':-1})
        self.assertEqual(aliases(a,'A'),{'A':1,'BD':1,'CE':-1,'ABCDE':-1})
        # max_order restricts seeds, not full alias orbit.
        b=alias_structure({'D':'AB','E':'-AC'},5,max_order=1)
        self.assertEqual(len(b['rows']),6)
        self.assertIn('ABCDE',aliases(b,'A'))

    def test_standard_order_and_all_alias_identities_on_actual_corners(self):
        s=create_fractional(factors(4),{'D':'ABC'},randomize=False)
        expected=[[-1,-1,-1,-1],[1,-1,-1,1],[-1,1,-1,1],[1,1,-1,-1],
                  [-1,-1,1,1],[1,-1,1,-1],[-1,1,1,-1],[1,1,1,1]]
        self.assertEqual([s.row(i)[4:] for i in range(8)],expected)
        s=create_fractional(factors(5),{'D':'AB','E':'-AC'},randomize=False)
        algebra=s.metadata['doe']['alias_structure']
        for i in range(8):
            values=s.row(i)[4:]
            def product(mask):return math.prod(v for j,v in enumerate(values) if mask&(1<<j))
            for row in algebra['rows']:
                for alias in row['aliases']:self.assertEqual(product(row['mask']),alias['sign']*product(alias['mask']))

    def test_actual_units_centers_replicates_and_seeded_order(self):
        fs=[dict(name=n,low=10*i,high=10*i+4) for i,n in enumerate('ABCD')]
        a=create_fractional(fs,{'D':'ABC'},replicates=2,centers=3,seed=5)
        b=create_fractional(fs,{'D':'ABC'},replicates=2,centers=3,seed=5)
        self.assertEqual(a,b);self.assertEqual(a.row_count,19)
        self.assertEqual(a.columns[1].values,list(range(1,20)))
        self.assertEqual(sorted(a.columns[0].values),list(range(1,20)))
        self.assertEqual(a.columns[2].values.count(0),3)
        for i,t in enumerate(a.columns[2].values):
            if t==0:self.assertEqual(a.row(i)[4:],[2,12,22,32])
        self.assertEqual(set(a.columns[3].values),{1})
        self.assertEqual(a.metadata['doe']['schema'],'statcraft-regular-fractional-v1')

    def test_nonterminal_generated_factor_and_normalized_product(self):
        a=alias_structure({'B':'D*C*A'},4)
        self.assertEqual(a['base_factors'],['A','C','D'])
        self.assertEqual(a['generators'],{'B':'ACD'})
        s=create_fractional(factors(4),{'B':'ACD'},randomize=False)
        for i in range(8):
            x=s.row(i)[4:];self.assertEqual(x[1],x[0]*x[2]*x[3])

    def test_invalid_generator_algebra(self):
        for gen,k in [({},4),({'A':'B'},3),({'D':'A'},4),({'D':'-A'},4),
                      ({'D':'AB','E':'-AB'},5),({'C':'AB','D':'AC'},4),
                      ({'D':'AAB'},4),({'D':'I'},4),({'X':'AB'},4),
                      ({'d':'ABC'},4),({'D':'A+'},4),({'D':5},4)]:
            with self.assertRaises(ValueError):alias_structure(gen,k)
        with self.assertRaises(ValueError):alias_structure({'D':'ABC'},4,max_order=4)

    def test_configuration_validation_and_bounded_maximum(self):
        for kwargs in [dict(replicates=0),dict(replicates=21),dict(centers=21),dict(randomize=1),dict(seed=True)]:
            with self.assertRaises(ValueError):create_fractional(factors(4),{'D':'ABC'},**kwargs)
        fs=factors(4);fs[0]['high']=math.inf
        with self.assertRaises(ValueError):create_fractional(fs,{'D':'ABC'})
        # Largest one-generator 8-factor corner plan has 128 runs; 20 reps+20centers.
        s=create_fractional(factors(8),{'H':'ABCDEFG'},replicates=20,centers=20)
        self.assertEqual(s.row_count,2580)


if __name__=='__main__':unittest.main()
