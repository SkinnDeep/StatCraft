"""Per-gallery native graph edits change appearance, never saved coordinates."""
import copy,json,unittest
from PySide6.QtCore import QEvent,QPointF,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from statcraft.native_graph_view import validate_view,validate_views,resolve_view,cartesian
from statcraft.native_graph_appearance import NativeGraphAppearanceDialog
from statcraft.native_output_chart import NativeOutputChart
from statcraft.graph_presentation import graph_presentation
from statcraft.graph_object_dialog import GraphObjectDialog
from statcraft.graph_options_pane import GraphOptionsPane


def fixture():
    grid={'x':[0.,1.,2.],'y':[0.,1.,2.],'z':[[0.,1.,2.],[1.,4.,5.],[2.,5.,8.]]}
    return {'title':'Saved result','origin':'native','result':{'analysis':'native_saved_output','graphs':[
        {'title':'Native histogram','panels':[{'kind':'histogram','x_label':'Residual','y_label':'Frequency','bounds':[0.,4.,0.,8.], 'series':[{'kind':'histogram','x':[.5,2.5],'y':[3.,7.],'edges':[0.,1.,4.],'color':'#4477aa'}]}]},
        {'title':'Native scatter','panels':[{'kind':'scatter','x_label':'Temperature','y_label':'Yield','series':[{'x':[1.,2.,3.],'y':[3.,4.,5.],'kind':'scatter','color':'#4477aa'}]}]},
        {'title':'Native contour','panels':[{'kind':'contour','grid':grid,'levels':[2.,4.,6.],'x_label':'A','y_label':'B','z_label':'Y'}]},
        {'title':'Native surface','panels':[{'kind':'surface','grid':grid,'x_label':'A','y_label':'B','z_label':'Y'}]},
        {'title':'Native effect curves','panels':[{'kind':'line','x_label':'A','y_label':'Fit','series':[{'x':[0.,1.,2.],'y':[0.,1.,0.],'kind':'line'}]}, {'kind':'line','x_label':'B','y_label':'Fit','series':[{'x':[0.,1.,2.],'y':[1.,0.,1.],'kind':'line'}]}]}
    ]}}


class NativeViewValidation(unittest.TestCase):
    def test_rejects_unknown_or_out_of_range_view_indices(self):
        for key in ('01','-1','100','one','٥'):
            with self.assertRaises(ValueError):validate_views({key:{}})
        with self.assertRaises(ValueError):validate_views({'2':{}},2)
    def test_rejects_invalid_palette_camera_and_overlay_fields(self):
        for value in ({'palette':['#ffffff']},{'palette':['red','blue']},{'camera':{'azimuth':0,'elevation':90,'zoom':1}},{'camera':{'azimuth':0,'elevation':0,'zoom':True}},{'data':[1,2]}):
            with self.assertRaises(ValueError):validate_view(value)
    def test_full_settings_and_styles_remain_detached_json(self):
        entry=fixture();entry['native_graph_views']={'0':{'styles':{'p0:s0':{'fill':'#FF0000'}},'palette':['#000000','#FFFFFF']}}
        before=copy.deepcopy(entry);view=resolve_view(entry,0);view['styles']['p0:s0']['fill']='#00ff00'
        self.assertEqual(entry,before);json.dumps(validate_views(entry['native_graph_views'],5),allow_nan=False)
    def test_gallery_titles_axes_and_overlays_are_independent(self):
        entry=fixture();entry['native_graph_views']={'0':{'presentation':resolve_view(entry,0)['presentation']|{'title':'Edited histogram'}}}
        self.assertEqual(resolve_view(entry,0)['presentation']['title'],'Edited histogram')
        self.assertEqual(resolve_view(entry,1)['presentation']['title'],'Native scatter')
        entry['_native_graph_index']=1;self.assertEqual(graph_presentation(entry)['x_label'],'Temperature')
    def test_probability_and_surface_do_not_advertise_cartesian_scales(self):
        entry=fixture();self.assertTrue(cartesian(entry,0));self.assertFalse(cartesian(entry,3))
        entry['result']['graphs'][1]['panels'][0]['kind']='probability';self.assertFalse(cartesian(entry,1))


