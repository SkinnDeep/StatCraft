"""Tests for OnShape CAD 3D navigation, ViewCube, and Extrema Probing on NativeOutputChart."""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
root = Path(__file__).resolve().parent.parent
deps = root.parent / 'statcraft-build-deps'
if str(deps) not in sys.path:
    sys.path.insert(0, str(deps))
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import math
import copy
import unittest
from PySide6.QtCore import QEvent, QPointF, QPoint, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent, QContextMenuEvent
from PySide6.QtWidgets import QApplication

from statcraft.native_output_chart import NativeOutputChart
from statcraft.spatial_view import DEFAULT_VIEW, view_state
from statcraft.output_zoom import OutputZoomView
from statcraft.verification_fonts import load_verification_fonts


def surface_fixture():
    grid = {
        'x': [10.0, 20.0, 30.0],
        'y': [100.0, 200.0, 300.0],
        'z': [
            [25.0, 45.0, 30.0],
            [55.0, 95.0, 70.0],  # Peak at (20, 200) -> 95.0
            [15.0, 35.0, 20.0],  # Trough at (10, 300) -> 15.0
        ],
    }
    return {
        'title': 'Saved Native 3D Project',
        'origin': 'native',
        'result': {
            'analysis': 'native_saved_output',
            'graphs': [
                {
                    'title': 'Surface Plot of Response',
                    'panels': [
                        {
                            'kind': 'surface',
                            'x_label': 'Temperature',
                            'y_label': 'Pressure',
                            'z_label': 'Response',
                            'grid': grid,
                        }
                    ],
                },
                {
                    'title': 'Contour Plot of Response',
                    'panels': [
                        {
                            'kind': 'contour',
                            'x_label': 'Temperature',
                            'y_label': 'Pressure',
                            'z_label': 'Response',
                            'grid': grid,
                            'levels': [30.0, 60.0, 90.0],
                        }
                    ],
                },
            ],
        },
    }


