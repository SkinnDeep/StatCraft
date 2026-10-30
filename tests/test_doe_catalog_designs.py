"""Independent count, contrast and array-strength checks for catalogue plans."""
from collections import Counter
from copy import deepcopy
from itertools import combinations,product
import json
import math
import random
import unittest

from statcraft.doe_catalog_designs import create_design,PB_RUNS,TAGUCHI_ARRAYS


def numeric_factors(k,levels=(0,1)):
    return [{'name':f'Factor {i+1}','kind':'number','levels':list(levels)} for i in range(k)]


def rows(sheet):
    return list(zip(*(column.values for column in sheet.columns[4:])))


class DOECatalogDesignTests(unittest.TestCase):
    def assert_pair_balance(self,sheet):
        factors=sheet.metadata['doe']['factors']
        data=rows(sheet)
        for a,b in combinations(range(len(factors)),2):
            counts=Counter((row[a],row[b]) for row in data)
            expected=len(data)//(len(factors[a]['levels'])*len(factors[b]['levels']))
            self.assertEqual(set(counts),set(product(factors[a]['levels'],factors[b]['levels'])))
            self.assertTrue(all(value==expected for value in counts.values()))
        for at,factor in enumerate(factors):
            self.assertEqual(set(Counter(row[at] for row in data).values()),{len(data)//len(factor['levels'])})

    def test_general_factorial_all_combinations_first_factor_fastest(self):
        factors=[{'name':'Temperature','kind':'number','levels':[10,20,30]},
                 {'name':'Material','kind':'text','levels':['Steel','Brass']},
                 {'name':'Pressure','kind':'number','levels':[1,2,4,8]}]
        sheet=create_design('general_factorial',factors,randomize=False)
        self.assertEqual(sheet.row_count,24)
        self.assertEqual(rows(sheet)[:4],[(10.,'Steel',1.),(20.,'Steel',1.),(30.,'Steel',1.),(10.,'Brass',1.)])
        self.assertEqual(Counter(rows(sheet)),Counter(product([10.,20.,30.],['Steel','Brass'],[1.,2.,4.,8.])))
        self.assertEqual(sheet.columns[5].kind,'text')
        self.assert_pair_balance(sheet)

    def test_all_pb_orders_intercept_and_main_effect_orthogonality(self):
        for order in PB_RUNS:
            with self.subTest(order=order):
                sheet=create_design('plackett_burman',numeric_factors(order-1,(-1,1)),randomize=False,options={'runs':order})
                self.assertEqual(sheet.row_count,order)
                matrix=rows(sheet)
                self.assertTrue(all(sum(row[c] for row in matrix)==0 for c in range(order-1)))
                for a,b in combinations(range(order-1),2):
                    self.assertEqual(sum(row[a]*row[b] for row in matrix),0)
                self.assert_pair_balance(sheet)

    def test_pb12_20_are_nonregular_screening_designs(self):
        for n in (12,20):
            sheet=create_design('plackett_burman',numeric_factors(n-1,(-1,1)),options={'runs':n},randomize=False)
            matrix=rows(sheet)
            # Main effects remain partially aliased with interactions, unlike
            # a fictitious full factorial generated from an arbitrary run count.
            correlations=[sum(row[a]*row[b]*row[c] for row in matrix) for a,b,c in combinations(range(n-1),3)]
            self.assertTrue(any(0<abs(value)<n for value in correlations))

    def test_pb_auto_size_and_categorical_factor_levels(self):
        factors=numeric_factors(9)
        factors[0]={'name':'Machine','kind':'text','levels':['North','South']}
        sheet=create_design('plackett_burman',factors,randomize=False)
        self.assertEqual(sheet.metadata['doe']['base_runs'],12)
        self.assertEqual(set(sheet.columns[4].values),{'North','South'})
        self.assert_pair_balance(sheet)

    def test_every_supported_homogeneous_taguchi_array_strength_two(self):
        for name,item in TAGUCHI_ARRAYS.items():
            if name=='L8_MIXED':continue
            with self.subTest(array=name):
                factors=numeric_factors(item['capacity'],range(item['levels']))
                sheet=create_design('taguchi',factors,options={'array':name},randomize=False)
                self.assertEqual(sheet.row_count,item['runs'])
                self.assert_pair_balance(sheet)
                self.assertEqual(sheet.metadata['doe']['array_key'],name)

    def test_l9_known_main_effect_contrast_rank(self):
        sheet=create_design('taguchi',numeric_factors(4,(1,2,3)),options={'array':'L9'},randomize=False)
        # Orthogonal linear/quadratic contrasts provide eight independent
        # main-effect columns plus the intercept in nine observations.
        import numpy as np
        matrix=[]
        for row in rows(sheet):
            values=[1]
            for value in row:
                z=value-2
                values.extend((z,3*z*z-2))
            matrix.append(values)
        self.assertEqual(np.linalg.matrix_rank(matrix),9)

    def test_l16_four_level_field_is_not_integer_modulo_four(self):
        sheet=create_design('taguchi',numeric_factors(5,(1,2,3,4)),options={'array':'L16'},randomize=False)
        self.assertEqual(sheet.metadata['doe']['array_key'],'L16_4')
        self.assert_pair_balance(sheet)

    def test_mixed_l8_one_four_level_with_four_binary_factors(self):
        factors=numeric_factors(4)
        factors.insert(2,{'name':'Material','kind':'text','levels':['A','B','C','D']})
        for array in ('L8','L8_MIXED',None):
            with self.subTest(array=array):
                sheet=create_design('taguchi',factors,options={'array':array},randomize=False)
                self.assertEqual(sheet.row_count,8)
                self.assert_pair_balance(sheet)
                self.assertEqual(sheet.metadata['doe']['array_key'],'L8_MIXED')

    def test_taguchi_auto_array_smallest_supported(self):
        for k,levels,expected in ((3,[0,1],4),(8,[0,1],12),(4,[0,1,2],9),(5,[0,1,2],27),(6,[1,2,3,4,5],25)):
            with self.subTest(k=k,levels=levels):
                sheet=create_design('taguchi',numeric_factors(k,levels),randomize=False)
                self.assertEqual(sheet.row_count,expected)

    def test_replicate_blocks_are_complete_and_orthogonal_to_factors(self):
        for kind,options,factors in [('general_factorial',{},numeric_factors(3)),('plackett_burman',{'runs':12},numeric_factors(5)),('taguchi',{'array':'L9'},numeric_factors(4,[1,2,3]))]:
            with self.subTest(kind=kind):
                sheet=create_design(kind,factors,replicates=3,blocks=3,seed=42,options=options)
                patterns=[]
                for block in (1,2,3):
                    patterns.append(Counter(row for row,b in zip(rows(sheet),sheet.columns[3].values) if b==block))
                self.assertEqual(patterns[0],patterns[1]);self.assertEqual(patterns[1],patterns[2])

    def test_centers_numeric_two_level_only_per_block(self):
        for kind in ('general_factorial','plackett_burman'):
            sheet=create_design(kind,numeric_factors(3,[10,30]),replicates=2,blocks=2,centers=3,randomize=False)
            center=[row for row,pt in zip(rows(sheet),sheet.columns[2].values) if pt==0]
            self.assertEqual(center,[(20.,20.,20.)]*6)
            self.assertEqual(sheet.row_count,sheet.metadata['doe']['base_runs']*2+6)
            self.assertEqual(Counter(b for b,pt in zip(sheet.columns[3].values,sheet.columns[2].values) if pt==0),{1:3,2:3})

    def test_randomization_seed_stable_global_rng_untouched_and_standard_order_restorable(self):
        factors=numeric_factors(5)
        state=random.getstate()
        a=create_design('plackett_burman',factors,seed=9)
        b=create_design('plackett_burman',factors,seed=9)
        c=create_design('plackett_burman',factors,seed=10)
        standard=create_design('plackett_burman',factors,randomize=False)
        self.assertEqual(a,b);self.assertNotEqual(a.columns[0].values,c.columns[0].values)
        self.assertEqual(random.getstate(),state)
        self.assertEqual([row for _,row in sorted(zip(a.columns[0].values,rows(a)))],rows(standard))
        self.assertEqual(a.columns[1].values,list(range(1,a.row_count+1)))

    def test_inputs_metadata_and_output_are_independent_json_safe(self):
        factors=numeric_factors(3);options={'array':'L4'}
        before=deepcopy(factors);saved=deepcopy(options)
        sheet=create_design('taguchi',factors,options=options)
        self.assertEqual(factors,before);self.assertEqual(options,saved)
        factors[0]['levels'][0]=99
        self.assertNotIn(99,sheet.columns[4].values)
        self.assertNotIn(99,sheet.metadata['doe']['factors'][0]['levels'])
        self.assertFalse(sheet.metadata['doe']['native_parity'])
        json.dumps(sheet.metadata,allow_nan=False)

    def test_strict_factor_validation(self):
        invalid=[[],numeric_factors(1),[{'name':'X','kind':'date','levels':[1,2]},numeric_factors(1)[0]],
                 [{'name':'StdOrder','kind':'number','levels':[1,2]},numeric_factors(1)[0]],
                 [{'name':'X','kind':'number','levels':[1,True]},numeric_factors(1)[0]],
                 [{'name':'X','kind':'number','levels':[1,float('inf')]},numeric_factors(1)[0]],
                 [{'name':'X','kind':'number','levels':[1,1.]},numeric_factors(1)[0]],
                 [{'name':'X','kind':'text','levels':['A','']},numeric_factors(1)[0]],
                 [{'name':'X','kind':'text','levels':['A',2]},numeric_factors(1)[0]],
                 [{'name':' X ','kind':'number','levels':[1,2]},{'name':'x','kind':'number','levels':[1,2]}]]
        for factors in invalid:
            with self.subTest(factors=factors),self.assertRaises(ValueError):create_design('general_factorial',factors)

    def test_unsupported_or_nonorthogonal_catalog_requests_reject(self):
        for options in ({'runs':10},{'runs':28},{'runs':True},{'runs':12.0},{'arbitrary':12}):
            with self.subTest(options=options),self.assertRaises(ValueError):create_design('plackett_burman',numeric_factors(5),options=options)
        with self.assertRaises(ValueError):create_design('plackett_burman',numeric_factors(12),options={'runs':12})
        with self.assertRaises(ValueError):create_design('taguchi',numeric_factors(5,[1,2,3]),options={'array':'L9'})
        with self.assertRaises(ValueError):create_design('taguchi',numeric_factors(3,[1,2,3,4,5,6]))
        with self.assertRaises(ValueError):create_design('taguchi',[{'name':'A','kind':'number','levels':[0,1]}, {'name':'B','kind':'number','levels':[0,1,2]}])
        with self.assertRaises(ValueError):create_design('taguchi',numeric_factors(3),centers=1)

    def test_run_limits_blocks_and_scalar_types(self):
        with self.assertRaisesRegex(ValueError,'4096'):create_design('general_factorial',numeric_factors(13))
        self.assertEqual(create_design('general_factorial',numeric_factors(12),randomize=False).row_count,4096)
        for change in ({'replicates':True},{'replicates':0},{'blocks':2},{'blocks':2,'replicates':3},{'centers':-1},{'centers':1.5},{'randomize':1},{'seed':False},{'name':''}):
            with self.subTest(change=change),self.assertRaises(ValueError):create_design('general_factorial',numeric_factors(3),**change)
        factors=numeric_factors(2);factors[0]={'name':'Material','kind':'text','levels':['A','B']}
        with self.assertRaises(ValueError):create_design('general_factorial',factors,centers=1)
        with self.assertRaises(ValueError):create_design('general_factorial',numeric_factors(2,[0,1,2]),centers=1)


if __name__=='__main__':unittest.main()