class NativeGraphEditing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.entry=fixture();self.chart=NativeOutputChart(self.entry);self.chart.resize(950,650);self.chart.show();self.app.processEvents();self.chart.grab()
    def tearDown(self):self.chart.close();self.chart.deleteLater();self.app.processEvents()
    def overlay(self,index,**values):
        self.entry.setdefault('native_graph_views',{}).setdefault(str(index),{}).update(values);self.chart.update();self.app.processEvents()
    def test_histogram_fill_edit_changes_real_bar_pixels(self):
        old=copy.deepcopy(self.entry['result']);self.overlay(0,styles={'p0:s0':{'fill':'#ff0000','edge':'#990000'}})
        dpr=self.chart.devicePixelRatio();image=self.chart.grab().toImage();path,info=self.chart.hover_regions[0];p=path.boundingRect().center();color=image.pixelColor(int(p.x()*dpr),int(p.y()*dpr))
        self.assertGreater(color.red(),240);self.assertLess(color.blue(),30);self.assertEqual(self.entry['result'],old)
    def test_hidden_series_does_not_leave_hover_or_selection_hits(self):
        self.overlay(0,styles={'p0:s0':{'visible':False}});self.chart.grab()
        self.assertEqual(self.chart.hover_regions,[]);self.assertEqual(self.chart.rendered_primitives,0)
        self.assertFalse(any(target=='p0:s0' for target,path in self.chart.hit_regions))
    def test_scatter_symbol_color_shape_and_size_are_real(self):
        self.chart.select_graph(1);self.overlay(1,styles={'p0:s0':{'color':'#ff0000','marker':'square','marker_size':18}})
        dpr=self.chart.devicePixelRatio();image=self.chart.grab().toImage();region,info=self.chart.hover_regions[1];p=region.boundingRect().center();c=image.pixelColor(int(p.x()*dpr),int(p.y()*dpr))
        self.assertGreater(c.red(),240);self.assertLess(c.blue(),30)
    def test_real_point_click_selects_series_object(self):
        self.chart.select_graph(1);self.chart.grab();region,info=self.chart.hover_regions[1];p=region.boundingRect().center()
        event=QMouseEvent(QEvent.Type.MouseButtonPress,p,QPointF(self.chart.mapToGlobal(p.toPoint())),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.chart,event);self.assertEqual(self.chart.selected_object,'p0:s0')
    def test_object_dialog_accepts_truthful_capabilities_and_style(self):
        self.chart.select_graph(1);dialog=GraphObjectDialog(self.chart.editable_objects(),{},'p0:s0');self.assertTrue(dialog.controls)
        dialog.close();dialog.deleteLater()
    def test_manual_scale_limits_clip_bar_data_and_regenerate_ticks(self):
        p=resolve_view(self.entry,0)['presentation']|{'x_min':0.,'x_max':1.,'y_min':0.,'y_max':4.}
        self.overlay(0,presentation=p);self.chart.grab();panel=self.chart.graphs[0]['panels'][0]
        self.assertEqual(self.chart._bounds(panel),(0.,1.,0.,4.));self.assertEqual(len(self.chart.hover_regions),1)
    def test_grid_visibility_and_label_positions_change_painting(self):
        before=self.chart.grab().toImage();p=resolve_view(self.entry,0)['presentation']|{'grid_enabled':False,'x_label':'New X','x_position':'high','y_position':'off'}
        self.overlay(0,presentation=p);after=self.chart.grab().toImage();self.assertNotEqual(before,after);self.assertEqual(self.chart._axis_label(self.chart.graphs[0]['panels'][0],'x'),'New X')
    def test_gallery_switch_signal_and_persisted_initial_index(self):
        seen=[];self.chart.graphSelected.connect(seen.append);self.chart.select_graph(1);self.assertEqual(seen,[1]);self.assertEqual(self.chart.current_view()['presentation']['title'],'Native scatter')
        entry=fixture();entry['_native_graph_index']=3;other=NativeOutputChart(entry);self.assertEqual(other.graph_index,3);self.assertEqual(other.graph_selector.currentIndex(),3);other.deleteLater()
    def test_palette_and_camera_edits_do_not_mutate_mesh(self):
        original=copy.deepcopy(self.entry['result']);self.chart.select_graph(3);before=self.chart.grab().toImage()
        self.overlay(3,palette=['#ffffff','#ff0000'],camera={'azimuth':60.,'elevation':45.,'zoom':1.4});after=self.chart.grab().toImage()
        self.assertNotEqual(before,after);self.assertEqual(self.chart.surface_camera['azimuth'],60.);self.assertEqual(original,self.entry['result'])
    def test_contour_palette_changes_bands_preserving_primitives(self):
        self.chart.select_graph(2);before=self.chart.grab().toImage();count=self.chart.rendered_primitives
        self.overlay(2,palette=['#ffffff','#ff0000']);after=self.chart.grab().toImage()
        self.assertNotEqual(before,after);self.assertEqual(count,self.chart.rendered_primitives)
    def test_title_only_edit_preserves_each_panel_axis_identity(self):
        self.chart.select_graph(4);p=resolve_view(self.entry,4)['presentation']|{'title':'New effect title'};self.overlay(4,presentation=p)
        self.assertEqual(self.chart._axis_label(self.chart.graphs[4]['panels'][0],'x'),'A');self.assertEqual(self.chart._axis_label(self.chart.graphs[4]['panels'][1],'x'),'B')
    def test_palette_camera_dialog_validation_and_camera_controls(self):
        dialog=NativeGraphAppearanceDialog(self.chart.current_view(),True);dialog.palette.setCurrentText('Heat');dialog.camera['azimuth'].setValue(70.);dialog.validate()
        self.assertTrue(dialog.settings['palette']);self.assertEqual(dialog.settings['camera']['azimuth'],70.);dialog.deleteLater()
    def test_options_pane_scopes_title_and_enables_only_supported_scales(self):
        pane=GraphOptionsPane();self.entry['_native_graph_index']=1;pane.load_entry(self.entry)
        self.assertEqual(pane.controls['title'].text(),'Native scatter');self.assertTrue(pane.controls['x_min'].isEnabled())
        self.entry['_native_graph_index']=3;pane.load_entry(self.entry);self.assertFalse(pane.controls['x_min'].isEnabled());pane.deleteLater()

if __name__=='__main__':unittest.main()
