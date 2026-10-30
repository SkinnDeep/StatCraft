"""Real painted-element data readouts, not nearest-axis guesses."""
import copy
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent,QPointF,QRectF,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication,QToolTip
from statcraft.modern_charts import ChartWidget
from statcraft.modern_expanded_charts import ExpandedChartWidget
from statcraft.native_output_chart import NativeOutputChart
from statcraft.histogram_graphs import build_histograms
from statcraft.model import Worksheet,Column
from statcraft.graph_hover import histogram_info

class DataHoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.widgets=[]
    def tearDown(self):
        QToolTip.hideText()
        for w in self.widgets:w.close();w.deleteLater()
        self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()
    def chart(self,entry,cls=ChartWidget):
        w=cls(entry);self.widgets.append(w);w.resize(900,620);w.show();self.app.processEvents();w.grab()
        self.assertIsNone(w.error)
        return w
    def basic(self):
        return {'title':'Histogram','result':{'graph':'histogram','graph_data':[[0.,1.,2.],[3.,3.]],'histogram_source':[0.,.1,.9,1.,1.9,2.], 'xlabel':'Strength','ylabel':'Frequency'}}
    def region(self,w,kind=None):
        return next((path,info) for path,info in w.hover_regions if kind is None or info['kind']==kind)
    def test_basic_bin_readout_reports_exact_bounds_and_count(self):
        w=self.chart(self.basic());path,info=self.region(w)
        got=w.hover_info_at(path.boundingRect().center())
        self.assertEqual(got['interval'],(0.,1.));self.assertEqual(got['value'],3.)
        self.assertEqual(got['count'],3);self.assertIn('Frequency: 3',got['text']);self.assertIn('N: 6',got['text'])
    def test_final_endpoint_belongs_to_last_histogram_bin(self):
        w=self.chart(self.basic());last=w.hover_regions[-1][1]
        self.assertEqual(last['interval'],(1.,2.));self.assertEqual(last['count'],3)
    def test_blank_margin_has_no_fabricated_data(self):
        w=self.chart(self.basic());self.assertIsNone(w.hover_info_at(QPointF(2,2)));self.assertEqual(w.hover_text_at(QPointF(2,2)),'')
    def test_real_mouse_move_shows_tooltip_and_miss_clears_it(self):
        w=self.chart(self.basic());path,info=self.region(w);pos=path.boundingRect().center()
        with patch('statcraft.graph_interaction.QToolTip.showText') as show,patch('statcraft.graph_interaction.QToolTip.hideText') as hide:
            event=QMouseEvent(QEvent.Type.MouseMove,pos,QPointF(w.mapToGlobal(pos.toPoint())),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(w,event);self.assertTrue(show.called);self.assertIn('Lower boundary: 0',show.call_args[0][1])
            miss=QMouseEvent(QEvent.Type.MouseMove,QPointF(2,2),QPointF(2,2),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(w,miss);self.assertTrue(hide.called);self.assertEqual(w._hover_text,'')
    def test_group_percent_bins_use_raw_group_counts_and_row_identities(self):
        ws=Worksheet(columns=[Column('Strength',values=[0.,.1,1.8,2.]),Column('Group','text',['A','A','B','B'])])
        r=build_histograms(ws,[0],variant='groups',group_index=1,settings={'bins':2,'scale':'Percent'})
        w=self.chart({'title':'Groups','result':r})
        a=next(info for _,info in w.hover_regions if info['series']=='A')
        self.assertEqual(a['measure'],'Percent');self.assertEqual(a['value'],100.)
        self.assertEqual(a['count'],2);self.assertEqual(a['rows'],[1,2]);self.assertIn('Series: A',a['text'])
    def test_density_and_cumulative_measures_are_not_mislabeled_counts(self):
        for scale,cumulative in [('Density',False),('Percent',True)]:
            ws=Worksheet(columns=[Column('Strength',values=[0.,.1,1.8,2.])])
            r=build_histograms(ws,[0],settings={'bins':2,'scale':scale,'cumulative':cumulative})
            w=self.chart({'title':'Scale','result':r});infos=[v for _,v in w.hover_regions]
            self.assertEqual(infos[-1]['count'],2);self.assertEqual(infos[-1]['measure'],('Cumulative ' if cumulative else '')+scale)
            self.assertNotEqual(infos[-1]['value'],infos[-1]['count'])
    def test_scatter_hover_retains_column_names_group_and_actual_row(self):
        e={'title':'Scatter','result':{'graph':'scatter','xlabel':'Temperature','ylabel':'Yield','series':[{'x':[1.,2.],'y':[3.,4.],'label':'Treatment A','connect':False,'fit':None,'row_indices':[5,9]}]}}
        w=self.chart(e);path,info=self.region(w,'point')
        self.assertEqual(info['row'],5);self.assertEqual(info['series'],'Treatment A');self.assertIn('Temperature: 1',info['text']);self.assertIn('Yield: 3',info['text'])
    def test_hidden_series_has_no_hover_targets(self):
        e=self.basic();e['graph_styles']={'p0:bars':{'visible':False}}
        w=self.chart(e);self.assertEqual(w.hover_regions,[])
    def test_resize_rebuilds_hit_regions_from_current_geometry(self):
        w=self.chart(self.basic());before=self.region(w)[0].boundingRect()
        w.resize(1200,750);self.app.processEvents();w.grab();after=self.region(w)[0].boundingRect()
        self.assertGreater(after.width(),before.width());self.assertGreater(after.height(),before.height())
        self.assertEqual(w.hover_info_at(after.center())['interval'],(0.,1.))
    def test_export_omits_hover_regions_and_balloon_then_restores(self):
        w=self.chart(self.basic());self.assertTrue(w.hover_regions)
        w._exporting=True;w.grab();self.assertEqual(w.hover_regions,[]);self.assertIsNone(w.hover_info_at(QPointF(300,300)))
        w._exporting=False;w.grab();self.assertTrue(w.hover_regions)
    def native(self):
        return {'title':'Saved graph','origin':'native','result':{'analysis':'native_saved_output','graphs':[
            {'title':'Saved histogram','panels':[{'kind':'histogram','x_label':'Residual','y_label':'Frequency','series':[{'kind':'histogram','x':[.5,2.5],'y':[3.,7.],'edges':[0.,1.,4.]}]}]},
            {'title':'Saved scatter','panels':[{'kind':'scatter','x_label':'Fit','y_label':'Residual','series':[{'kind':'scatter','x':[1.,2.],'y':[3.,4.]}]}]}]}}
    def test_native_histogram_uses_saved_unequal_edges_without_inventing_rows(self):
        w=self.chart(self.native(),NativeOutputChart);infos=[v for _,v in w.hover_regions]
        self.assertEqual(infos[-1]['interval'],(1.,4.));self.assertEqual(infos[-1]['value'],7.)
        self.assertNotIn('row',infos[-1]);self.assertNotIn('rows',infos[-1]);self.assertNotIn('count',infos[-1])
    def test_native_gallery_switch_immediately_invalidates_old_hits(self):
        w=self.chart(self.native(),NativeOutputChart);self.assertTrue(w.hover_regions)
        w.select_graph(1);self.assertEqual(w.hover_regions,[]);self.app.processEvents();w.grab()
        self.assertTrue(all(v['kind']=='point' for _,v in w.hover_regions));info=w.hover_regions[0][1]
        self.assertIsNone(info['row']);self.assertIn('Fit: 1',info['text'])
    def test_native_mouse_data_uses_display_percent_not_normal_score(self):
        e=self.native();e['result']['graphs']=[{'title':'Probability','panels':[{'kind':'probability','x_label':'Residual','y_label':'Percent','series':[{'kind':'scatter','x':[1.,2.],'y':[0.,1.]}]}]}]
        w=self.chart(e,NativeOutputChart);info=w.hover_regions[0][1]
        self.assertEqual(info['y'],50.);self.assertIn('Percent: 50',info['text'])
    def test_expanded_xy_and_bubble_readouts(self):
        e={'title':'Bubble','result':{'graph':'expanded','panels':[{'kind':'xy','x_label':'Temperature','y_label':'Yield','series':[{'name':'Group A','points':[[1,2,3],[2,3,4]],'row_indices':[4,8]}]}]}}
        w=self.chart(e,ExpandedChartWidget);info=w.hover_regions[0][1]
        self.assertEqual(info['row'],4);self.assertEqual(info['size'],3);self.assertIn('Size: 3',info['text'])
    def test_expanded_3d_points_report_actual_xyz(self):
        e={'title':'3D','result':{'graph':'expanded','panels':[{'kind':'xyz','points':[[1,2,3],[2,4,6]],'axes':['Temp','Pressure','Yield']}]}}
        w=self.chart(e,ExpandedChartWidget);self.assertTrue(w.hover_regions);info=w.hover_regions[0][1]
        self.assertIn(info['z'],(3,6));self.assertIn('Yield:',info['text'])
    def test_overlapping_regions_choose_frontmost_element(self):
        w=self.chart(self.basic());w.reset_hover_regions();rect=QRectF(40,40,20,20)
        w.remember_hover(rect,{'kind':'bar','text':'Back'},clip=QRectF(0,0,100,100));w.remember_hover(rect,{'kind':'bar','text':'Front'},clip=QRectF(0,0,100,100))
        self.assertEqual(w.hover_text_at(QPointF(50,50)),'Front')
    def test_hover_rectangles_are_clipped_to_visible_plot(self):
        w=self.chart(self.basic());w.reset_hover_regions();w.remember_hover(QRectF(0,0,50,50),{'text':'Data'},clip=QRectF(20,20,20,20))
        self.assertIsNone(w.hover_info_at(QPointF(10,10)));self.assertEqual(w.hover_text_at(QPointF(30,30)),'Data')

    def test_native_contour_hover_reports_actual_saved_band(self):
        e=self.native();e['result']['graphs']=[{'title':'Contour','panels':[{'kind':'contour','z_label':'Yield','levels':[10.,20.],'colors':['#112233','#445566','#778899'],'polygons':[{'x':[0,1,1,0],'y':[0,0,1,1],'color':'#445566'}]}]}]
        w=self.chart(e,NativeOutputChart);info=w.hover_regions[0][1]
        self.assertEqual(info['level_range'],(10.,20.));self.assertIn('Yield: 10 to 20',info['text'])
    def test_native_surface_hover_reports_saved_cell_ranges_without_refit(self):
        grid={'x':[0.,1.],'y':[1.,2.],'z':[[10.,20.],[30.,40.]]}
        e=self.native();e['result']['graphs']=[{'title':'Surface','panels':[{'kind':'surface','x_label':'Temp','y_label':'Velocity','z_label':'Yield','grid':grid}]}]
        before=copy.deepcopy(e);w=self.chart(e,NativeOutputChart);info=w.hover_regions[0][1]
        self.assertEqual(info['ranges'],[(0.,1.),(1.,2.),(10.,40.)]);self.assertIn('Saved mesh cell',info['text']);self.assertEqual(e,before)
    def test_basic_boxplot_hover_reports_real_five_number_summary(self):
        e={'title':'Box','result':{'graph':'boxplot','data':{'low':1.,'q1':2.,'median':3.,'q3':4.,'high':5.,'outliers':[]}}}
        w=self.chart(e);info=w.hover_regions[0][1]
        self.assertEqual(info['kind'],'boxplot');self.assertIn('median: 3',info['text'])
    def test_heatmap_hover_has_exact_cell_coordinates_and_value(self):
        e={'title':'Heatmap','result':{'graph':'expanded','panels':[{'kind':'heatmap','values':[[1,2],[3,4]],'x_labels':['A','B'],'y_labels':['C','D']}]}}
        w=self.chart(e,ExpandedChartWidget);info=w.hover_regions[-1][1]
        self.assertEqual(info['value'],4);self.assertIn('Column: B',info['text']);self.assertIn('Row: D',info['text'])
    def test_pie_hover_has_category_value_and_percentage(self):
        e={'title':'Pie','result':{'graph':'expanded','panels':[{'kind':'pie','values':[1,3],'categories':['A','B']}]}}
        w=self.chart(e,ExpandedChartWidget);info=w.hover_regions[-1][1]
        self.assertIn('Category: B',info['text']);self.assertIn('Percent: 75',info['text'])
    def test_interval_hover_has_exact_mean_and_bounds(self):
        e={'title':'Intervals','result':{'graph':'expanded','panels':[{'kind':'intervals','items':[{'name':'Group A','mean':3.,'lower':2.,'upper':4.}]}]}}
        w=self.chart(e,ExpandedChartWidget);info=w.hover_regions[0][1]
        self.assertIn('Mean: 3',info['text']);self.assertIn('Lower: 2',info['text']);self.assertIn('Upper: 4',info['text'])
    def test_dotplot_hover_reports_original_value_and_row(self):
        from statcraft.dotplot_graphs import build_dotplots
        ws=Worksheet(columns=[Column('Strength',values=[0.,.001,1.,2.])])
        r=build_dotplots(ws,response_indices=[0]);w=self.chart({'title':'Dotplot','result':r})
        info=next(v for _,v in w.hover_regions if v['row']==2)
        self.assertEqual(info['value'],.001);self.assertIn('Strength: 0.001',info['text'])
    def test_individual_value_hover_keeps_real_row_identity(self):
        from statcraft.categorical_points import build_points
        ws=Worksheet(columns=[Column('Strength',values=[1.,2.,3.])])
        r=build_points(ws,response_indices=[0]);w=self.chart({'title':'Individual','result':r})
        info=next(v for _,v in w.hover_regions if v.get('row')==2)
        self.assertEqual(info['y'],2.);self.assertIn('Row: 2',info['text'])
    def test_group_boxplot_hover_reports_group_n_and_quartiles(self):
        from statcraft.boxplot_graphs import build_boxplots
        ws=Worksheet(columns=[Column('Strength',values=[1.,2.,3.,4.])])
        r=build_boxplots(ws,response_indices=[0]);w=self.chart({'title':'Boxplot','result':r})
        info=next(v for _,v in w.hover_regions if v['kind']=='boxplot')
        self.assertIn('N: 4',info['text']);self.assertIn('median: 2.5',info['text'])

    def test_layout_children_receive_hover_but_not_edit_clicks(self):
        from statcraft.graph_composite import GraphCompositeWidget
        from statcraft.graph_layouts import build_layout
        w=GraphCompositeWidget({'title':'Layout','result':build_layout([self.basic()],1,1)});self.widgets.append(w)
        w.resize(1000,700);w.show();self.app.processEvents();w.grab();child=w.frames[0].chart
        self.assertFalse(child.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        path,info=child.hover_regions[0];pos=path.boundingRect().center()
        event=QMouseEvent(QEvent.Type.MouseMove,pos,QPointF(child.mapToGlobal(pos.toPoint())),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(child,event);self.assertIn('Frequency: 3',child._hover_text)
        click=QMouseEvent(QEvent.Type.MouseButtonPress,pos,QPointF(child.mapToGlobal(pos.toPoint())),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(child,click);self.assertIsNone(child.selected_object)
    def test_production_hover_acceptance_path(self):
        from statcraft.chart_hover_smoke import verify_chart_hover
        verify_chart_hover(self.app,None,None,'work',lambda value:None)

if __name__=='__main__':unittest.main()

