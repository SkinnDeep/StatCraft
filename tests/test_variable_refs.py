import unittest
from statcraft.model import Column, Worksheet
from statcraft.variable_dialogs import format_variable_reference, format_variable_list, resolve_variables


class VariableReferenceTests(unittest.TestCase):
    def sheet(self):
        return Worksheet('Data', [
            Column('Strength (N)',values=[1,2]),
            Column('Same name',values=[2,3]),
            Column('Same name',values=[4,5]),
            Column('Batch "A": C2 \\ Ω\nnext',kind='text',values=['A','B']),
            Column('C2',values=[6,7]),
            Column('When',kind='date',values=[45000,45001]),
        ])

    def test_readable_reference_retains_header_and_position(self):
        sheet=self.sheet()
        self.assertEqual(format_variable_reference(0,sheet),'C1: "Strength (N)"')
        indices=[2,0,1,4]
        self.assertEqual(resolve_variables(format_variable_list(indices,sheet),sheet),indices)

    def test_duplicate_names_use_stable_position(self):
        sheet=self.sheet()
        self.assertEqual(resolve_variables('C3: "Same name" C2: "Same name"',sheet),[2,1])
        with self.assertRaises(ValueError): resolve_variables('"Same name"',sheet)

    def test_punctuation_quotes_unicode_and_newlines_round_trip(self):
        sheet=self.sheet(); reference=format_variable_reference(3,sheet)
        self.assertIn('C4-T:',reference)
        self.assertEqual(resolve_variables(reference,sheet,('text',)),[3])

    def test_quoted_column_like_name_is_a_name(self):
        sheet=self.sheet()
        self.assertEqual(resolve_variables('C2 "C2"',sheet),[1,4])
        self.assertEqual(resolve_variables("'Strength (N)'",sheet),[0])

    def test_native_type_suffix_and_eligibility(self):
        sheet=self.sheet()
        self.assertEqual(resolve_variables('c4-t C6-D',sheet,('text','date')),[3,5])
        for value in ('C4-D','C6-T','C4-T'):
            with self.assertRaises(ValueError): resolve_variables(value,sheet)

    def test_decorated_identity_survives_header_rename(self):
        sheet=self.sheet(); reference=format_variable_reference(0,sheet)
        sheet.columns[0].name='New name'
        self.assertEqual(resolve_variables(reference,sheet),[0])

    def test_invalid_mixed_and_duplicate_references_fail(self):
        sheet=self.sheet()
        for value in ('C1:','C1: unquoted','C1: "ok" garbage','C0: "bad"',
                      'C99: "bad"','C1 "Strength (N)"','C1: "unterminated',
                      'C1: "ok"C2','C1: "ok" C1','C1: "a" "b"'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_variables(value,sheet)

    def test_empty_reference_list_is_empty(self):
        self.assertEqual(resolve_variables('  ',self.sheet()),[])


if __name__=='__main__': unittest.main()
