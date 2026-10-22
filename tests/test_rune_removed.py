from argparse import Namespace
import unittest

from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot


class RuneRemovalTests(unittest.TestCase):
    def test_runtime_has_no_rune_solver_or_rune_states(self):
        args = Namespace(
            disable_control=True,
            cfg="default",
            debug=False,
            record=False,
            is_ui=True,
            disable_viz=True,
            test_image="",
            init_state="",
        )

        bot = MapleStoryAutoBot(args)

        self.assertFalse(hasattr(bot, "rune_solver"))
        self.assertEqual(
            set(bot.fsm.states),
            {"hunting", "aux", "patrol", "smart_patrol"},
        )
        self.assertIsNone(bot.fsm.states["hunting"].check_transitions())


if __name__ == "__main__":
    unittest.main()
