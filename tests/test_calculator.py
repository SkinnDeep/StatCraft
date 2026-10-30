import unittest
from statcraft.calculator import evaluate
from statcraft.model import Worksheet, Column


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.sheet = Worksheet('Data', [Column('x', values=[1, 2, None, 4]), Column('y', values=[10, 20, 30])])

    def test_formula_and_missing_alignment(self):
        self.assertEqual(evaluate('C1 * 2 + C2', self.sheet), [12,24,None,None])
        self.assertEqual(evaluate('SQRT(C1^2)', self.sheet), [1,2,None,4])
        self.assertEqual(evaluate('5', self.sheet), [5,5,5,5])

    def test_no_code_execution_or_attributes(self):
        for expr in ['__import__("os")', 'C1.__class__', '[C1]', 'C1[0]', 'SUM(C1)', 'C5', 'True']:
            with self.assertRaises(ValueError): evaluate(expr,self.sheet)

    def test_domain_errors_are_transactional(self):
        with self.assertRaisesRegex(ValueError, 'row 2'): evaluate('1 / (C1-2)', self.sheet)
        self.assertEqual(self.sheet.columns[0].values, [1,2,None,4])
