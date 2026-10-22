import os
import unittest

import cv2
import numpy as np

from src.utils.common import get_mask
from src.utils.image_io import read_image
from src.utils.nametag import (
    find_best_nametag_match,
    parse_nametag_row_bands,
    plate_support,
    prepare_nametag_template,
)


def _cyan_plate(width=76, height=15):
    plate = np.zeros((height, width, 3), dtype=np.uint8)
    plate[:] = (200, 178, 120)
    plate[4:height - 4, 8:width - 8] = (20, 20, 20)
    return plate


def _cms_three_row_template():
    """Synthetic CMS-like stack: cyan name, brown guild, cyan medal."""
    canvas = np.full((64, 111, 3), 40, dtype=np.uint8)
    # Name row (cyan/teal pill)
    canvas[1:21, 26:92] = (200, 178, 120)
    canvas[5:17, 34:84] = (25, 25, 25)
    # Guild row (brown)
    canvas[23:43, 27:85] = (55, 70, 95)
    canvas[27:39, 35:77] = (220, 220, 220)
    # Medal / tag (cyan bar)
    canvas[47:60, 12:110] = (210, 190, 130)
    return canvas


class NametagMatchingTests(unittest.TestCase):
    def test_ignores_duplicate_name_in_top_ui_and_matches_scaled_world_tag(self):
        rng = np.random.default_rng(7)
        template = rng.integers(0, 256, (12, 40, 3), dtype=np.uint8)
        mask = np.full(template.shape[:2], 255, dtype=np.uint8)
        frame = np.full((180, 220, 3), 240, dtype=np.uint8)

        # The party UI contains the same name, but it is outside the world ROI.
        frame[15:27, 150:190] = template
        scaled = cv2.resize(
            template,
            None,
            fx=0.95,
            fy=0.90,
            interpolation=cv2.INTER_AREA,
        )
        frame[105:105 + scaled.shape[0], 55:55 + scaled.shape[1]] = scaled

        match = find_best_nametag_match(
            frame,
            template,
            mask,
            ((0.95, 0.90), (1.0, 1.0)),
            (0, 80, frame.shape[1], frame.shape[0]),
        )

        self.assertIsNotNone(match)
        self.assertEqual(match[0], (55, 105))
        self.assertLess(match[1], 0.001)

    def test_trims_terrain_padding_from_large_screenshot(self):
        # Large frame so prepare_nametag_template crops (tight crops are kept).
        canvas = np.zeros((240, 320, 3), dtype=np.uint8)
        canvas[:] = (70, 140, 190)
        plate = _cyan_plate()
        canvas[80:80 + plate.shape[0], 100:100 + plate.shape[1]] = plate

        trimmed = prepare_nametag_template(canvas)
        self.assertLess(trimmed.shape[0], canvas.shape[0])
        self.assertLess(trimmed.shape[1], canvas.shape[1])
        self.assertGreater(plate_support(trimmed), 0.5)

    def test_tight_three_row_template_kept_as_is(self):
        template = _cms_three_row_template()
        self.assertTrue(template.shape[1] < 200 and template.shape[0] < 120)
        prepared = prepare_nametag_template(template)
        self.assertEqual(prepared.shape, template.shape)
        bands = parse_nametag_row_bands(prepared)
        self.assertIsNotNone(bands["name"])
        self.assertLess(bands["name"][0], bands["name"][1])
        # Guild and/or medal should be detected on the synthetic stack.
        self.assertTrue(bands["guild"] is not None or bands["medal"] is not None)

    def test_name_only_scene_still_matches_full_template(self):
        template = _cms_three_row_template()
        bands = parse_nametag_row_bands(template)
        name_y0, name_y1 = bands["name"]
        name_only = np.full_like(template, 40)
        name_only[name_y0:name_y1] = template[name_y0:name_y1]

        frame = np.full((200, 300, 3), 40, dtype=np.uint8)
        frame[90:90 + name_only.shape[0], 80:80 + name_only.shape[1]] = name_only
        mask = get_mask(template, (0, 255, 0))
        match = find_best_nametag_match(
            frame,
            template,
            mask,
            ((1.0, 1.0),),
            (0, 0, frame.shape[1], frame.shape[0]),
            require_plate=True,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match[0], (80, 90))
        self.assertLess(match[1], 0.15)
        # Returned size is name-row (stable top), not full stack height.
        self.assertEqual(match[2][0], name_y1 - name_y0)

    def test_full_stack_preferred_over_name_only_decoy(self):
        template = _cms_three_row_template()
        bands = parse_nametag_row_bands(template)
        name_y0, name_y1 = bands["name"]
        mask = get_mask(template, (0, 255, 0))

        frame = np.full((220, 320, 3), 40, dtype=np.uint8)
        # Decoy: name row only
        frame[40:40 + (name_y1 - name_y0), 20:20 + template.shape[1]] = template[
            name_y0:name_y1
        ]
        # True: full 3-row stack
        frame[100:100 + template.shape[0], 150:150 + template.shape[1]] = template

        match = find_best_nametag_match(
            frame,
            template,
            mask,
            ((1.0, 1.0),),
            (0, 0, frame.shape[1], frame.shape[0]),
            require_plate=True,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match[0], (150, 100))

    def test_rejects_yellow_terrain_when_cyan_plate_is_required(self):
        plate = _cyan_plate()
        mask = np.full(plate.shape[:2], 255, dtype=np.uint8)
        frame = np.zeros((180, 260, 3), dtype=np.uint8)
        frame[:] = (40, 150, 210)
        frame[40:70, 180:240] = (45, 160, 220)
        frame[110:110 + plate.shape[0], 40:40 + plate.shape[1]] = plate

        match = find_best_nametag_match(
            frame,
            plate,
            mask,
            ((1.0, 1.0),),
            (0, 20, frame.shape[1], frame.shape[0]),
            require_plate=True,
        )

        self.assertIsNotNone(match)
        self.assertEqual(match[0], (40, 110))
        self.assertGreater(plate_support(frame[110:110 + plate.shape[0], 40:40 + plate.shape[1]]), 0.5)

    def test_real_screenshot_locks_onto_character_nameplate(self):
        frame_path = os.path.join(
            "dist", "screenshot", "2026-09-03_23-57-48_img_frame.png"
        )
        tag_path = os.path.join("nametag", "风吹雀雀很凉.png")
        if not os.path.exists(frame_path) or not os.path.exists(tag_path):
            self.skipTest("real nametag fixtures are not present")

        frame = read_image(frame_path, cv2.IMREAD_COLOR)
        template = prepare_nametag_template(read_image(tag_path, cv2.IMREAD_COLOR))
        mask = get_mask(template, (0, 255, 0))
        match = find_best_nametag_match(
            frame,
            template,
            mask,
            ((0.95, 0.90), (1.0, 1.0), (1.05, 1.05)),
            (0, 100, frame.shape[1], 610),
            require_plate=True,
        )

        self.assertIsNotNone(match)
        location, score, size, _scale = match
        roi = frame[location[1]:location[1] + size[0], location[0]:location[0] + size[1]]
        self.assertLess(score, 0.18)
        self.assertGreater(plate_support(roi), 0.4)
        self.assertTrue(480 <= location[0] <= 540)
        self.assertTrue(440 <= location[1] <= 480)

    def test_overlapped_nameplate_is_still_preferred_over_terrain(self):
        frame_path = os.path.join(
            "dist", "screenshot", "2026-09-04_00-01-38_img_frame.png"
        )
        tag_path = os.path.join("nametag", "风吹雀雀很凉.png")
        if not os.path.exists(frame_path) or not os.path.exists(tag_path):
            self.skipTest("real nametag fixtures are not present")

        frame = read_image(frame_path, cv2.IMREAD_COLOR)
        template = prepare_nametag_template(read_image(tag_path, cv2.IMREAD_COLOR))
        mask = get_mask(template, (0, 255, 0))
        match = find_best_nametag_match(
            frame,
            template,
            mask,
            ((0.95, 0.90), (1.0, 1.0), (1.05, 1.05)),
            (0, 100, frame.shape[1], 610),
            require_plate=True,
        )

        self.assertIsNotNone(match)
        location, score, size, _scale = match
        roi = frame[location[1]:location[1] + size[0], location[0]:location[0] + size[1]]
        self.assertGreater(plate_support(roi), 0.28)
        self.assertTrue(640 <= location[0] <= 720)
        self.assertTrue(390 <= location[1] <= 440)

    def test_real_full_template_not_shrunk_by_prepare(self):
        tag_path = None
        for name in os.listdir("nametag"):
            lower = name.lower()
            if not name.endswith(".png"):
                continue
            if any(token in lower for token in ("full", "backup", "example", "from")):
                continue
            tag_path = os.path.join("nametag", name)
            break
        if tag_path is None:
            self.skipTest("nametag fixture missing")
        image = read_image(tag_path, cv2.IMREAD_COLOR)
        if image is None:
            self.skipTest("nametag fixture unreadable")
        if not (image.shape[1] < 200 and image.shape[0] < 120):
            self.skipTest("fixture is not a tight crop")
        prepared = prepare_nametag_template(image)
        self.assertEqual(prepared.shape, image.shape)
        bands = parse_nametag_row_bands(prepared)
        self.assertEqual(bands["name"][0], 0)


if __name__ == "__main__":
    unittest.main()
