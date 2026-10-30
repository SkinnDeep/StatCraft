"""Actual Presenter, saved project, source-edit and ModernWindow regression paths."""
import math
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft.recipes import columns
from statcraft.brushing import brushable_rows


def presenter():
    p=Presenter()
    p.worksheet=Worksheet('Attribute Data',[
        Column('Defects',values=[4,1,None,3,2,5,2,1]),
        Column('Inspected',values=[47,39,50,55,42,67,44,40]),
        Column('Area',values=[2.4,2.1,2.6,2.2,2.8,2.5,2.3,2.4]),
        Column('Label','text',['A','B','C','A','B','C','A','A'])])
    return p


class AttributeCapabilityWorkflowTests(unittest.TestCase):
    def test_move_rename_save_load_rerun_both_methods(self):
        for method,size_index in [('binomial',1),('poisson',2)]:
            with self.subTest(method=method),scratch() as tmp:
                p=presenter();entry=p.attribute_capability(method,0,size_index=size_index)
                original=entry['result']
                p.insert_columns(0)
                p.move_columns([1],'after_last')
                for index in range(len(p.worksheet.columns)):p.rename_column(index,'Renamed '+str(index+1))
                expected=p.rerun_result(entry)['result']
                self.assertEqual(original['rates'],expected['rates'])
                path=Path(tmp)/'capability.mpx';p.save(path)
                q=Presenter();q.load(path)
                self.assertEqual(len(q.history),2)
                for saved in list(q.history):
                    rerun=q.rerun_result(saved)['result']
                    self.assertEqual(original['rates'],rerun['rates'])
                    self.assertEqual(original['rate_ci'],rerun['rate_ci'])
                    self.assertEqual(original['omitted_rows'],rerun['omitted_rows'])

    def test_constant_size_has_one_dependency_and_no_phantom_column(self):
        p=presenter();entry=p.attribute_capability('binomial',0,sample_size=100,size_index=None)
        self.assertEqual(columns(entry['recipe']),[0])
        p.delete_columns([1,2,3])
        self.assertEqual(entry['result']['rates'],p.rerun_result(entry)['result']['rates'])

    def test_delete_source_then_undo(self):
        p=presenter();entry=p.attribute_capability('binomial',0,size_index=1)
        p.delete_columns([1])
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(entry)
        p.undo()
        self.assertEqual(entry['result']['rate_ci'],p.rerun_result(entry)['result']['rate_ci'])

    def test_brushing_retains_aligned_source_rows_and_rejects_missing_row(self):
        p=presenter();entry=p.attribute_capability('poisson',0,size_index=2)
        self.assertEqual(brushable_rows(entry),[1,2,4,5,6,7,8])
        self.assertEqual(p.validate_brushed_rows(entry,[1,4]),[1,4])
        with self.assertRaises(ValueError):p.validate_brushed_rows(entry,[3])

    def test_show_graphs_false_is_saved_and_rerun_without_graph(self):
        p=presenter();entry=p.attribute_capability('binomial',0,sample_size=100,options={'show_graphs':False})
        self.assertNotIn('graph',entry['result'])
        self.assertNotIn('graph',p.rerun_result(entry)['result'])


class LateAnalysisRealWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from statcraft.verification_fonts import load_verification_fonts
        cls.app=QApplication.instance() or QApplication([])
        load_verification_fonts(cls.app)

    def test_all_late_families_route_to_actual_chart_widgets(self):
        from statcraft.modern_app import ModernWindow
        p=Presenter()
        p.worksheet=Worksheet('Late Analyses',[
            Column('Measure',values=[10+math.sin(i)*.8+i*.02 for i in range(24)]),
            Column('Second',values=[20+math.cos(i*.6)+math.sin(i)*.3 for i in range(24)]),
            Column('Group',values=[i//4+1 for i in range(24)]),
            Column('Defect','text',['Chip','Burr','Crack','Chip']*6),
            Column('Counts',values=[1,2,3,1,4,2]*4),
            Column('Exposure',values=[20]*24)])
        entries=[
            (p.imr_chart(settings={'variables':[0]}),'IMRChartWidget'),
            (p.attribute_control_chart(settings={'chart_type':'P','variables':[4],'is_subgroup_col':True,'subgroup_col_idx':5}),'AttributeControlChartWidget'),
            (p.time_weighted_control_chart(settings={'chart_type':'EWMA','columns':['Measure'],'subgroup_spec':1}),'TimeWeightedControlChartWidget'),
            (p.rare_event_control_chart(settings={'chart_type':'G','columns':['Counts']}),'RareEventControlChartWidget'),
            (p.multivariate_control_chart(settings={'chart_type':'TSQUARED','variables':['Measure','Second'],'subgroup_size':1}),'MultivariateControlChartWidget'),
            (p.pareto_chart(settings={'defect_column':'Defect','is_summarized':True,'count_column':'Counts'}),'ParetoChartWidget'),
            (p.type1_gage(0,10,settings={'tolerance_val':10}),'Type1GageChartWidget'),
            (p.tolerance_intervals(settings={'variable_indices':[0]}),'ToleranceIntervalChartWidget'),
            (p.attribute_capability('binomial',4,size_index=5),'AttributeCapabilityChartWidget')]
        w=ModernWindow(p);w.resize(1280,900);w.show()
        try:
            for entry,expected in entries:
                with self.subTest(expected=expected):
                    w.show_result(entry);self.app.processEvents()
                    chart=w._active_chart_widget
                    self.assertIsNotNone(chart)
                    self.assertEqual(type(chart).__name__,expected)
                    self.assertFalse(chart.grab().isNull())
                    self.assertEqual(w.result_tabs.tabText(w.result_tabs.currentIndex()),'Graph')
                    if entry['result']['analysis']=='attribute_capability':
                        from PySide6.QtWidgets import QTableWidget
                        report_index=next(i for i in range(w.result_tabs.count()) if w.result_tabs.tabText(i)=='Report')
                        report_text=' '.join(table.item(row,col).text() for table in w.result_tabs.widget(report_index).content.findChildren(QTableWidget) for row in range(table.rowCount()) for col in range(table.columnCount()) if table.item(row,col))
                        self.assertIn('95% confidence interval',report_text)
                        self.assertNotIn('Count Index',report_text)
                        self.assertNotIn('Size Index',report_text)

        finally:
            p.dirty=False;p._results_dirty=False;w.close()


if __name__=='__main__':unittest.main()
