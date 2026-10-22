"""Tests for rope edge I/O and smart_patrol Return transitions."""
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.states.smart_patrol import (
    PHASE_ENGAGE,
    PHASE_RETURN,
    PHASE_SCAN,
    SmartPatrolState,
)
from src.utils.ropes import (
    append_edge,
    is_off_preferred_band,
    load_ropes,
    nearest_edge,
    normalize_edge,
    save_ropes,
)


class RopeIoTests(unittest.TestCase):
    def test_normalize_infers_direction(self):
        up = normalize_edge({"start": [10, 40], "end": [12, 10]}, 0)
        self.assertEqual(up["direction"], "up")
        down = normalize_edge({"start": [10, 10], "end": [12, 40], "id": "d1"}, 0)
        self.assertEqual(down["direction"], "down")
        self.assertEqual(down["id"], "d1")

    def test_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ropes.yaml")
            doc = {
                "map": "duoluozhuyi-xia",
                "preferred_y": 22.0,
                "preferred_y_tol": 10,
                "edges": [
                    {
                        "id": "rope_1",
                        "start": [30, 50],
                        "end": [32, 18],
                        "direction": "up",
                        "duration_hint_sec": 2.5,
                    }
                ],
            }
            save_ropes("duoluozhuyi-xia", doc, path=path)
            loaded = load_ropes("duoluozhuyi-xia", path=path)
            self.assertEqual(loaded["map"], "duoluozhuyi-xia")
            self.assertEqual(loaded["preferred_y"], 22.0)
            self.assertEqual(len(loaded["edges"]), 1)
            self.assertEqual(loaded["edges"][0]["direction"], "up")
            self.assertEqual(loaded["edges"][0]["start"], [30.0, 50.0])

    def test_append_edge_and_nearest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ropes.yaml")
            e1 = append_edge(
                "duoluozhuyi-xia",
                (10, 40),
                (11, 15),
                direction="up",
                duration_hint_sec=2.0,
                path=path,
            )
            e2 = append_edge(
                "duoluozhuyi-xia",
                (80, 40),
                (81, 16),
                direction="up",
                path=path,
            )
            self.assertEqual(e1["id"], "rope_1")
            self.assertEqual(e2["id"], "rope_2")
            doc = load_ropes("duoluozhuyi-xia", path=path)
            self.assertEqual(len(doc["edges"]), 2)
            near = nearest_edge(doc["edges"], (12, 39))
            self.assertEqual(near["id"], "rope_1")
            near2 = nearest_edge(doc["edges"], (78, 41))
            self.assertEqual(near2["id"], "rope_2")

    def test_off_preferred_band(self):
        self.assertFalse(is_off_preferred_band(20, 22, 12))
        self.assertTrue(is_off_preferred_band(50, 22, 12))
        self.assertFalse(is_off_preferred_band(None, 22, 12))
        self.assertFalse(is_off_preferred_band(50, None, 12))


def _make_bot(**overrides):
    bot = SimpleNamespace(
        cfg={
            "smart_patrol": {
                "range": [0.2, 0.8],
                "turn_point_thres": 2,
                "scan_turn_sec": 8.0,
                "engage_timeout_sec": 6.0,
                "no_mob_turn_sec": 0.3,
                "rope_enable": True,
                "rope_cooldown_sec": 0.5,
                "rope_approach_dist": 8.0,
                "rope_arrive_dist": 10.0,
                "rope_climb_timeout_sec": 6.0,
                "preferred_y": 20.0,
                "preferred_y_tol": 8.0,
            }
        },
        cmd_move_x="none",
        cmd_move_y="none",
        cmd_action="none",
        monsters=[],
        decision_monsters=[],
        is_player_minimap_detected=True,
        loc_player_minimap=(50, 50),  # off preferred band (20±8)
        img_minimap=SimpleNamespace(shape=(40, 100, 3)),
        kb=MagicMock(),
        update_cmd_by_mob_detection=MagicMock(),
        update_cmd_by_random=MagicMock(),
        is_player_stuck=MagicMock(return_value=False),
        handle_hit_react_frame=MagicMock(return_value=False),
        has_soft_combat_target=MagicMock(return_value=False),
        is_engaging=MagicMock(return_value=False),
        clear_engage=MagicMock(),
        rope_doc={
            "map": "duoluozhuyi-xia",
            "preferred_y": 20.0,
            "preferred_y_tol": 8.0,
            "edges": [
                {
                    "id": "rope_1",
                    "start": [48, 50],
                    "end": [50, 20],
                    "direction": "up",
                    "duration_hint_sec": 1.0,
                }
            ],
        },
        rope_edges=None,
    )
    bot.rope_edges = list(bot.rope_doc["edges"])
    for k, v in overrides.items():
        setattr(bot, k, v)
    return bot


