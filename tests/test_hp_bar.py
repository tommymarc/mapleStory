import os
import unittest

import cv2
import numpy as np

from src.utils.hp_bar import (
    detect_monster_hp_bars,
    hp_bar_in_attack_box,
    hp_bar_matches_monster,
    merge_hp_bar_detections,
)


def _paint_hp_bar(img, x, y, fill_w, full_w=42, fill_h=3, green=(0, 243, 0)):
    """Paint an Artale-style bar: black roof/caps, neon-green remaining HP."""
    full_w = max(fill_w + 2, full_w)
    img[y - 1, x : x + full_w] = (0, 0, 0)
    img[y : y + fill_h, x : x + full_w] = (0, 0, 0)
    img[y : y + fill_h, x + 1 : x + 1 + fill_w] = green
    # Right/left caps stay black from the full-width fill above.


class HpBarDetectTests(unittest.TestCase):
    def test_detects_full_and_damaged_bars(self):
        img = np.full((120, 220, 3), 180, dtype=np.uint8)
        _paint_hp_bar(img, 20, 30, fill_w=40, full_w=42)
        _paint_hp_bar(img, 120, 30, fill_w=18, full_w=42)
        found = detect_monster_hp_bars(img)
        self.assertGreaterEqual(len(found), 2)
        xs = sorted(bar["hp_bar"][0] for bar in found)
        self.assertTrue(any(abs(x - 20) <= 3 for x in xs))
        self.assertTrue(any(abs(x - 120) <= 3 for x in xs))
        for monster in found:
            self.assertEqual(monster["source"], "hp_bar")
            self.assertTrue(monster["has_hp_bar"])
            bx, by, bw, bh = monster["hp_bar"]
            mx, my = monster["position"]
            self.assertGreaterEqual(my, by)
            self.assertGreaterEqual(bw, 16)
            self.assertLessEqual(bh, 6)

    def test_rejects_green_without_black_roof(self):
        img = np.full((80, 120, 3), 180, dtype=np.uint8)
        img[20:23, 20:60] = (0, 243, 0)
        self.assertEqual(detect_monster_hp_bars(img), [])

    def test_old_exact_color_would_miss_artale_green(self):
        img = np.full((80, 120, 3), 40, dtype=np.uint8)
        _paint_hp_bar(img, 20, 30, fill_w=40, full_w=42)
        legacy = cv2.inRange(img, np.array([71, 204, 64]), np.array([71, 204, 64]))
        self.assertEqual(int(np.count_nonzero(legacy)), 0)
        self.assertGreaterEqual(len(detect_monster_hp_bars(img)), 1)

    def test_detects_real_screenshot_bars(self):
        path = (
            r"C:\Users\Administrator\AppData\Roaming\grokapp\grok-app\data"
            r"\attachments\paste\20260924-145329-028-2026-09-24_14-53-00_img_frame_debug.png"
        )
        if not os.path.isfile(path):
            self.skipTest("screenshot attachment not on disk")
        encoded = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        self.assertIsNotNone(img)
        found = detect_monster_hp_bars(img)
        self.assertGreaterEqual(len(found), 2, found)
        # Bars in this frame sit on the platform around y=300-320.
        ys = [bar["hp_bar"][1] for bar in found]
        self.assertTrue(any(290 <= y <= 330 for y in ys), ys)


class HpBarMergeTests(unittest.TestCase):
    def test_merges_bar_onto_template_and_keeps_unmatched(self):
        template = [{
            "name": "野猪",
            "position": (100, 44),
            "size": (50, 50),
            "score": 0.2,
        }]
        hp = [{
            "name": "Health Bar",
            "position": (97, 48),
            "size": (56, 52),
            "score": 0.12,
            "source": "hp_bar",
            "has_hp_bar": True,
            "hp_bar": (110, 40, 42, 3),
        }, {
            "name": "Health Bar",
            "position": (300, 48),
            "size": (56, 52),
            "score": 0.12,
            "source": "hp_bar",
            "has_hp_bar": True,
            "hp_bar": (310, 40, 40, 3),
        }]
        merged = merge_hp_bar_detections(template, hp)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["name"], "野猪")
        self.assertTrue(merged[0]["has_hp_bar"])
        self.assertEqual(merged[1]["source"], "hp_bar")

    def test_match_rejects_far_away_box(self):
        hp = {"hp_bar": (10, 10, 40, 3)}
        monster = {"position": (400, 200), "size": (50, 50)}
        self.assertFalse(hp_bar_matches_monster(hp, monster))


class HpBarAttackRangeTests(unittest.TestCase):
    def test_bar_inside_attack_x_counts_even_if_above_box(self):
        monster = {
            "source": "hp_bar",
            "has_hp_bar": True,
            "hp_bar": (150, 80, 40, 3),
            "position": (140, 90),
            "size": (56, 52),
        }
        # Attack box is around the nametag, so the bar sits above y0.
        self.assertTrue(hp_bar_in_attack_box(monster, (100, 110, 220, 180)))
        self.assertFalse(hp_bar_in_attack_box(monster, (300, 110, 400, 180)))

    def test_get_nearest_monster_uses_hp_bar_aux(self):
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot

        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {
            "bot": {"attack": "hybrid"},
            "directional_attack": {"range_x": 180, "range_y": 70},
            "monster_detect": {"max_mob_area_trigger": 1500},
        }
        bot.loc_player = (200, 140)
        bot.img_frame = np.zeros((400, 500, 3), dtype=np.uint8)
        bot.monsters_info = {}
        bot.decision_monsters = [{
            "name": "Health Bar",
            "position": (220, 90),
            "size": (56, 52),
            "score": 0.12,
            "source": "hp_bar",
            "has_hp_bar": True,
            "hp_bar": (230, 80, 42, 3),
        }]
        nearest = bot.get_nearest_monster(is_left=False)
        self.assertIsNotNone(nearest)
        self.assertEqual(nearest["source"], "hp_bar")


if __name__ == "__main__":
    unittest.main()