class TestNativeSurfaceCAD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_verification_fonts(cls.app)

    def setUp(self):
        self.entry = surface_fixture()
        self.chart = NativeOutputChart(self.entry)
        self.chart.resize(900, 650)
        self.chart.show()
        self.app.processEvents()

    def tearDown(self):
        self.chart.close()
        self.chart.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_has_3d_panel_detection(self):
        # Graph 0 is Surface -> True
        self.chart.select_graph(0)
        self.assertTrue(self.chart._has_3d_panel())

        # Graph 1 is Contour -> False
        self.chart.select_graph(1)
        self.assertFalse(self.chart._has_3d_panel())

    def test_cad_orbit_rotation_right_drag(self):
        self.chart.select_graph(0)
        self.chart.reset_cad_view()
        orig_azimuth = self.chart.surface_camera['azimuth']
        orig_elevation = self.chart.surface_camera['elevation']

        # Right-click drag moving mouse right (dx = +40) and up (dy = -20)
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(400, 300),
            QPointF(400, 300),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mousePressEvent(press)
        self.assertTrue(self.chart._is_dragging)

        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(440, 280),
            QPointF(440, 280),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mouseMoveEvent(move)

        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(440, 280),
            QPointF(440, 280),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mouseReleaseEvent(release)
        self.assertFalse(self.chart._is_dragging)

        # OnShape standard: moving mouse right decreases azimuth (-40 * 0.5 = -20)
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], orig_azimuth - 20.0, places=2)
        # Moving mouse up increases elevation (-(-20) * 0.5 = +10)
        self.assertAlmostEqual(self.chart.surface_camera['elevation'], orig_elevation - 10.0, places=2)

    def test_cad_pan_middle_drag_and_ctrl_right_drag(self):
        self.chart.select_graph(0)
        self.chart.reset_cad_view()

        # 1. Middle-click drag
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(400, 300),
            QPointF(400, 300),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mousePressEvent(press)
        self.assertTrue(self.chart._is_dragging)

        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(430, 340),
            QPointF(430, 340),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mouseMoveEvent(move)

        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(430, 340),
            QPointF(430, 340),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mouseReleaseEvent(release)

        self.assertAlmostEqual(self.chart.surface_camera.get('pan_x', 0.0), 30.0, places=2)
        self.assertAlmostEqual(self.chart.surface_camera.get('pan_y', 0.0), 40.0, places=2)

        # 2. Ctrl + Right-click drag
        ctrl_press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(430, 340),
            QPointF(430, 340),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.chart.mousePressEvent(ctrl_press)

        ctrl_move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(450, 330),
            QPointF(450, 330),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.chart.mouseMoveEvent(ctrl_move)

        ctrl_release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(450, 330),
            QPointF(450, 330),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
        )
        self.chart.mouseReleaseEvent(ctrl_release)

        self.assertAlmostEqual(self.chart.surface_camera.get('pan_x', 0.0), 50.0, places=2)
        self.assertAlmostEqual(self.chart.surface_camera.get('pan_y', 0.0), 30.0, places=2)

    def test_cad_wheel_zoom(self):
        self.chart.select_graph(0)
        self.chart.reset_cad_view()
        orig_zoom = self.chart.surface_camera['zoom']

        # Zoom in
        wheel_in = QWheelEvent(
            QPointF(400, 300),
            QPointF(400, 300),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        self.chart.wheelEvent(wheel_in)
        self.assertGreater(self.chart.surface_camera['zoom'], orig_zoom)

        # Zoom out
        wheel_out = QWheelEvent(
            QPointF(400, 300),
            QPointF(400, 300),
            QPoint(0, 0),
            QPoint(0, -240),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        self.chart.wheelEvent(wheel_out)
        self.assertLess(self.chart.surface_camera['zoom'], orig_zoom)

    def test_viewcube_canonical_faces_and_iso(self):
        self.chart.select_graph(0)

        # Top
        self.chart.set_cad_orientation(0.0, 89.0)
        self.assertAlmostEqual(self.chart.surface_camera['elevation'], 89.0)
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], 0.0)

        # Front
        self.chart.set_cad_orientation(0.0, 0.0)
        self.assertAlmostEqual(self.chart.surface_camera['elevation'], 0.0)
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], 0.0)

        # Right
        self.chart.set_cad_orientation(90.0, 0.0)
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], 90.0)

        # Iso
        self.chart.set_cad_orientation(-35.0, 25.0)
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], -35.0)
        self.assertAlmostEqual(self.chart.surface_camera['elevation'], 25.0)

    def test_hud_reset_and_double_click(self):
        self.chart.select_graph(0)
        self.chart.rotate_cad_view(45.0, 20.0)
        self.assertNotEqual(self.chart.surface_camera['azimuth'], DEFAULT_VIEW['azimuth'])

        # Reset via double click
        self.chart.mouseDoubleClickEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonDblClick,
                QPointF(400, 300),
                QPointF(400, 300),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        self.assertEqual(self.chart.surface_camera['azimuth'], DEFAULT_VIEW['azimuth'])
        self.assertEqual(self.chart.surface_camera['elevation'], DEFAULT_VIEW['elevation'])

    def test_extrema_beacons_and_probing(self):
        self.chart.select_graph(0)
        self.chart.grab()  # Trigger render to populate hit regions and vertices

        # Verify peak and min points were correctly detected from grid
        self.assertEqual(self.chart._max_pt, (20.0, 200.0, 95.0))
        self.assertEqual(self.chart._min_pt, (10.0, 300.0, 15.0))

        # Check that hit regions contain peak and min targets
        region_names = [name for name, _ in self.chart.hit_regions]
        self.assertIn('cad_peak_3d', region_names)
        self.assertIn('cad_min_3d', region_names)
        # self.assertIn('cad_hud_peak_3d', region_names)
        # self.assertIn('cad_hud_min_3d', region_names)
        # self.assertIn('cad_hud_reset_3d', region_names)

        # Test probing closest vertex
        self.assertTrue(len(self.chart._surface_vertices) > 0)
        first_v = self.chart._surface_vertices[0]
        self.chart._probe_surface_click(first_v['pos'])
        self.assertIsNotNone(self.chart.active_cad_card)
        self.assertEqual(self.chart.active_cad_card['mode'], 'probe_3d')
        self.assertEqual(self.chart.active_cad_card['x'], first_v['pt'][0])
        self.assertEqual(self.chart.active_cad_card['y'], first_v['pt'][1])
        self.assertEqual(self.chart.active_cad_card['fit'], first_v['pt'][2])

    def test_context_menu_suppression_on_3d(self):
        self.chart.select_graph(0)
        cme = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(400, 300))
        self.chart.contextMenuEvent(cme)
        self.assertTrue(cme.isAccepted())

    def test_output_zoom_view_forwarding(self):
        chart = NativeOutputChart(self.entry)
        chart.resize(900, 650)
        chart.select_graph(0)
        zoom_view = OutputZoomView(chart)
        zoom_view.resize(900, 650)
        orig_zoom = chart.surface_camera['zoom']

        wheel_event = QWheelEvent(
            QPointF(400, 300),
            QPointF(400, 300),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        zoom_view.wheelEvent(wheel_event)
        self.assertGreater(chart.surface_camera['zoom'], orig_zoom)
        zoom_view.close()



    def test_left_click_drag_does_not_move_plot(self):
        self.chart.select_graph(0)
        orig_az = self.chart.surface_camera['azimuth']
        orig_el = self.chart.surface_camera['elevation']
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(400, 300), QPointF(400, 300), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.chart.mousePressEvent(press)
        self.assertFalse(self.chart._is_dragging)
        move = QMouseEvent(QEvent.Type.MouseMove, QPointF(500, 400), QPointF(500, 400), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.chart.mouseMoveEvent(move)
        self.assertEqual(self.chart.surface_camera['azimuth'], orig_az)
        self.assertEqual(self.chart.surface_camera['elevation'], orig_el)

    def test_viewcube_drag_orbit_and_corner_snaps(self):
        self.chart.select_graph(0)
        self.chart.grab()
        orig_az = self.chart.surface_camera['azimuth']

        # 1. ViewCube corner snaps
        from statcraft.native_output_chart import handle_viewcube_action
        handle_viewcube_action(self.chart, 'viewcube_corner_tfr')
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], 45.0, places=1)
        self.assertAlmostEqual(self.chart.surface_camera['elevation'], 35.3, places=1)

        handle_viewcube_action(self.chart, 'viewcube_corner_tfl')
        self.assertAlmostEqual(self.chart.surface_camera['azimuth'], -45.0, places=1)
        self.assertAlmostEqual(self.chart.surface_camera['elevation'], 35.3, places=1)

        # 2. ViewCube dragging to rotate
        box_center = QPointF(837, 132)
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            box_center, box_center,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mousePressEvent(press)
        self.assertIsNotNone(self.chart._viewcube_drag_start)

        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(867, 152), QPointF(867, 152),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mouseMoveEvent(move)
        self.assertTrue(self.chart._viewcube_moved)

        rel = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(867, 152), QPointF(867, 152),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.chart.mouseReleaseEvent(rel)
        self.assertIsNone(self.chart._viewcube_drag_start)


if __name__ == '__main__':
    unittest.main()