class SmartPatrolRopeTests(unittest.TestCase):
    def test_scan_flips_at_minimap_bound(self):
        bot = _make_bot(loc_player_minimap=(5, 20))
        bot.cfg["smart_patrol"]["preferred_y"] = 20.0
        bot.cfg["smart_patrol"]["turn_point_thres"] = 1
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.scan_dir = "left"
        state.apply_scan_move()
        # Hard clamp: flip + move inward on first past-bound frame (no cliff walk).
        self.assertEqual(state.scan_dir, "right")
        self.assertEqual(bot.cmd_move_x, "right")
        self.assertEqual(bot.cmd_action, "none")

    def test_scan_keeps_walking_when_mobs_are_only_in_search_roi(self):
        bot = _make_bot(loc_player_minimap=(50, 20))
        bot.cfg["bot"] = {"attack": "hybrid"}
        bot.cfg["hybrid_attack"] = {"aoe_trigger_count": 2}
        bot.hybrid_aoe_monster_count = 0
        bot.monsters = [{"name": "mob", "position": (1, 1), "size": (10, 10)}]
        bot.decision_monsters = list(bot.monsters)
        bot.get_nearest_monster = MagicMock(return_value=None)
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.scan_dir = "right"
        state.on_frame()
        self.assertEqual(state.phase, PHASE_SCAN)
        self.assertEqual(bot.cmd_move_x, "right")

    def test_scan_to_engage_when_monsters_in_attack_range(self):
        bot = _make_bot(loc_player_minimap=(50, 20))
        bot.cfg["bot"] = {"attack": "hybrid"}
        bot.cfg["hybrid_attack"] = {"aoe_trigger_count": 2}
        bot.hybrid_aoe_monster_count = 2
        bot.get_nearest_monster = MagicMock(return_value=None)

        def _detect():
            bot.hybrid_aoe_monster_count = 2
            bot.cmd_action = "aoe_attack"
            bot.cmd_move_x = "none"

        bot.update_cmd_by_mob_detection = _detect
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.scan_dir = "right"
        state.on_frame()
        self.assertEqual(state.phase, PHASE_ENGAGE)
        self.assertEqual(bot.cmd_move_x, "right")
        bot.kb.set_command.assert_called()
        sent = bot.kb.set_command.call_args[0][0]
        self.assertIn("aoe_attack", sent)

    def test_engage_returns_to_scan_after_no_mob_timeout(self):
        bot = _make_bot(loc_player_minimap=(50, 20))
        # Disable rope so no_mob leave goes to Scan, not Return.
        bot.cfg["smart_patrol"]["rope_enable"] = False
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state._enter_phase(PHASE_ENGAGE)
        state.t_no_mob_since = time.time() - 1.0
        state.on_frame()
        self.assertEqual(state.phase, PHASE_SCAN)

    def test_off_band_triggers_return(self):
        bot = _make_bot(loc_player_minimap=(50, 50))  # far from preferred_y=20
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.t_last_rope_attempt = 0.0
        state.on_frame()
        self.assertEqual(state.phase, PHASE_RETURN)
        self.assertIsNotNone(state.active_edge)
        self.assertEqual(state.active_edge["id"], "rope_1")

    def test_return_approaches_then_climbs(self):
        bot = _make_bot(loc_player_minimap=(20, 50))  # left of start x=48
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.active_edge = bot.rope_edges[0]
        state._enter_phase(PHASE_RETURN)
        state.apply_return_move()
        self.assertEqual(state.return_sub, "approach")
        self.assertEqual(bot.cmd_move_x, "right")
        self.assertEqual(bot.cmd_move_y, "none")

        # Arrive at start → climb
        bot.loc_player_minimap = (48, 50)
        state.apply_return_move()
        self.assertEqual(state.return_sub, "climb")
        self.assertEqual(bot.cmd_move_y, "up")

        # Near end → back to Scan
        bot.loc_player_minimap = (50, 20)
        state.apply_return_move()
        self.assertEqual(state.phase, PHASE_SCAN)

    def test_scan_no_mob_triggers_return_with_cooldown(self):
        # On preferred band but not already at rope end (else Return finishes same frame).
        bot = _make_bot(loc_player_minimap=(20, 22))
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.t_no_mob_since = time.time() - 1.0
        state.t_last_rope_attempt = 0.0
        state.on_frame()
        self.assertEqual(state.phase, PHASE_RETURN)
        self.assertEqual(state.return_sub, "approach")

    def test_fsm_registers_smart_patrol(self):
        from src.engine.FiniteStateMachine import FiniteStateMachine
        from src.states.hunting import HuntingState
        from src.states.auxiliary import AuxiliaryState
        from src.states.patrol import PatrolState
        from src.states.smart_patrol import SmartPatrolState as SPS

        bot = SimpleNamespace()
        bot.fsm = FiniteStateMachine()
        bot.fsm.add_state(HuntingState("hunting", bot))
        bot.fsm.add_state(AuxiliaryState("aux", bot))
        bot.fsm.add_state(PatrolState("patrol", bot))
        bot.fsm.add_state(SPS("smart_patrol", bot))
        self.assertIn("smart_patrol", bot.fsm.states)



