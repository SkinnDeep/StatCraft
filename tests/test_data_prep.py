import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from statcraft.model import Worksheet,Column
from statcraft.app import Presenter
from statcraft import data_prep as d


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.sheet=Worksheet('Runs',[Column('A',values=[1,None,3],metadata={'formula':'C2'}),Column('B',values=[4,5]),Column('Group','text',['x','y','x'])])

    def test_stack_order_lengths_missing_and_no_source_mutation(self):
        before=copy.deepcopy(self.sheet);s=d.stack_columns(self.sheet,[1,0])
        self.assertEqual(s.columns[0].values,[4,5,1,None,3]);self.assertEqual(s.columns[1].values,['B','B','A','A','A'])
        self.assertEqual(s.columns[0].metadata,{});self.assertEqual(self.sheet,before)
        self.assertEqual(d.stack_columns(self.sheet,[0,1],omit_missing=True).columns[0].values,[1,3,4,5])

    def test_typed_stack(self):
        for kind,values in [('date',[45000,None]),('text',['',None])]:
            s=Worksheet('Typed',[Column('A',kind,values),Column('B',kind,values)])
            out=d.stack_columns(s,[0,1]);self.assertEqual(out.columns[0].kind,kind);self.assertEqual(out.columns[0].values,values*2)

    def test_unstack_multiple_response_padding(self):
        s=d.unstack_columns(self.sheet,[0,1],2)
        self.assertEqual(s.headers,['A_x','A_y','B_x','B_y'])
        self.assertEqual([c.values for c in s.columns],[[1,3],[None,None],[4,None],[5,None]])

    def test_unstack_distinguishes_missing_and_blank_groups(self):
        s=Worksheet('Groups',[Column('V',values=[1,2,3]),Column('G','text',[None,'','Missing'])])
        out=d.unstack_columns(s,[0],1,include_missing=True)
        self.assertEqual(len(set(out.headers)),3);self.assertEqual([c.values for c in out.columns],[[1],[2],[3]])
        self.assertEqual(len(d.unstack_columns(s,[0],1).columns),2)

    def test_transpose_padding_and_names(self):
        out=d.transpose(self.sheet,[1,0]);self.assertEqual(out.headers,['Source','Row 1','Row 2','Row 3'])
        self.assertEqual([c.values for c in out.columns],[['B','A'],[4,1],[5,None],[None,3]])

    def test_transpose_dates_preserve_serials(self):
        out=d.transpose(Worksheet('Date',[Column('D','date',[45001,45002])]),[0])
        self.assertEqual(out.columns[1].kind,'date');self.assertEqual(out.columns[1].values,[45001])

    def test_invalid_selection_and_mixed_types(self):
        for fn,args in [(d.stack_columns,(self.sheet,[0,2])),(d.transpose,(self.sheet,[0,2])),(d.stack_columns,(self.sheet,[0,0])),(d.transpose,(self.sheet,[True])),(d.unstack_columns,(self.sheet,[0],0))]:
            with self.assertRaises(ValueError):fn(*args)

    def test_stacking_worksheets_name_union_and_source(self):
        a=Worksheet('One',[Column('ID',values=[1,2]),Column('Date','date',[45000])])
        b=Worksheet('Two',[Column('Group','text',['a']),Column('ID',values=[3])])
        s=d.stack_worksheets([a,b],match='name');self.assertEqual(s.headers,['ID','Date','Group','Source worksheet'])
        self.assertEqual([c.values for c in s.columns],[[1,2,3],[45000,None,None],[None,None,'a'],['One','One','Two']])

    def test_stacking_position_checks_type_and_width(self):
        a=Worksheet('A',[Column('X',values=[1])]);b=Worksheet('B',[Column('Other',values=[2])])
        self.assertEqual(d.stack_worksheets([a,b],source=False).columns[0].values,[1,2])
        b.columns.append(Column('Text','text',['x']))
        with self.assertRaises(ValueError):d.stack_worksheets([a,b])
        with self.assertRaises(ValueError):d.stack_worksheets([a,Worksheet('B',[Column('X','text',['x'])])])

    def test_join_modes_order_and_missing_keys(self):
        a=Worksheet('A',[Column('ID',values=[2,None,1]),Column('A','text',['b','missing','a'])])
        b=Worksheet('B',[Column('ID',values=[1,3,None]),Column('B','text',['one','three','missing'])])
        out=d.merge_worksheets(a,b,0,0,how='full')
        self.assertEqual(out.headers,['ID','A','ID_2','B'])
        self.assertEqual(out.columns[0].values,[2,None,1,None,None]);self.assertEqual(out.columns[3].values,[None,None,'one','three','missing'])
        self.assertEqual(d.merge_worksheets(a,b,0,0,how='inner').columns[0].values,[1])
        self.assertEqual(d.merge_worksheets(a,b,0,0).row_count,3)

    def test_join_rejects_duplicates_without_fanout(self):
        a=Worksheet('A',[Column('ID',values=[1,1])])
        with self.assertRaises(ValueError):d.merge_worksheets(a,a,0,0)

    def test_side_by_side_unequal_lengths(self):
        out=d.merge_worksheets(self.sheet,Worksheet('R',[Column('D','date',[45000])]),how='position')
        self.assertEqual(out.columns[-1].values,[45000,None,None])

    def test_limits_before_output_allocation(self):
        with patch.object(d,'MAX_CELLS',4):
            for fn,args in [(d.stack_columns,(self.sheet,[0,1])),(d.transpose,(self.sheet,[0,1])),(d.unstack_columns,(self.sheet,[0,1],2)),(d.stack_worksheets,([self.sheet,self.sheet],)),(d.merge_worksheets,(self.sheet,self.sheet))]:
                with self.assertRaises(ValueError):fn(*args,**({'how':'position'} if fn is d.merge_worksheets else {}))

    def test_store_owned_mpx_roundtrip_and_source_unchanged(self):
        p=Presenter();p.worksheet=self.sheet;before=copy.deepcopy(self.sheet)
        d.store_prepared(p,d.unstack_columns(self.sheet,[0,1],2));self.assertEqual(p.native_project.worksheets[0],before)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'prep.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual(q.worksheet,p.worksheet);self.assertEqual(len(q.native_project.worksheets),2)

    def test_new_project_is_independent_and_invalid_destination_atomic(self):
        p=Presenter();p.worksheet=self.sheet;sheet=d.transpose(self.sheet,[0,1]);target=d.store_prepared(p,sheet,'project')
        self.assertIsNot(target,p);self.assertIs(p.worksheet,self.sheet);self.assertTrue(target.dirty)
        with self.assertRaises(ValueError):d.store_prepared(p,sheet,'unknown')
        self.assertIsNone(p.native_project)


if __name__=='__main__':unittest.main()
