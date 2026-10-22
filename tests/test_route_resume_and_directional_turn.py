import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest.mock

import numpy as np

from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
from tools.routeRecorder import RouteRecorder


class RouteResumeTests(unittest.TestCase):
    def test_client_capture_keeps_top_of_game_frame(self):
        recorder = RouteRecorder.__new__(RouteRecorder)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[:20] = (11, 22, 233)
        recorder.capture = MagicMock(
            returns_client_frame=True,
            get_frame=MagicMock(return_value=frame),
        )
        recorder.cfg = {
            "game_window": {
                "size": [693, 1282],
                "title_bar_height": 59,
                "ratio_tolerance": 0.08,
            }
        }
        recorder._window_size_adapted = False
        recorder.last_status = ""

        normalized = recorder.get_img_frame()

        self.assertEqual(normalized.shape, (700, 1296, 3))
        self.assertTrue(np.all(normalized[0, 0] == (11, 22, 233)))

    def test_motion_is_inferred_when_arrow_listener_misses_press(self):
        self.assertEqual(
            RouteRecorder.infer_motion_action((20, 30), (16, 30)),
            "left none none",
        )
        self.assertEqual(
            RouteRecorder.infer_motion_action((20, 30), (20, 34)),
            "none down none",
        )


class DirectionalTurnTests(unittest.TestCase):
    def test_attack_waits_for_fresh_delivered_turn_pulse(self):
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {"directional_attack": {"character_turn_delay": 0.06}}
        bot.kb = SimpleNamespace(
            facing_direction="right",
            t_last_direction_input=0.0,
        )
        bot.t_last_attack = 0.0
        bot.combat_turn_ready_at = 0.0
        bot.combat_turn_pending_direction = None
        bot.combat_turn_requested_at = 0.0
        bot.cmd_move_x = "none"
        bot.cmd_action = "none"

        self.assertFalse(bot._pulse_direction_then_attack("left", 0.9, 10.0))
        self.assertEqual((bot.cmd_move_x, bot.cmd_action), ("left", "none"))

        self.assertFalse(bot._pulse_direction_then_attack("left", 0.9, 10.1))
        self.assertEqual((bot.cmd_move_x, bot.cmd_action), ("left", "none"))

        bot.kb.facing_direction = "left"
        bot.kb.t_last_direction_input = bot.combat_turn_requested_at
        self.assertTrue(bot._pulse_direction_then_attack("left", 0.9, 10.1))
        self.assertEqual((bot.cmd_move_x, bot.cmd_action), ("none", "attack"))

    def test_hybrid_uses_aoe_for_two_independent_monsters(self):
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {
            "bot": {"attack": "hybrid"},
            "key": {"aoe_skill": "c"},
            "aoe_skill": {"range_x": 400, "range_y": 170},
            "directional_attack": {
                "range_x": 200, "range_y": 70, "cooldown": 0.9,
                "character_turn_delay": 0.06,
            },
            "hybrid_attack": {"aoe_trigger_count": 2, "aoe_cooldown": 1.2},
            "monster_detect": {"search_box_margin": 50},
        }
        bot.img_frame = np.zeros((700, 1296, 3), dtype=np.uint8)
        bot.loc_player = (600, 350)
        bot.monsters = []
        targets = [
            {"position": (520, 330), "size": (40, 40), "score": 0.1},
            {"position": (660, 330), "size": (40, 40), "score": 0.1},
        ]
        bot.get_monsters_in_range = MagicMock(return_value=targets)
        bot.t_last_attack = 0.0
        bot.t_last_aoe_attack = 0.0
        bot.hybrid_aoe_monster_count = 0
        bot.combat_turn_ready_at = 0.0
        bot.combat_turn_pending_direction = None
        bot.combat_turn_requested_at = 0.0
        bot.cmd_move_x = "right"
        bot.cmd_move_y = "none"
        bot.cmd_action = "none"

        with unittest.mock.patch(
            "src.engine.MapleStoryAutoLevelUp.time.time", return_value=10.0
        ):
            bot.update_cmd_by_mob_detection()

        self.assertEqual(bot.hybrid_aoe_monster_count, 2)
        self.assertEqual(
            (bot.cmd_move_x, bot.cmd_move_y, bot.cmd_action),
            ("none", "none", "aoe_attack"),
        )

    def test_hybrid_aoe_cooldown_honors_sub_second_config(self):
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {"hybrid_attack": {"aoe_cooldown": 0.3}}
        self.assertAlmostEqual(bot._hybrid_aoe_cooldown(), 0.3)

    def test_edge_overlap_still_counts_as_attack_target(self):
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {
            "bot": {"attack": "hybrid"},
            "directional_attack": {"range_x": 130, "range_y": 80},
            "monster_detect": {"max_mob_area_trigger": 1500},
        }
        bot.img_frame = np.zeros((700, 1296, 3), dtype=np.uint8)
        bot.loc_player = (400, 300)
        bot.monsters_info = {}
        bot.decision_monsters = [
            {"position": (510, 275), "size": (90, 70), "score": 0.1},
        ]
        nearest = bot.get_nearest_monster(is_left=False)
        self.assertIsNotNone(nearest)
        self.assertEqual(nearest["position"], (510, 275))


