import unittest

import numpy as np

from src.utils.common import (
    get_all_other_player_locations_on_minimap,
    get_minimap_loc_size,
    get_player_location_on_minimap,
)


class MinimapDetectionTests(unittest.TestCase):
    def test_player_dot_coordinates_are_averaged_across_opencv_shapes(self):
        minimap = np.zeros((20, 24, 3), dtype=np.uint8)
        player_color = (136, 255, 255)
        minimap[8:10, 12:14] = player_color

        location = get_player_location_on_minimap(minimap, player_color)

        self.assertEqual(location, (12, 8))

    def test_other_player_points_support_opencv_flat_coordinate_shape(self):
        minimap = np.zeros((12, 16, 3), dtype=np.uint8)
        minimap[4:6, 7:9] = (0, 0, 255)

        locations = get_all_other_player_locations_on_minimap(minimap)

        self.assertEqual(set(locations), {(7, 4), (8, 4), (7, 5), (8, 5)})

    def test_near_white_compact_minimap_frame_is_detected(self):
        frame = np.zeros((240, 360, 3), dtype=np.uint8)
        frame[10:100, 8:138] = (244, 244, 244)
        frame[11:99, 9:137] = (20, 30, 40)

        result = get_minimap_loc_size(frame)

        self.assertEqual(result, (9, 11, 128, 88))

    def test_player_marker_uses_largest_compact_component(self):
        minimap = np.zeros((40, 60, 3), dtype=np.uint8)
        minimap[8, 8:10] = (0, 255, 255)  # decorative noise, too small
        minimap[20:23, 31:34] = (0, 255, 255)

        location = get_player_location_on_minimap(minimap, (0, 255, 255))

        self.assertEqual(location, (32, 21))



    def test_right_side_quest_panel_is_rejected(self):
        # Real minimap top-left + a tall white quest/task panel on the right
        # (repro of false locate at ~x=966 on 1296-wide CMS frames).
        frame = np.zeros((700, 1296, 3), dtype=np.uint8)
        # Real compact minimap
        frame[10:100, 8:138] = (244, 244, 244)
        frame[11:99, 9:137] = (20, 30, 40)
        # Tall right-side UI panel that previously won CC order
        frame[100:310, 960:1140] = (244, 244, 244)
        frame[101:309, 961:1139] = (40, 50, 60)

        result = get_minimap_loc_size(frame)

        self.assertIsNotNone(result)
        x, y, w, h = result
        self.assertLess(x, 200)
        self.assertLess(y, 150)
        self.assertLess(w, 220)
        self.assertLess(h, 160)
        self.assertNotEqual((x, y, w, h), (961, 101, 178, 208))

    def test_oversized_wrong_aspect_topleft_rejected_keeps_real(self):
        frame = np.zeros((700, 1296, 3), dtype=np.uint8)
        frame[10:100, 8:138] = (244, 244, 244)
        frame[11:99, 9:137] = (20, 30, 40)
        # Oversized tall panel also in left half but too tall/wrong aspect
        frame[120:340, 20:200] = (244, 244, 244)
        frame[121:339, 21:199] = (30, 30, 30)

        result = get_minimap_loc_size(frame)
        self.assertEqual(result, (9, 11, 128, 88))

if __name__ == "__main__":
    unittest.main()
