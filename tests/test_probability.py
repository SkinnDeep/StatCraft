import math
import unittest
from statcraft.probability import calculate


class ProbabilityTests(unittest.TestCase):
    def test_closed_form_densities_and_cdfs(self):
        self.assertAlmostEqual(calculate('Normal', 'PDF/PMF', 0, [0, 1])['result'], 1/math.sqrt(2*math.pi))
        self.assertEqual(calculate('Normal', 'CDF', 0, [0, 1])['result'], .5)
        self.assertAlmostEqual(calculate('Binomial', 'PDF/PMF', 2, [4, .5])['result'], 6/16)
        self.assertAlmostEqual(calculate('Poisson', 'PDF/PMF', 0, [2])['result'], math.exp(-2))
        self.assertAlmostEqual(calculate('Exponential', 'CDF', 2, [2])['result'], 1-math.exp(-1))
        self.assertAlmostEqual(calculate('Weibull', 'CDF', 3, [2, 3])['result'], 1-math.exp(-1))

    def test_inverse_roundtrip(self):
        for name, p in [('Normal', [3,2]), ('Student t',[7]), ('Chi-square',[4]), ('F',[5,8])]:
            q = calculate(name, 'Inverse CDF', .9, p)['result']
            self.assertAlmostEqual(calculate(name, 'CDF', q, p)['result'], .9, places=9)

    def test_invalid_parameters(self):
        for name, op, x, p in [('Normal','CDF',0,[0,0]), ('Binomial','CDF',0,[2.5,.5]), ('Poisson','CDF',0,[-1]), ('Student t','Inverse CDF',1,[4])]:
            with self.assertRaises(ValueError): calculate(name, op, x, p)
