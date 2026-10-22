import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot


def _make_bot():
    # Avoid full __init__; build a lightweight stub with methods bound
    bot = object.__new__(MapleStoryAutoBot)
    bot.cfg = {
        "combat": {
            "hit_react_enable": True,
            "hit_react_min_drop_percent": 4.0,
            "hit_react_duration_sec": 0.4,
            "hit_react_cooldown_sec": 1.3,
            "hit_react_jump": True,
        },
        "hybrid_attack": {},
        "bot": {"attack": "directional"},
    }
    bot.loc_player = (100, 100)
    bot.engage_side = "right"
    bot.monsters = []
    bot.decision_monsters = []
    bot.prev_hp_percent = 80.0
    bot.hit_react_until = 0.0
    bot.hit_react_dir = None
    bot.hit_react_need_jump = False
    bot.t_last_hit_react = 0.0
    bot.cmd_move_x = "none"
    bot.cmd_move_y = "none"
    bot.cmd_action = "none"
    bot.kb = SimpleNamespace(facing_direction="right", set_command=MagicMock())
    bot.health_monitor = SimpleNamespace(hp_percent=80.0)
    bot.img_frame = None
    bot.detect_monsters_near_player = MagicMock(return_value=[])
    return bot


class HitReactTests(unittest.TestCase):
    def test_sharp_drop_arms_retreat_opposite_engage(self):
        bot = _make_bot()
        bot.health_monitor.hp_percent = 75.0  # 5% drop
        MapleStoryAutoBot.update_hit_react_from_hp(bot)
        self.assertTrue(MapleStoryAutoBot.is_hit_reacting(bot))
        self.assertEqual(bot.hit_react_dir, "left")  # opposite of engage right
        self.assertTrue(bot.hit_react_need_jump)

    def test_small_drop_ignored(self):
        bot = _make_bot()
        bot.health_monitor.hp_percent = 77.5  # 2.5% drop < 4
        MapleStoryAutoBot.update_hit_react_from_hp(bot)
        self.assertFalse(MapleStoryAutoBot.is_hit_reacting(bot))

    def test_apply_jump_once_then_none(self):
        bot = _make_bot()
        bot.hit_react_dir = "left"
        bot.hit_react_need_jump = True
        MapleStoryAutoBot.apply_hit_react_cmd(bot)
        self.assertEqual(bot.cmd_move_x, "left")
        self.assertEqual(bot.cmd_action, "jump")
        self.assertFalse(bot.hit_react_need_jump)
        MapleStoryAutoBot.apply_hit_react_cmd(bot)
        self.assertEqual(bot.cmd_action, "none")

    def test_handle_skips_when_inactive(self):
        bot = _make_bot()
        self.assertFalse(MapleStoryAutoBot.handle_hit_react_frame(bot))

    def test_cooldown_blocks_retrigger(self):
        bot = _make_bot()
        bot.health_monitor.hp_percent = 70.0
        MapleStoryAutoBot.update_hit_react_from_hp(bot)
        self.assertTrue(MapleStoryAutoBot.is_hit_reacting(bot))
        # Expire window but keep cooldown
        bot.hit_react_until = time.time() - 0.01
        bot.prev_hp_percent = 70.0
        bot.health_monitor.hp_percent = 60.0
        MapleStoryAutoBot.update_hit_react_from_hp(bot)
        # Still within cooldown from first trigger
        self.assertFalse(bot.hit_react_until > time.time())


if __name__ == "__main__":
    unittest.main()
