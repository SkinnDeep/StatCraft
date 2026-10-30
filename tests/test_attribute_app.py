import unittest
from statcraft.app import Presenter, format_entry, chart_segments
from statcraft.model import Column, Worksheet


class AttributeAppTests(unittest.TestCase):
    def test_aligned_missing_shorter_column_report_and_signals(self):
        p = Presenter()
        p.worksheet = Worksheet('Counts', [Column('Defective', values=[1, None, 8, 5]), Column('Inspected', values=[20, 30, 40])])
        entry = p.attribute_chart('P', 0, 1)
        result = entry['result']
        self.assertEqual(result['observations'], [.05, None, .2, None])
        self.assertEqual(result['missing'], 2)
        self.assertAlmostEqual(result['center'], .15)
        self.assertEqual(chart_segments(result['observations']), [[(1, .05)], [(3, .2)]])
        self.assertIn('Test 1 signal rows:', format_entry(entry))
        self.assertFalse(p.dirty)

    def test_invalid_chart_does_not_record_result(self):
        p = Presenter()
        p.worksheet = Worksheet('Counts', [Column('Defective', values=[3]), Column('Inspected', values=[2])])
        with self.assertRaises(ValueError): p.attribute_chart('P', 0, 1)
        with self.assertRaises(ValueError): p.attribute_chart('U', 0, 0)
        with self.assertRaises(ValueError): p.attribute_chart('invalid', 0, 1)
        self.assertEqual(p.history, [])
