import unittest
from statcraft.variable_dialogs import resolve_variables
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter


class VariableMappingTests(unittest.TestCase):
    def worksheet(self):
        return Worksheet('Data',[Column('Length mm',values=[1]),Column('Mass',values=[2]),Column('Group',kind='text',values=['A'])])

    def test_refs_and_quoted_names_preserve_order(self):
        self.assertEqual(resolve_variables('c2 "Length mm"',self.worksheet()),[1,0])

    def test_invalid_duplicate_wrong_type_and_unclosed_name(self):
        for text in ('C0','C9','C1 C1','Group','"Length mm','unknown'):
            with self.assertRaises(ValueError): resolve_variables(text,self.worksheet())
        self.assertEqual(resolve_variables('Group',self.worksheet(),('text',)),[2])

    def test_duplicate_names_require_column_address(self):
        w=self.worksheet(); w.columns[1].name='Length mm'
        with self.assertRaises(ValueError): resolve_variables('"Length mm"',w)
        self.assertEqual(resolve_variables('C1 C2',w),[0,1])

    def test_batch_column_naming_undo_preserves_values(self):
        p=Presenter(); p.worksheet=self.worksheet()
        p.rename_columns(0,['Length','Mass g']); p.undo()
        self.assertEqual([c.name for c in p.worksheet.columns],['Length mm','Mass','Group'])
        self.assertEqual(p.worksheet.columns[0].values,[1])
        p.redo(); self.assertEqual(p.worksheet.columns[1].name,'Mass g')

    def test_invalid_name_paste_is_transactional(self):
        p=Presenter(); p.worksheet=self.worksheet()
        with self.assertRaises(ValueError): p.rename_columns(2,['A','B'])
        self.assertEqual(p.worksheet.columns[2].name,'Group')
