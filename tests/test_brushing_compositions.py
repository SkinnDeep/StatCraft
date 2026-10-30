import copy
import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.recipes import run,columns
from statcraft.brushing import brushable_rows
from statcraft.compositions import validate_composition
from statcraft import session,io


def document():
    p=Presenter();p.worksheet=Worksheet('Data',[
        Column('X',values=[1,2,None,4,5,6,7,8]),Column('Y',values=[2,5,6,9,8,13,None,17]),
        Column('Batch','text',['B','A','B','A','B','A','B','A']),Column('Region','text',['N','N','S','S','N','N','S','S'])])
    return p


class BrushingAndCompositionTests(unittest.TestCase):
    def test_scatter_links_follow_connection_order_and_omitted_rows(self):
        p=document();entry=p.scatter_plot(0,1,'connect_groups',2,order='Increasing Y')
        self.assertEqual(brushable_rows(entry),[1,2,4,5,6,8])
        before=copy.deepcopy(p.worksheet)
        self.assertEqual(p.validate_brushed_rows(entry,[8,1,8]),[1,8]);self.assertEqual(p.worksheet,before)

    def test_simple_scatter_and_expanded_xy_row_links(self):
        p=document();entry=run(p,{'action':'graph','parameters':{'method':'scatter','indices':[0,1],'bins':10}})
        self.assertEqual(brushable_rows(entry),[1,2,4,5,6,8])
        for method in ('line_plot','area_graph','time_series'):
            entry=p.expanded_graph(method,[0,1],group_index=2)
            self.assertEqual(brushable_rows(entry),[1,2,4,5,6,8])

    def test_stale_foreign_and_invalid_rows_rejected(self):
        p=document();entry=p.scatter_plot(0,1)
        for rows in ([3],[999],[True]):
            with self.assertRaises(ValueError):p.validate_brushed_rows(entry,rows)
        with self.assertRaises(ValueError):p.validate_brushed_rows(copy.deepcopy(entry),[1])
        p.set_cell(0,0,'100')
        with self.assertRaisesRegex(ValueError,'current worksheet'):p.validate_brushed_rows(entry,[1])

    def test_aggregate_graphs_never_fabricate_row_links(self):
        p=document();entry=p.expanded_graph('bar_chart',[2])
        self.assertEqual(brushable_rows(entry),[])
        with self.assertRaises(ValueError):p.validate_brushed_rows(entry,[1])

    def test_panel_recipe_dependencies_and_original_row_ids(self):
        p=document();source=p.scatter_plot(0,1,'groups',2)
        panel=p.panel_graph(source['recipe'],[2],source_appearance={'graph_styles':{'p0:s0':{'marker':'diamond'}}})
        self.assertEqual(columns(panel['recipe']),[0,1,2])
        self.assertEqual(panel['result']['by_variables'],['Batch'])
        self.assertEqual([f['label'] for f in panel['result']['facets']],['Batch = A','Batch = B'])
        self.assertEqual(brushable_rows(panel['result']['graphs'][0]),[2,4,6,8])
        self.assertEqual(panel['result']['graphs'][0]['graph_styles']['p0:s0']['marker'],'diamond')
        self.assertFalse(p.result_stale(panel));p.set_cell(0,2,'A');self.assertTrue(p.result_stale(panel))

    def test_two_by_variables_preserve_observed_combinations(self):
        p=document();p.worksheet.columns[0].values[2]=3;p.worksheet.columns[1].values[6]=14
        source=p.scatter_plot(0,1)
        panel=p.panel_graph(source['recipe'],[2,3],shared_x=False,shared_y=True)
        self.assertEqual(panel['result']['count'],4)
        self.assertFalse(panel['result']['shared_x']);self.assertTrue(panel['result']['shared_y'])

    def test_panel_group_styles_follow_labels_and_compositions_format(self):
        from statcraft.compositions import appearance_from_entry
        from statcraft.app import format_entry
        p=document();source=p.scatter_plot(0,1,'groups',2)
        p.update_graph_styles(source,{'p0:s0':{'color':'#aa2244'},'p0:s1':{'color':'#227744'}})
        panel=p.panel_graph(source['recipe'],[2],source_appearance=appearance_from_entry(source))
        self.assertEqual(panel['result']['graphs'][0]['graph_styles']['p0:s0']['color'],'#aa2244')
        self.assertEqual(panel['result']['graphs'][1]['graph_styles']['p0:s0']['color'],'#227744')
        self.assertIn('2 graphs',format_entry(panel))
        self.assertIn('1 graphs',format_entry(p.graph_layout([source],1,2)))

    def test_failed_panel_fit_is_atomic(self):
        p=document();p.worksheet.columns[1].values=[2]*8
        source=run(p,{'action':'graph','parameters':{'method':'histogram','indices':[1],'bins':3}})
        history=list(p.history)
        with self.assertRaises(ValueError):p.panel_graph(source['recipe'],[2],source_appearance={'histogram_settings':{'fit':'Normal'}})
        self.assertEqual(p.history,history)

    def test_layout_snapshots_keep_styles_and_unique_stable_id(self):
        p=document();a=p.scatter_plot(0,1);b=p.expanded_graph('bar_chart',[2])
        p.update_graph_styles(a,{'p0:s0':{'color':'#aabbcc'}})
        layout=p.graph_layout([a,b],1,3,'Chosen graphs');result=layout['result']
        self.assertEqual(result['graphs'][0]['entry_id'],a['entry_id']);self.assertEqual(len(result['graphs']),2)
        p.update_graph_styles(a,{'p0:s0':{'color':'#112233'}})
        self.assertEqual(result['graphs'][0]['graph_styles']['p0:s0']['color'],'#aabbcc')
        with self.assertRaises(ValueError):p.graph_layout([a,copy.deepcopy(a)],1,2)

    def test_edit_layout_undo_restores_grid_and_selection(self):
        p=document();a=p.scatter_plot(0,1);b=p.expanded_graph('bar_chart',[2]);layout=p.graph_layout([a,b],1,2)
        p.update_graph_layout(layout,[b,a],2,1,'Rearranged')
        self.assertEqual(layout['result']['rows'],2);self.assertEqual(layout['result']['graphs'][0]['entry_id'],b['entry_id'])
        p.undo();self.assertEqual(layout['result']['rows'],1);self.assertEqual(layout['result']['graphs'][0]['entry_id'],a['entry_id'])
        p.redo();self.assertEqual(layout['result']['columns'],1)

    def test_mpx_keeps_panels_layout_and_row_ids(self):
        p=document();a=p.scatter_plot(0,1);panel=p.panel_graph(a['recipe'],[2]);layout=p.graph_layout([a,p.expanded_graph('bar_chart',[2])],1,2)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'composed.mpx';p.save(path);q=Presenter();q.load(path)
            saved=next(e for e in q.history if e['result'].get('graph')=='panel_graph')
            self.assertFalse(q.result_stale(saved));rerun=q.rerun_result(saved)
            self.assertEqual(rerun['result']['facets'],saved['result']['facets'])
            restored=next(e for e in q.history if e['result'].get('graph')=='graph_layout')
            self.assertEqual(restored['result']['graphs'][0]['entry_id'],layout['result']['graphs'][0]['entry_id'])
            q.delete_result(next(e for e in q.history if e['entry_id']==a['entry_id']))
            self.assertEqual(len(restored['result']['graphs']),2)

    def test_bad_compositions_and_row_maps_rejected(self):
        p=document();a=p.scatter_plot(0,1);layout=p.graph_layout([a],1,1)
        invalid=copy.deepcopy(layout);invalid['worksheet_id']='sheet';invalid['result']['rows']=0
        with self.assertRaises(io.FormatError):session.validate([invalid],['sheet'])
        invalid=copy.deepcopy(a);invalid.update(worksheet_id='sheet',source_unavailable=42)
        with self.assertRaises(io.FormatError):session.validate([invalid],['sheet'])
        malformed=copy.deepcopy(a);malformed['result']['series'][0]['row_indices']=None
        with self.assertRaises(ValueError):brushable_rows(malformed)
        with self.assertRaises(ValueError):validate_composition({'graph':'panel_graph','graphs':[layout],'columns':1,'shared_x':True,'shared_y':True,'facets':[]})


if __name__=='__main__':unittest.main()
