import unittest
from src.utils.monster_tracker import MonsterTracker


def _mob(x, y, w=40, h=50, name="slime"):
    return {"name": name, "position": (x, y), "size": (w, h), "score": 0.1}


class MonsterTrackerTests(unittest.TestCase):
    def test_stable_id_across_frames(self):
        tr = MonsterTracker()
        live1, soft1 = tr.update([_mob(100, 200)], now=1.0, ttl_sec=0.4, match_dist=80)
        self.assertEqual(len(live1), 1)
        self.assertEqual(len(soft1), 0)
        tid = live1[0]["track_id"]

        live2, soft2 = tr.update([_mob(110, 205)], now=1.1, ttl_sec=0.4, match_dist=80)
        self.assertEqual(live2[0]["track_id"], tid)
        self.assertEqual(soft2, [])

    def test_soft_ghost_within_ttl(self):
        tr = MonsterTracker()
        live1, _ = tr.update([_mob(100, 200)], now=1.0, ttl_sec=0.4, match_dist=80)
        tid = live1[0]["track_id"]

        live2, soft2 = tr.update([], now=1.2, ttl_sec=0.4, match_dist=80)
        self.assertEqual(live2, [])
        self.assertEqual(len(soft2), 1)
        self.assertTrue(soft2[0]["is_soft"])
        self.assertEqual(soft2[0]["track_id"], tid)
        self.assertEqual(soft2[0]["position"], (100, 200))

        live3, soft3 = tr.update([], now=1.5, ttl_sec=0.4, match_dist=80)
        self.assertEqual(live3, [])
        self.assertEqual(soft3, [])

    def test_rematch_after_soft(self):
        tr = MonsterTracker()
        live1, _ = tr.update([_mob(100, 200)], now=1.0, ttl_sec=0.4, match_dist=80)
        tid = live1[0]["track_id"]
        _, soft = tr.update([], now=1.2, ttl_sec=0.4, match_dist=80)
        self.assertEqual(soft[0]["track_id"], tid)
        live3, soft3 = tr.update([_mob(105, 198)], now=1.35, ttl_sec=0.4, match_dist=80)
        self.assertEqual(live3[0]["track_id"], tid)
        self.assertEqual(soft3, [])


class SoftCombatDecisionTests(unittest.TestCase):
    def test_decision_union_and_aoe_live_only(self):
        from types import SimpleNamespace
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot

        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {"combat": {
            "monster_track_enable": True,
            "monster_track_ttl_sec": 0.4,
            "monster_track_match_dist": 80,
        }}
        bot.monster_tracker = MonsterTracker()
        bot.img_frame_debug = None

        live = [_mob(50, 50)]
        bot._update_monster_tracks(live, now=10.0)
        self.assertEqual(len(bot.monsters), 1)
        self.assertEqual(len(bot.soft_monsters), 0)
        self.assertTrue(len(bot.decision_monsters) == 1)

        bot._update_monster_tracks([], now=10.2)
        self.assertEqual(bot.monsters, [])
        self.assertEqual(len(bot.soft_monsters), 1)
        self.assertTrue(bot.has_soft_combat_target())
        self.assertEqual(len(bot.decision_monsters), 1)

        # AoE counter uses self.monsters (live) only — caller responsibility
        bot.loc_player = (50, 50)
        bot.img_frame = SimpleNamespace(shape=(600, 800, 3))
        # with empty live, count should be 0 even if soft exists
        # monkeypatch get_aoe_attack_range
        bot.get_aoe_attack_range = lambda: (0, 0, 800, 600)
        self.assertEqual(bot.count_monsters_in_aoe_range(), 0)


if __name__ == "__main__":
    unittest.main()


class CrowdDecisionStabilityTests(unittest.TestCase):
    def _bot(self, combat=None):
        from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
        bot = MapleStoryAutoBot.__new__(MapleStoryAutoBot)
        bot.cfg = {"combat": {
            "monster_track_enable": True,
            "monster_track_ttl_sec": 0.4,
            "monster_track_match_dist": 80,
            "monster_track_soft_when_live_max": 1,
            "engage_side_sticky": True,
            **(combat or {}),
        }}
        bot.monster_tracker = MonsterTracker()
        import numpy as np
        bot.img_frame_debug = np.zeros((100, 100, 3), dtype=np.uint8)
        bot.loc_player = (400, 300)
        bot.engage_side = None
        bot.engage_until = 0.0
        return bot

    def test_live_crowded_drops_soft_from_decision(self):
        bot = self._bot()
        # Seed one soft ghost on the left
        bot._update_monster_tracks([_mob(100, 280)], now=1.0)
        bot._update_monster_tracks([], now=1.1)
        self.assertEqual(len(bot.soft_monsters), 1)
        # Two live on the right → soft ignored for decisions
        live = [_mob(500, 280), _mob(560, 280)]
        bot._update_monster_tracks(live, now=1.15)
        self.assertEqual(len(bot.monsters), 2)
        self.assertTrue(all(not m.get("is_soft") for m in bot.decision_monsters))
        self.assertEqual(len(bot.decision_monsters), 2)

    def test_sparse_live_keeps_soft_in_decision(self):
        bot = self._bot()
        bot._update_monster_tracks([_mob(100, 280)], now=1.0)
        bot._update_monster_tracks([], now=1.1)
        bot._update_monster_tracks([_mob(500, 280)], now=1.15)
        self.assertEqual(len(bot.monsters), 1)
        self.assertEqual(len(bot.soft_monsters), 1)
        self.assertEqual(len(bot.decision_monsters), 2)

    def test_both_sides_picks_nearer_not_none(self):
        bot = self._bot()
        left = _mob(350, 280)   # nearer
        right = _mob(480, 280)
        direction = bot.get_attack_direction(left, right)
        self.assertEqual(direction, "left")

    def test_sticky_side_holds_when_both_present(self):
        bot = self._bot()
        bot.engage_side = "right"
        left = _mob(350, 280)   # nearer
        right = _mob(480, 280)
        direction = bot.get_attack_direction(left, right)
        self.assertEqual(direction, "right")
