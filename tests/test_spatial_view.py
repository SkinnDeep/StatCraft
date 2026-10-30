import math
import unittest

from statcraft.spatial_view import camera_point, depth_order, normalize_point, project_point, view_state


class SpatialViewTests(unittest.TestCase):
    def test_known_quarter_turn_changes_horizontal_axis_into_depth(self):
        horizontal, vertical, depth = camera_point((1, 0, 0), view_state(90, 0))
        self.assertAlmostEqual(horizontal, 0)
        self.assertAlmostEqual(vertical, 0)
        self.assertAlmostEqual(depth, 1)
        self.assertEqual(camera_point((0, 0, 1), view_state(0, 0)), (0, 1, 0))

    def test_elevation_preserves_length_and_changes_depth(self):
        result = camera_point((.3, -.8, .5), view_state(43, 62))
        self.assertAlmostEqual(sum(v*v for v in result), .3**2 + .8**2 + .5**2)
        self.assertNotEqual(result, camera_point((.3, -.8, .5), view_state(43, 0)))

    def test_normalization_is_per_axis_and_centers_data(self):
        ranges = ((10, 20), (-1, 1), (100, 500))
        self.assertEqual(normalize_point((15, 0, 300), ranges), (0, 0, 0))
        self.assertEqual(normalize_point((10, 1, 500), ranges), (-1, 1, 1))

    def test_perspective_makes_near_geometry_larger_and_reverses_with_orbit(self):
        ranges = ((-1, 1), (-1, 1), (-1, 1))
        viewport = (0, 0, 800, 600)
        near = project_point((1, 1, 0), ranges, view_state(0, 0), viewport)
        far = project_point((1, -1, 0), ranges, view_state(0, 0), viewport)
        self.assertGreater(near[0] - 400, far[0] - 400)
        self.assertGreater(near[2], far[2])
        points = [(0, -1, 0), (0, 1, 0)]
        self.assertEqual(depth_order(points, ranges, view_state(0, 0)), [0, 1])
        self.assertEqual(depth_order(points, ranges, view_state(180, 0)), [1, 0])

    def test_zoom_scales_about_viewport_center_and_aspect_stays_equal(self):
        ranges = ((-1, 1), (-1, 1), (-1, 1))
        a = project_point((1, 0, 1), ranges, view_state(0, 0, 1), (20, 30, 800, 400))
        b = project_point((1, 0, 1), ranges, view_state(0, 0, 2), (20, 30, 800, 400))
        self.assertAlmostEqual(b[0]-420, 2*(a[0]-420))
        self.assertAlmostEqual(230-b[1], 2*(230-a[1]))
        self.assertAlmostEqual(a[0]-420, 230-a[1])
        self.assertEqual(a[2], b[2])

    def test_cad_pan_translates_projected_coordinates(self):
        ranges = ((-1, 1), (-1, 1), (-1, 1))
        viewport = (20, 30, 800, 400)
        base = project_point((0, 0, 0), ranges, view_state(0, 0, 1), viewport)
        panned = project_point((0, 0, 0), ranges, view_state(0, 0, 1, pan_x=45.0, pan_y=-25.0), viewport)
        self.assertAlmostEqual(panned[0], base[0] + 45.0)
        self.assertAlmostEqual(panned[1], base[1] - 25.0)
        self.assertEqual(panned[2], base[2])

    def test_camera_limits_and_invalid_inputs(self):
        self.assertEqual(view_state(540, 100, 100), {'azimuth': -180, 'elevation': 89, 'zoom': 2.5})
        self.assertEqual(view_state(0, -100, .001)['zoom'], .4)
        for value in (True, float('inf'), float('nan'), '10'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                view_state(zoom=value)
        with self.assertRaises(ValueError):
            normalize_point((0, 0, 0), ((1, 1), (-1, 1), (-1, 1)))
        with self.assertRaises(ValueError):
            project_point((0, 0, 0), ((-1, 1),)*3, view_state(), (0, 0, 0, 100))
        with self.assertRaises(ValueError):
            project_point((0, 10, 0), ((-1, 1),)*3, view_state(0, 0), (0, 0, 100, 100))


if __name__ == '__main__':
    unittest.main()