class TestPreferredYSoftLock(unittest.TestCase):
    def test_soft_lock_after_stable_y(self):
        bot = _make_bot(loc_player_minimap=(40.0, 55.0))
        bot.cfg["smart_patrol"]["preferred_y"] = None
        bot.rope_doc["preferred_y"] = None
        bot.rope_edges = []
        bot.rope_doc["edges"] = []
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        bot.decision_monsters = [{"x": 1}]
        t0 = time.time()
        state._y_lock_anchor = 55.0
        state._y_lock_since = t0 - 4.0
        state._maybe_soft_lock_preferred_y(t0)
        self.assertEqual(bot.rope_doc.get("preferred_y"), 55.0)
        self.assertTrue(state._y_soft_locked)

    def test_missing_rope_warn_throttled(self):
        bot = _make_bot()
        bot.rope_edges = []
        bot.rope_doc["edges"] = []
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()  # soft info once via force path
        prev = state.t_last_missing_rope_log
        self.assertGreater(prev, 0.0)
        now = time.time()
        self.assertTrue(state._warn_missing_ropes(now + 1.0, force=False))
        self.assertEqual(state.t_last_missing_rope_log, prev)

    def test_past_bound_immediate_inward_no_jump(self):
        bot = _make_bot(loc_player_minimap=(95, 20))  # ratio 0.95 > 0.8
        bot.cfg["smart_patrol"]["range"] = [0.2, 0.8]
        bot.cfg["smart_patrol"]["preferred_y"] = 20.0
        bot.cmd_action = "jump"
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state.scan_dir = "right"
        state.apply_scan_move()
        self.assertEqual(state.scan_dir, "left")
        self.assertEqual(bot.cmd_move_x, "left")
        self.assertEqual(bot.cmd_action, "none")


if __name__ == "__main__":
    unittest.main()


class TestBoundaryBeatsChase(unittest.TestCase):
    def test_enforce_blocks_outward_move_at_right_margin(self):
        bot = _make_bot(loc_player_minimap=(78, 20))  # ratio 0.78, range [0.2,0.8], margin 0.03
        bot.cfg["smart_patrol"]["range"] = [0.2, 0.8]
        bot.cfg["smart_patrol"]["edge_jump_margin"] = 0.03
        bot.cfg["smart_patrol"]["rope_enable"] = False
        bot.cmd_move_x = "right"  # chase pulse toward outward mob
        bot.cmd_action = "none"
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        clamped = state._enforce_x_bounds()
        self.assertTrue(clamped)
        self.assertNotEqual(bot.cmd_move_x, "right")
        self.assertEqual(state.scan_dir, "left")

    def test_filter_drops_outward_monster_at_right_bound(self):
        bot = _make_bot(loc_player_minimap=(80, 20))  # exactly at right 0.8
        bot.cfg["smart_patrol"]["range"] = [0.2, 0.8]
        bot.cfg["smart_patrol"]["edge_jump_margin"] = 0.03
        bot.cfg["smart_patrol"]["rope_enable"] = False
        bot.loc_player = (400, 300)
        outward = {"name": "out", "position": (500, 290), "size": (40, 40)}
        inward = {"name": "in", "position": (300, 290), "size": (40, 40)}
        bot.decision_monsters = [outward, inward]
        bot.monsters = [outward, inward]
        bot.soft_monsters = []
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        state._filter_outward_bound_monsters()
        names = [m["name"] for m in bot.decision_monsters]
        self.assertIn("in", names)
        self.assertNotIn("out", names)

    def test_rope_enable_false_skips_return_and_warn(self):
        bot = _make_bot(loc_player_minimap=(50, 50))  # off band
        bot.cfg["smart_patrol"]["rope_enable"] = False
        state = SmartPatrolState("smart_patrol", bot)
        state.on_enter()
        self.assertEqual(state.t_last_missing_rope_log, 0.0)  # warn skipped
        state.on_frame()
        self.assertNotEqual(state.phase, PHASE_RETURN)