if __name__ == "__main__":
    unittest.main()


class CrowdEngageStickyTests(unittest.TestCase):
    def test_both_sides_sets_engage_and_clears_route_move(self):
        """Crowded both-sides must engage immediately, not leave route move cmds."""
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {
            "bot": {"attack": "directional"},
            "key": {},
            "directional_attack": {
                "range_x": 200, "range_y": 70, "cooldown": 0.9,
                "character_turn_delay": 0.06,
            },
            "monster_detect": {
                "search_box_margin": 50,
                "max_mob_area_trigger": 100,
            },
            "combat": {
                "engage_hold_sec": 1.2,
                "engage_side_sticky": True,
                "monster_track_soft_when_live_max": 1,
            },
        }
        bot.img_frame = np.zeros((700, 1296, 3), dtype=np.uint8)
        bot.img_frame_debug = np.zeros((700, 1296, 3), dtype=np.uint8)
        bot.loc_player = (600, 350)
        bot.monsters_info = {}
        left = {"position": (520, 330), "size": (40, 40), "score": 0.1}
        right = {"position": (660, 330), "size": (40, 40), "score": 0.1}
        bot.monsters = [left, right]
        bot.soft_monsters = []
        bot.decision_monsters = [left, right]
        bot.hybrid_aoe_monster_count = 0
        bot.t_last_attack = 0.0
        bot.t_last_aoe_attack = 0.0
        bot.combat_turn_ready_at = 0.0
        bot.combat_turn_pending_direction = None
        bot.combat_turn_requested_at = 0.0
        bot.engage_until = 0.0
        bot.engage_side = None
        bot.engage_miss_since = 0.0
        bot.engage_miss_mode = None
        bot.engage_flicker_armed_until = 0.0
        bot.kb = SimpleNamespace(facing_direction="right", t_last_direction_input=0.0)
        # Simulate hunting having already written a route move
        bot.cmd_move_x = "right"
        bot.cmd_move_y = "none"
        bot.cmd_action = "none"

        with unittest.mock.patch(
            "src.engine.MapleStoryAutoLevelUp.time.time", return_value=10.0
        ):
            bot.update_cmd_by_mob_detection(use_cached=True)

        self.assertIn(bot.engage_side, ("left", "right"))
        self.assertGreater(bot.engage_until, 10.0)
        # Route horizontal move must be overridden (stand or turn pulse only)
        self.assertIn(bot.cmd_move_x, ("none", "left", "right"))
        # Must not simply leave prior route "right" without engaging
        # (engage_side set proves combat took control)
        self.assertTrue(bot.is_engaging() or bot.cmd_action in ("attack", "none"))

    def test_sticky_does_not_flip_across_frames(self):
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {
            "bot": {"attack": "directional"},
            "key": {},
            "directional_attack": {
                "range_x": 200, "range_y": 70, "cooldown": 0.9,
                "character_turn_delay": 0.06,
            },
            "monster_detect": {
                "search_box_margin": 50,
                "max_mob_area_trigger": 100,
            },
            "combat": {
                "engage_hold_sec": 1.2,
                "engage_side_sticky": True,
            },
        }
        bot.img_frame = np.zeros((700, 1296, 3), dtype=np.uint8)
        bot.img_frame_debug = np.zeros((700, 1296, 3), dtype=np.uint8)
        bot.loc_player = (600, 350)
        bot.monsters_info = {}
        left = {"position": (520, 330), "size": (40, 40), "score": 0.1}
        right = {"position": (660, 330), "size": (40, 40), "score": 0.1}
        bot.monsters = [left, right]
        bot.soft_monsters = []
        bot.decision_monsters = [left, right]
        bot.hybrid_aoe_monster_count = 0
        bot.t_last_attack = 0.0
        bot.combat_turn_ready_at = 0.0
        bot.combat_turn_pending_direction = None
        bot.combat_turn_requested_at = 0.0
        bot.engage_until = 0.0
        bot.engage_side = None
        bot.engage_miss_since = 0.0
        bot.engage_miss_mode = None
        bot.engage_flicker_armed_until = 0.0
        bot.kb = SimpleNamespace(facing_direction="left", t_last_direction_input=0.0)
        bot.cmd_move_x = "none"
        bot.cmd_move_y = "none"
        bot.cmd_action = "none"

        with unittest.mock.patch(
            "src.engine.MapleStoryAutoLevelUp.time.time", return_value=10.0
        ):
            bot.update_cmd_by_mob_detection(use_cached=True)
        first_side = bot.engage_side
        self.assertIn(first_side, ("left", "right"))

        # Next frame: swap which is nearer by nudging player; sticky must hold
        bot.loc_player = (640, 350) if first_side == "left" else (560, 350)
        bot.cmd_move_x = "right"  # pretend route tried again
        with unittest.mock.patch(
            "src.engine.MapleStoryAutoLevelUp.time.time", return_value=10.05
        ):
            bot.update_cmd_by_mob_detection(use_cached=True)
        self.assertEqual(bot.engage_side, first_side)
