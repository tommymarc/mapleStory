import os
import tempfile
import unittest

import cv2
import numpy as np

from src.utils.monster_templates import (
    load_monster_template,
    select_monster_template_files,
)


class MonsterTemplateTests(unittest.TestCase):
    def test_rgba_template_uses_alpha_and_crops_transparent_border(self):
        image = np.zeros((12, 14, 4), dtype=np.uint8)
        image[3:9, 4:11, :3] = (20, 40, 60)
        image[3:9, 4:11, 3] = 255

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "monster.png")
            self.assertTrue(cv2.imwrite(path, image))

            template, mask = load_monster_template(path)

        self.assertEqual(template.shape, (6, 7, 3))
        self.assertEqual(mask.shape, (6, 7))
        self.assertTrue(np.all(mask == 255))

    def test_alpha_threshold_excludes_translucent_edge_pixels(self):
        image = np.zeros((5, 5, 4), dtype=np.uint8)
        image[1:4, 1:4, :3] = (10, 20, 30)
        image[1:4, 1:4, 3] = 20
        image[2, 2, 3] = 255

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "monster.png")
            self.assertTrue(cv2.imwrite(path, image))

            template, mask = load_monster_template(path, alpha_threshold=32)

        self.assertEqual(template.shape, (1, 1, 3))
        self.assertEqual(mask.tolist(), [[255]])

    def test_legacy_green_screen_template_remains_supported(self):
        image = np.full((8, 9, 3), (0, 255, 0), dtype=np.uint8)
        image[2:7, 3:8] = (0, 0, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "legacy.png")
            self.assertTrue(cv2.imwrite(path, image))

            template, mask = load_monster_template(path)

        self.assertEqual(template.shape, (5, 5, 3))
        self.assertTrue(np.all(mask == 255))

    def test_template_loads_from_chinese_path(self):
        image = np.zeros((6, 7, 4), dtype=np.uint8)
        image[1:5, 2:6, :3] = (20, 40, 60)
        image[1:5, 2:6, 3] = 255
        encoded_ok, encoded = cv2.imencode(".png", image)
        self.assertTrue(encoded_ok)

        with tempfile.TemporaryDirectory() as temp_dir:
            unicode_dir = os.path.join(temp_dir, "黑斧木妖")
            os.makedirs(unicode_dir)
            path = os.path.join(unicode_dir, "移动_0.png")
            with open(path, "wb") as image_file:
                image_file.write(encoded.tobytes())

            template, mask = load_monster_template(path)

        self.assertEqual(template.shape, (4, 4, 3))
        self.assertTrue(np.all(mask == 255))


    def test_selects_three_stand_and_three_move(self):
        files = [
            "monster/野猪/die1_0.png",
            "monster/野猪/hit1_0.png",
            "monster/野猪/jump_0.png",
            "monster/野猪/move_0.png",
            "monster/野猪/move_1.png",
            "monster/野猪/move_2.png",
            "monster/野猪/stand_0.png",
            "monster/野猪/stand_1.png",
            "monster/野猪/stand_2.png",
            "monster/野猪/stand_3.png",
            "monster/野猪/stand_4.png",
            "monster/野猪/stand_5.png",
        ]
        selected = select_monster_template_files(
            files,
            prefixes=["stand", "move"],
            max_files=6,
            per_prefix=3,
        )
        names = [os.path.basename(path) for path in selected]
        self.assertEqual(
            names,
            [
                "stand_0.png",
                "stand_1.png",
                "stand_2.png",
                "move_0.png",
                "move_1.png",
                "move_2.png",
            ],
        )

    def test_prefix_cap_does_not_fill_with_extra_stand_frames(self):
        files = [
            "monster/黑斧木妖/stand_0.png",
            "monster/黑斧木妖/move_0.png",
            "monster/黑斧木妖/move_1.png",
            "monster/黑斧木妖/move_2.png",
            "monster/黑斧木妖/move_3.png",
        ]
        selected = select_monster_template_files(
            files,
            prefixes=["stand", "move"],
            max_files=6,
            per_prefix=3,
        )
        names = [os.path.basename(path) for path in selected]
        self.assertEqual(
            names,
            ["stand_0.png", "move_0.png", "move_1.png", "move_2.png"],
        )


if __name__ == "__main__":
    unittest.main()
