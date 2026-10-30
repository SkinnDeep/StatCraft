"""Saved native geometry is visible, selectable and genuinely three-dimensional."""
import copy
import unittest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from statcraft.native_output_chart import NativeOutputChart, _clip_level
from statcraft.verification_fonts import load_verification_fonts


def fixture():
    grid={'x':[0.,1.,2.],'y':[0.,1.,2.],'z':[[0.,1.,2.],[1.,4.,5.],[2.,5.,8.]]}
    return {'title':'Saved native analysis','origin':'native','result':{
        'analysis':'native_saved_output','graphs':[
            {'title':'Contour of yield','panels':[{'kind':'contour','x_label':'Temperature',
                'y_label':'Velocity','z_label':'Yield','grid':grid,'levels':[2.,4.,6.]}]},
            {'title':'Surface of yield','panels':[{'kind':'surface','x_label':'Temperature',
                'y_label':'Velocity','z_label':'Yield','grid':grid}]},
            {'title':'Saved residual plots','columns':2,'panels':[
                {'kind':'scatter','title':'Residuals Versus Fits','series':[{'x':[1,2,3],'y':[-1,0,1],'kind':'scatter'}]},
                {'kind':'histogram','title':'Histogram','series':[{'x':[-1,0,1],'y':[1,4,1],'kind':'histogram'}]},
                {'kind':'probability','title':'Normal Probability','series':[{'x':[-1,0,1],'y':[-1.2,0,1.2],'kind':'scatter'}]},
                {'kind':'line','title':'Order','series':[{'x':[1,2,3],'y':[-1,0,1],'kind':'line'}]}
            ]}
        ]}}


class NativeOutputChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        load_verification_fonts(cls.app)

    def setUp(self):
        self.entry=fixture();self.original=copy.deepcopy(self.entry)
        self.chart=NativeOutputChart(self.entry);self.chart.resize(950,650);self.chart.show();self.app.processEvents()

    def tearDown(self):
        self.chart.close();self.chart.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_contour_uses_saved_mesh_and_renders_nonempty_colored_regions(self):
        pixmap=self.chart.grab()
        self.assertIsNone(self.chart.error)
        self.assertGreater(self.chart.rendered_primitives,8)
        image=pixmap.toImage();colors={image.pixelColor(x,y).name() for x in range(90,700,20) for y in range(130,500,20)}
        self.assertGreaterEqual(len(colors & {'#d4e7ef','#4aa1a3','#a1c450','#e8be43'}),2)
        self.assertEqual(self.entry,self.original)

    def test_gallery_switches_to_every_stored_graph(self):
        self.assertEqual(self.chart.graph_selector.count(),3)
        for index,kind in enumerate(('contour','surface','scatter')):
            self.chart.graph_selector.setCurrentIndex(index);self.app.processEvents();self.chart.grab()
            self.assertEqual(self.chart.graph_index,index)
            self.assertEqual(self.chart.panels[0]['kind'],kind)
            self.assertIsNone(self.chart.error)
            self.assertGreater(self.chart.rendered_primitives,0)

    def test_surface_depth_sort_and_camera_rotation_changes_image_without_changing_data(self):
        self.chart.select_graph(1);self.app.processEvents();before=self.chart.grab().toImage()
        self.assertEqual(self.chart.rendered_primitives,4)
        for kind,pos,buttons in ((QEvent.Type.MouseButtonPress,QPointF(300,260),Qt.MouseButton.RightButton),
                                 (QEvent.Type.MouseMove,QPointF(390,290),Qt.MouseButton.RightButton),
                                 (QEvent.Type.MouseButtonRelease,QPointF(390,290),Qt.MouseButton.NoButton)):
            event=QMouseEvent(kind,pos,QPointF(self.chart.mapToGlobal(pos.toPoint())),Qt.MouseButton.RightButton,buttons,Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(self.chart,event)
        self.app.processEvents();after=self.chart.grab().toImage()
        self.assertNotEqual(before,after)
        self.assertNotEqual(self.chart.surface_camera['azimuth'],-35.)
        self.assertEqual(self.entry,self.original)

    def test_native_polygons_can_render_without_grid(self):
        panel=self.chart.graphs[0]['panels'][0];panel.pop('grid');panel['polygons']=[{'x':[0,2,2,0],'y':[0,0,2,2],'color':'#1f8a70'}]
        self.chart.grab();self.assertIsNone(self.chart.error);self.assertEqual(self.chart.rendered_primitives,1)
        self.assertEqual(self.chart.grab().toImage().pixelColor(250,250).name(),'#1f8a70')

    def test_export_contract_supports_appearance_without_rerun_claim(self):
        self.assertTrue(self.chart.editable_objects());self.assertNotIn('recipe',self.entry)
        self.assertIn(self.chart.graph_selector,self.chart.export_controls)
        self.chart._exporting=True;self.chart.grab();self.assertIsNone(self.chart.error)
        self.assertNotIn('recipe',self.entry)

    def test_contour_clipping_interpolates_stored_vertices_at_requested_level(self):
        clipped=_clip_level([(0.,0.,0.),(2.,0.,2.),(0.,2.,2.)],1.,True)
        self.assertTrue(all(v[2]>=1. for v in clipped))
        self.assertIn((1.,0.,1.),clipped);self.assertIn((0.,1.,1.),clipped)

    def test_native_horizontal_bars_and_histogram_edges_use_saved_dimensions(self):
        self.chart.graphs=[{'title':'Saved effects','panels':[{'kind':'bar','horizontal':True,
            'bounds':[0.,12.,0.,6.],'x_ticks':[0.,4.,8.,12.], 'x_label':'Term','y_label':'Effect',
            'series':[{'kind':'bar','x':[1.,3.,5.],'y':[3.,6.,11.],'categories':['AB','B','A'],'bar_width':1.2}]}]}]
        self.chart.select_graph(0);self.chart.grab()
        self.assertIsNone(self.chart.error);self.assertEqual(self.chart.rendered_primitives,3)
        panel=self.chart.graphs[0]['panels'][0]
        panel.update(kind='histogram',horizontal=False,bounds=[0.,4.,0.,8.])
        panel['series']=[{'kind':'histogram','x':[.5,2.5],'y':[3.,7.],'edges':[0.,1.,4.]}]
        self.chart.grab();self.assertIsNone(self.chart.error);self.assertEqual(self.chart.rendered_primitives,2)

    def test_surface_rotation_uses_selected_graph_even_after_frame_panel_snapshot(self):
        self.chart.select_graph(1);self.chart.panels=[{'kind':'snapshot'}]
        event=QMouseEvent(QEvent.Type.MouseButtonPress,QPointF(250,250),QPointF(250,250),Qt.MouseButton.RightButton,Qt.MouseButton.RightButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.chart,event)
        self.assertIsNotNone(self.chart._rotate_start)


if __name__=='__main__':unittest.main()
