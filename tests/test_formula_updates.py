import copy
import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.conditional_formatting import effective_highlights


def document():
    p=Presenter();p.worksheet=Worksheet('Data',[Column('Input',values=[1,2,3]),Column('Twice'),Column('Total')])
    return p


class FormulaUpdateTests(unittest.TestCase):
    def test_edit_chain_and_single_undo_redo(self):
        p=document();p.assign_formula(1,'C1*2');p.assign_formula(2,'C2+1')
        previous=len(p._undo_stack);p.set_cell(0,0,'10')
        self.assertEqual([c.values[0] for c in p.worksheet.columns],[10,20,21])
        self.assertEqual(len(p._undo_stack),previous+1)
        p.undo();self.assertEqual([c.values[0] for c in p.worksheet.columns],[1,2,3])
        p.redo();self.assertEqual([c.values[0] for c in p.worksheet.columns],[10,20,21])

    def test_dependency_order_does_not_follow_column_position(self):
        p=document();p.assign_formula(2,'C1*2');p.assign_formula(1,'C3+1')
        p.set_cell(0,0,'5');self.assertEqual([c.values[0] for c in p.worksheet.columns],[5,11,10])

    def test_missing_paste_growth_and_delete_rows(self):
        p=document();p.assign_formula(1,'C1*2');p.paste(1,0,'*\n7\n8\n')
        self.assertEqual(p.worksheet.columns[1].values,[2,None,14,16])
        p.delete_rows([0]);self.assertEqual(p.worksheet.columns[1].values,[None,14,16])
        p.undo();self.assertEqual(p.worksheet.columns[1].values,[2,None,14,16])

    def test_circular_assignment_is_atomic(self):
        p=document();p.assign_formula(1,'C1*2');before=copy.deepcopy(p.worksheet)
        history=list(p.history);undo=len(p._undo_stack)
        with self.assertRaisesRegex(ValueError,'Circular'):p.assign_formula(0,'C2+1')
        self.assertEqual(p.worksheet,before);self.assertEqual(p.history,history)
        self.assertEqual(len(p._undo_stack),undo)
        with self.assertRaisesRegex(ValueError,'Circular'):p.assign_formula(2,'C3+1')

    def test_failed_update_rolls_back_input_all_outputs_and_dirty_state(self):
        p=document();p.assign_formula(1,'10/C1');p.assign_formula(2,'C2+1')
        before=copy.deepcopy(p.worksheet);undo=len(p._undo_stack);dirty=p.dirty
        with self.assertRaisesRegex(ValueError,'C2.*row 2'):p.paste(0,0,'4\n0\n')
        self.assertEqual(p.worksheet,before);self.assertEqual(len(p._undo_stack),undo);self.assertEqual(p.dirty,dirty)

    def test_global_mode_manual_calculate_and_reenable(self):
        p=document();p.assign_formula(1,'C1*2');p.set_automatic_formulas(False)
        p.set_cell(0,0,'8');self.assertEqual(p.worksheet.columns[1].values[0],2)
        self.assertEqual(p.calculate_all_formulas(),1);self.assertEqual(p.worksheet.columns[1].values[0],16)
        p.set_cell(0,0,'9');p.set_automatic_formulas(True)
        self.assertEqual(p.worksheet.columns[1].values[0],18)
        p.undo();self.assertEqual(p.worksheet.columns[1].values[0],16)

    def test_enable_failure_keeps_mode_off(self):
        p=document();p.assign_formula(1,'1/C1');p.set_automatic_formulas(False);p.set_cell(0,0,'0')
        with self.assertRaises(ValueError):p.set_automatic_formulas(True)
        self.assertFalse(p.auto_calculate_formulas);self.assertEqual(p.worksheet.columns[1].values[0],1)

    def test_remove_formula_retains_values_and_allows_edits(self):
        p=document();p.assign_formula(1,'C1*2');p.remove_formulas([1]);p.set_cell(0,0,'9')
        self.assertEqual(p.worksheet.columns[1].values[0],2)
        p.set_cell(0,1,'7');self.assertEqual(p.worksheet.columns[1].values[0],7)
        p.undo();p.undo();p.undo();self.assertEqual(p.worksheet.columns[1].metadata['formula'],'C1*2')

    def test_direct_overwrite_is_explicit_while_automatic(self):
        p=document();p.assign_formula(1,'C1*2')
        with self.assertRaisesRegex(ValueError,'Remove its formula'):p.set_cell(0,1,'100')
        with self.assertRaisesRegex(ValueError,'Remove its formula'):p.paste(0,0,'100\t200\n')
        self.assertEqual(p.worksheet.columns[0].values[0],1)
        p.set_automatic_formulas(False);p.set_cell(0,1,'100');self.assertEqual(p.worksheet.columns[1].values[0],100)

    def test_insert_move_and_delete_preserve_reference_identity(self):
        p=document();p.assign_formula(1,'C1*2');p.insert_columns(0)
        self.assertEqual(p.worksheet.columns[2].metadata['formula'],'C2*2')
        p.move_columns([2],'before_c1')
        self.assertEqual(p.worksheet.columns[0].metadata['formula'],'C3*2')
        p.set_cell(0,2,'8');self.assertEqual(p.worksheet.columns[0].values[0],16)
        p.delete_columns([1]);self.assertEqual(p.worksheet.columns[0].metadata['formula'],'C2*2')
        before=copy.deepcopy(p.worksheet)
        with self.assertRaisesRegex(ValueError,'used by a formula'):p.delete_columns([1])
        self.assertEqual(p.worksheet,before)

    def test_stored_constant_edit_updates_formulas(self):
        p=document();p.replace_stored_data(constants=[Column('Scale',values=[2])]);p.assign_formula(1,'C1*K1')
        p.replace_stored_data(constants=[Column('Scale',values=[4])]);self.assertEqual(p.worksheet.columns[1].values,[4,8,12])
        p.undo();self.assertEqual(p.worksheet.columns[1].values,[2,4,6])

    def test_batch_replace_has_one_undo_and_calculates_once_at_commit(self):
        p=document();p.assign_formula(1,'C1*2');before=len(p._undo_stack)
        p.replace_cells('1','10',whole_word=True)
        self.assertEqual(p.worksheet.columns[1].values,[20,4,6]);self.assertEqual(len(p._undo_stack),before+1)
        p.undo();self.assertEqual(p.worksheet.columns[0].values,[1,2,3])

    def test_all_worksheets_calculate_and_undo_together(self):
        p=document();p.assign_formula(1,'C1*2');p.add_worksheet('Other');p.paste(0,0,'3\n4\n')
        p.assign_formula(1,'C1+10');p.set_automatic_formulas(False)
        p.set_cell(0,0,'30');p.select_worksheet(0);p.set_cell(0,0,'20')
        self.assertEqual(p.calculate_all_formulas(),2)
        sheets=p.native_project.worksheets
        self.assertEqual([s.columns[1].values[0] for s in sheets],[40,40])
        p.undo();self.assertEqual([s.columns[1].values[0] for s in sheets],[2,13])
        p.redo();self.assertEqual([s.columns[1].values[0] for s in sheets],[40,40])

    def test_mpx_formulas_reopen_and_continue_calculating(self):
        p=document();p.assign_formula(1,'C1*2');p.assign_formula(2,'C2+1')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'formulas.mpx';p.save(path)
            q=Presenter();q.load(path);q.set_cell(0,0,'9')
            self.assertEqual([c.values[0] for c in q.worksheet.columns],[9,18,19])

    def test_all_worksheet_failure_restores_earlier_calculated_sheets(self):
        p=document();p.assign_formula(1,'C1*2');p.add_worksheet('Other')
        p.paste(0,0,'1\n2\n');p.assign_formula(1,'1/C1');p.set_automatic_formulas(False)
        p.set_cell(0,0,'0');p.select_worksheet(0);p.set_cell(0,0,'20')
        before=copy.deepcopy(p.native_project.worksheets);undo=len(p._undo_stack)
        with self.assertRaises(ValueError):p.calculate_all_formulas()
        self.assertEqual(p.native_project.worksheets,before);self.assertEqual(len(p._undo_stack),undo)

    def test_dynamic_formatting_follows_formula_and_preserves_manual_color(self):
        p=document();p.assign_formula(1,'C1*20');p.set_cell_highlight([0],[1],'#d4edda')
        p.apply_conditional_formatting(1,'greater_than',50,color='#f8d7da')
        p.set_cell(0,0,'4');self.assertEqual(effective_highlights(p.worksheet.columns[1])['0'],'#f8d7da')
        p.set_cell(0,0,'1');self.assertNotIn('0',effective_highlights(p.worksheet.columns[1]))
        p.clear_conditional_formatting([1]);self.assertEqual(p.worksheet.columns[1].metadata['cell_highlights'],{'0':'#d4edda'})

    def test_invalid_conditional_rule_is_atomic(self):
        p=document();before=copy.deepcopy(p.worksheet)
        with self.assertRaises(ValueError):p.apply_conditional_formatting(0,'between',1,'bad')
        self.assertEqual(p.worksheet,before);self.assertFalse(p.can_undo)


if __name__=='__main__':unittest.main()
