import unittest

import cv2
import numpy as np

from src.utils.route_visualization import render_route_visualization


class RouteVisualizationTests(unittest.TestCase):
    def setUp(self):
        self.base = np.zeros((44, 60, 3), dtype=np.uint8)
        cv2.line(self.base, (8, 15), (51, 15), (170, 170, 170), 1)
        cv2.line(self.base, (12, 31), (47, 31), (120, 120, 120), 1)
        self.route = self.base.copy()
        cv2.line(self.route, (10, 15), (45, 15), (0, 0, 255), 1)
        cv2.circle(self.route, (45, 15), 2, (0, 255, 255), -1)
        self.actions = {
            (255, 0, 0): "left none none",
            (255, 255, 0): "none none goal",
        }

    def test_renderer_never_mutates_navigation_images(self):
        base_before = self.base.copy()
        route_before = self.route.copy()

        preview = render_route_visualization(
            self.base,
            self.route,
            self.actions,
            player_position=(20, 15),
            viewport=(8, 8, 30, 20),
            current_command="left none none",
            scale=4,
        )

        np.testing.assert_array_equal(self.base, base_before)
        np.testing.assert_array_equal(self.route, route_before)
        self.assertEqual(preview.ndim, 3)
        self.assertEqual(preview.shape[2], 3)
        self.assertGreater(preview.shape[0], self.base.shape[0])
        self.assertGreater(preview.shape[1], self.base.shape[1])

    def test_route_is_thicker_than_a_nearest_neighbour_copy(self):
        preview = render_route_visualization(
            self.base,
            self.route,
            self.actions,
            scale=4,
            crop=False,
            show_legend=False,
        )
        nearest = cv2.resize(self.route, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
        preview_red = (preview[:, :, 2] > 180) & (preview[:, :, 2] > preview[:, :, 1] * 1.3)
        nearest_red = (nearest[:, :, 2] > 180) & (nearest[:, :, 1] < 50)
        self.assertGreater(np.count_nonzero(preview_red), np.count_nonzero(nearest_red))

    def test_base_map_without_route_can_be_polished(self):
        preview = render_route_visualization(
            self.base,
            scale=3,
            crop=True,
            show_legend=False,
        )
        self.assertGreater(preview.size, 0)
        self.assertFalse(np.all(preview == 0))

    def test_empty_input_returns_placeholder(self):
        preview = render_route_visualization(None, None)
        self.assertEqual(preview.shape, (120, 180, 3))


if __name__ == "__main__":
    unittest.main()
