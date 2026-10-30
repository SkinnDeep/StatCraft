import math
from statistics import NormalDist, stdev
import unittest

from statcraft.histogram_options import build_histogram_panel, validate_histogram_settings


class HistogramOptionsTests(unittest.TestCase):
    def test_defaults_detached(self):
        settings = {}
        actual = validate_histogram_settings(settings)
        self.assertEqual(actual, dict(bins=10, scale='Frequency', cumulative=False, fit=None))
        actual['bins'] = 3
        self.assertEqual(settings, {})

    def test_invalid_settings(self):
        for settings in ({'bins': True}, {'bins': 0}, {'bins': 1}, {'bins': 1001}, {'bins': 2.0},
                         {'scale': 'Count'}, {'fit': 'Weibull'}, {'cumulative': 1},
                         {'cumulative': True, 'scale': 'Density'}, {'bogus': 1}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_histogram_settings(settings)

    def test_interval_bounds_are_inclusive(self):
        for bins in (2, 1000):
            self.assertEqual(validate_histogram_settings({'bins': bins})['bins'], bins)
            panel = build_histogram_panel([0, 1, 2], {'bins': bins})
            self.assertEqual(len(panel['counts']), bins)
            self.assertEqual(sum(panel['counts']), 3)

    def test_cutpoints_and_closed_final_interval(self):
        panel = build_histogram_panel([0, 1, 2, 3, 4], {'bins': 2})
        self.assertEqual(panel['edges'], [0, 2, 4])
        self.assertEqual(panel['counts'], [2, 3])
        self.assertEqual(panel['kind'], 'histogram')
        self.assertEqual(panel['curves'], [])

    def test_percent_density_and_cumulative(self):
        values = [0, 1, 2, 3, 4]
        self.assertEqual(build_histogram_panel(values, {'bins': 2, 'scale': 'Percent'})['counts'], [40, 60])
        density = build_histogram_panel(values, {'bins': 2, 'scale': 'Density'})
        self.assertEqual(density['counts'], [.2, .3])
        self.assertAlmostEqual(sum(density['counts']) * 2, 1)
        self.assertEqual(build_histogram_panel(values, {'bins': 2, 'cumulative': True})['counts'], [2, 5])
        self.assertEqual(build_histogram_panel(values, {'bins': 2, 'cumulative': True, 'scale': 'Percent'})['counts'], [40, 100])

    def test_constant_source_is_visible_without_fit(self):
        panel = build_histogram_panel([7, 7, 7], {'bins': 10})
        self.assertEqual(sum(panel['counts']), 3)
        self.assertLess(panel['edges'][0], 7)
        self.assertGreater(panel['edges'][-1], 7)
        with self.assertRaisesRegex(ValueError, 'positive sample'):
            build_histogram_panel([7, 7], {'fit': 'Normal'})

    def test_source_is_required_not_invented(self):
        for source in (None, [], {'edges': [0, 1], 'counts': [2]}, [None, 1], [True], [math.inf], [math.nan]):
            with self.subTest(source=source), self.assertRaises(ValueError):
                build_histogram_panel(source, {})

    def test_normal_scaling_and_sample_stdev(self):
        values = [-2, -1, 0, 1, 2]
        normal = NormalDist(0, stdev(values))
        for scale, multiplier in [('Frequency', 5 * 2), ('Percent', 100 * 2), ('Density', 1)]:
            panel = build_histogram_panel(values, {'bins': 2, 'fit': 'Normal', 'scale': scale})
            label, xs, ys, color = panel['curves'][0]
            self.assertEqual(label, 'Normal')
            self.assertEqual(xs[80], 0)
            self.assertAlmostEqual(ys[80], normal.pdf(0) * multiplier)
        for scale, multiplier in [('Frequency', 5), ('Percent', 100)]:
            panel = build_histogram_panel(values, {'fit': 'Normal', 'scale': scale, 'cumulative': True})
            ys = panel['curves'][0][2]
            self.assertAlmostEqual(ys[80], .5 * multiplier)
            self.assertTrue(all(a <= b for a, b in zip(ys, ys[1:])))
        with self.assertRaisesRegex(ValueError, 'at least two'):
            build_histogram_panel([1], {'fit': 'Normal'})


if __name__ == '__main__':
    unittest.main()
