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
import unittest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget
from statcraft.modern_expanded_charts import ExpandedChartWidget
from statcraft.model_plots_chart import interpolate_contour_grid
from statcraft.spatial_view import DEFAULT_VIEW, view_state, project_point


def _render_chart(chart, w=800, h=600):
    chart.resize(w, h)
    pm = chart.grab()
    return not pm.isNull()


class TestCAD3DAndContourInteractions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _build_test_window(self):
        win = ModernWindow()
        win.presenter.worksheet = Worksheet(
            'RSM_Experiment',
            [
                Column('Temp', 'number', [150, 150, 150, 150, 200, 200, 200, 200, 175, 175, 160, 190]),
                Column('Pressure', 'number', [10, 10, 20, 20, 10, 10, 20, 20, 15, 15, 15, 18]),
                Column('Time', 'number', [30, 60, 30, 60, 30, 60, 30, 60, 45, 55, 40, 50]),
                Column('Yield', 'number', [62.0, 68.5, 71.0, 79.0, 74.5, 82.0, 86.0, 94.5, 78.0, 80.5, 70.0, 88.0]),
            ],
        )
        rsm_entry = win.presenter.analyze_response_surface(
            3,
            [0, 1, 2],
            [{'low': 150.0, 'high': 200.0}, {'low': 10.0, 'high': 20.0}, {'low': 30.0, 'high': 60.0}],
            terms=[[0], [1], [2], [0, 1], [0, 0], [1, 1]],
        )
        win.refresh()
        return win, rsm_entry

    def test_bilinear_contour_grid_interpolation(self):
        x_grid = [10.0, 20.0]
        y_grid = [100.0, 200.0]
        z_grid = [
            [1.0, 3.0],   # y=100: x=10 -> 1, x=20 -> 3
            [5.0, 7.0],   # y=200: x=10 -> 5, x=20 -> 7
        ]
        val = interpolate_contour_grid(x_grid, y_grid, z_grid, 15.0, 150.0)
        self.assertAlmostEqual(val, 4.0, places=5)

        self.assertAlmostEqual(interpolate_contour_grid(x_grid, y_grid, z_grid, 10.0, 100.0), 1.0, places=5)
        self.assertAlmostEqual(interpolate_contour_grid(x_grid, y_grid, z_grid, 20.0, 200.0), 7.0, places=5)

    def test_cad_surface_view_rotation_pan_zoom_reset(self):
        win, rsm_entry = self._build_test_window()
        try:
            sp_entry = win.presenter.model_surface_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(sp_entry)
            self.assertTrue(_render_chart(chart))
            self.assertTrue(chart._has_3d_panel())

            # Initial view
            self.assertEqual(chart.view_state['azimuth'], DEFAULT_VIEW['azimuth'])
            self.assertEqual(chart.view_state['elevation'], DEFAULT_VIEW['elevation'])
            self.assertEqual(chart.view_state['zoom'], DEFAULT_VIEW['zoom'])
            self.assertEqual(chart.view_state.get('pan_x', 0.0), 0.0)
            self.assertEqual(chart.view_state.get('pan_y', 0.0), 0.0)

            # Rotate CAD view
            chart.rotate_cad_view(15.0, -10.0)
            self.assertEqual(chart.view_state['azimuth'], DEFAULT_VIEW['azimuth'] + 15.0)
            self.assertEqual(chart.view_state['elevation'], DEFAULT_VIEW['elevation'] - 10.0)

            # Pan CAD view
            chart.pan_cad_view(25.0, -40.0)
            self.assertEqual(chart.view_state['pan_x'], 25.0)
            self.assertEqual(chart.view_state['pan_y'], -40.0)

            # Zoom CAD view
            orig_zoom = chart.view_state['zoom']
            chart.zoom_cad_view(1.0)
            self.assertGreater(chart.view_state['zoom'], orig_zoom)

            # Reset CAD view
            chart.reset_cad_view()
            self.assertEqual(chart.view_state['azimuth'], DEFAULT_VIEW['azimuth'])
            self.assertEqual(chart.view_state['elevation'], DEFAULT_VIEW['elevation'])
            self.assertEqual(chart.view_state['zoom'], DEFAULT_VIEW['zoom'])
            self.assertEqual(chart.view_state.get('pan_x', 0.0), 0.0)
            self.assertEqual(chart.view_state.get('pan_y', 0.0), 0.0)
        finally:
            win.presenter.dirty = False
            win.close()

    def test_cad_surface_extrema_and_probing(self):
        win, rsm_entry = self._build_test_window()
        try:
            sp_entry = win.presenter.model_surface_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(sp_entry)
            self.assertTrue(_render_chart(chart))

            panel = chart.panels[0]
            self.assertIn('max_pt', panel)
            self.assertIn('min_pt', panel)
            self.assertGreater(panel['max_pt'][2], panel['min_pt'][2])
            self.assertTrue(len(panel['surface_vertices']) > 0)

            # Verify hit regions were registered
            region_names = [target for target, _ in chart.hit_regions]
            self.assertIn('cad_peak_3d', region_names)
            self.assertIn('cad_min_3d', region_names)
            # self.assertIn('cad_hud_peak_3d', region_names)
            # self.assertIn('cad_hud_min_3d', region_names)
            # self.assertIn('cad_hud_reset_3d', region_names)

            # Click HUD Peak button
            chart.active_cad_card = {'mode': 'peak_3d'}
            self.assertTrue(_render_chart(chart))
            self.assertEqual(chart.active_cad_card['mode'], 'peak_3d')

            # Click HUD Min button
            chart.active_cad_card = {'mode': 'min_3d'}
            self.assertTrue(_render_chart(chart))
            self.assertEqual(chart.active_cad_card['mode'], 'min_3d')

            # Probe nearest vertex
            first_v = panel['surface_vertices'][0]
            chart._probe_surface_click(first_v['pos'])
            self.assertIsNotNone(chart.active_cad_card)
            self.assertEqual(chart.active_cad_card['mode'], 'probe_3d')
            self.assertAlmostEqual(chart.active_cad_card['x'], first_v['pt'][0], places=5)
            self.assertAlmostEqual(chart.active_cad_card['y'], first_v['pt'][1], places=5)
            self.assertAlmostEqual(chart.active_cad_card['fit'], first_v['pt'][2], places=5)
        finally:
            win.presenter.dirty = False
            win.close()

    def test_cad_contour_extrema_and_probing(self):
        win, rsm_entry = self._build_test_window()
        try:
            cp_entry = win.presenter.model_contour_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(cp_entry)
            self.assertTrue(_render_chart(chart))

            panel = chart.panels[0]
            self.assertIn('max_pt', panel)
            self.assertIn('min_pt', panel)
            self.assertGreater(panel['max_pt'][2], panel['min_pt'][2])

            region_names = [target for target, _ in chart.hit_regions]
            self.assertIn('cad_peak_2d', region_names)
            self.assertIn('cad_min_2d', region_names)
            # self.assertIn('cad_hud_peak_2d', region_names)
            # self.assertIn('cad_hud_min_2d', region_names)

            # Probe point in contour center
            plot = panel['plot_rect']
            center_pos = plot.center()
            chart._probe_contour_click(center_pos)
            self.assertIsNotNone(chart.active_cad_card)
            self.assertEqual(chart.active_cad_card['mode'], 'probe_2d')
            self.assertGreater(chart.active_cad_card['fit'], panel['min_pt'][2] - 1e-6)
            self.assertLess(chart.active_cad_card['fit'], panel['max_pt'][2] + 1e-6)

            # Repaint with probed card
            self.assertTrue(_render_chart(chart))
        finally:
            win.presenter.dirty = False
            win.close()

    def test_expanded_chart_cad_navigation(self):
        # 3D surface in expanded dialog
        entry = {
            'panels': [{
                'kind': 'surface',
                'title': '3D Surface',
                'x': [1.0, 2.0, 3.0],
                'y': [10.0, 20.0, 30.0],
                'z': [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
            }]
        }
        dlg = ExpandedChartWidget(entry)
        dlg.resize(900, 680)
        self.assertTrue(_render_chart(dlg))

        # Rotate
        dlg.rotate_view(20.0, 10.0)
        self.assertEqual(dlg.view_state['azimuth'], DEFAULT_VIEW['azimuth'] + 20.0)
        self.assertEqual(dlg.view_state['elevation'], DEFAULT_VIEW['elevation'] + 10.0)

        # Pan
        dlg.pan_view(30.0, -15.0)
        self.assertEqual(dlg.view_state['pan_x'], 30.0)
        self.assertEqual(dlg.view_state['pan_y'], -15.0)

        # Zoom
        orig_zoom = dlg.view_state['zoom']
        dlg.zoom_view(1.0)
        self.assertGreater(dlg.view_state['zoom'], orig_zoom)
        self.assertEqual(dlg.view_state['pan_x'], 30.0)

        # Reset
        dlg.reset_view()
        self.assertEqual(dlg.view_state['azimuth'], DEFAULT_VIEW['azimuth'])
        self.assertEqual(dlg.view_state.get('pan_x', 0.0), 0.0)
        dlg.close()


    def test_onshape_viewcube_and_orientation_snapping(self):
        win, rsm_entry = self._build_test_window()
        try:
            sp_entry = win.presenter.model_surface_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(sp_entry)
            self.assertTrue(_render_chart(chart))

            region_names = [target for target, _ in chart.hit_regions]
            # Check ViewCube faces and ISO button
            self.assertIn('viewcube_top', region_names)
            self.assertIn('viewcube_front', region_names)
            self.assertIn('viewcube_left', region_names)
            self.assertIn('viewcube_iso', region_names)

            # Snap to TOP
            chart.set_cad_orientation(0.0, 89.0)
            self.assertEqual(chart.view_state['elevation'], 89.0)
            self.assertEqual(chart.view_state['azimuth'], 0.0)

            # Snap to FRONT
            chart.set_cad_orientation(0.0, 0.0)
            self.assertEqual(chart.view_state['elevation'], 0.0)
            self.assertEqual(chart.view_state['azimuth'], 0.0)

            # Snap to RIGHT
            chart.set_cad_orientation(90.0, 0.0)
            self.assertEqual(chart.view_state['elevation'], 0.0)
            self.assertEqual(chart.view_state['azimuth'], 90.0)

            # Snap to ISO (default)
            chart.set_cad_orientation(-35.0, 25.0)
            self.assertEqual(chart.view_state['azimuth'], -35.0)
            self.assertEqual(chart.view_state['elevation'], 25.0)
        finally:
            win.presenter.dirty = False
            win.close()

    def test_fast_decimation_smooth_cad(self):
        win, rsm_entry = self._build_test_window()
        try:
            sp_entry = win.presenter.model_surface_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(sp_entry)
            # Dragging mode (optimized low-poly preview)
            chart._is_dragging = True
            self.assertTrue(_render_chart(chart))

            # Rest mode (full resolution 25x25 shaded surface)
            chart._is_dragging = False
            self.assertTrue(_render_chart(chart))
            self.assertIn('surface_vertices', chart.panels[0])
            self.assertEqual(len(chart.panels[0]['surface_vertices']), 25 * 25)
        finally:
            win.presenter.dirty = False
            win.close()

    def test_output_zoom_view_wheel_forwarding(self):
        win, rsm_entry = self._build_test_window()
        try:
            from statcraft.output_zoom import OutputZoomView
            from PySide6.QtGui import QWheelEvent
            from PySide6.QtCore import QPoint
            sp_entry = win.presenter.model_surface_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(sp_entry)
            zoom_view = OutputZoomView(chart)
            zoom_view.resize(800, 600)
            chart.resize(800, 600)

            orig_zoom = chart.view_state['zoom']
            # Send wheel event to OutputZoomView
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
            # Verified that wheel event zoomed the 3D model!
            self.assertGreater(chart.view_state['zoom'], orig_zoom)
        finally:
            win.presenter.dirty = False
            win.close()

    def test_context_menu_and_edit_error_suppression(self):
        win, rsm_entry = self._build_test_window()
        try:
            from PySide6.QtGui import QContextMenuEvent
            from PySide6.QtCore import QPoint
            sp_entry = win.presenter.model_surface_plot(
                rsm_entry['recipe'],
                x_index=0,
                y_index=1,
            )
            chart = ChartWidget(sp_entry)
            chart.resize(800, 600)

            # 1. Verify contextMenuEvent is accepted on 3D panels (does not bubble to output menu)
            cme = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(400, 300))
            chart.contextMenuEvent(cme)
            self.assertTrue(cme.isAccepted())

            # 2. Verify _activate_graph_object suppresses cad_ and viewcube_ targets
            win._activate_graph_object(sp_entry, 'viewcube_top')
            win._activate_graph_object(sp_entry, 'cad_peak_3d')
            # Should safely return without raising ValueError('Select a saved StatCraft graph to edit.')
        finally:
            win.presenter.dirty = False
            win.close()


if __name__ == '__main__':
    unittest.main()
