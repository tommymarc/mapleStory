import unittest

from src.engine.MapleStoryAutoLevelUp import MapleStoryAutoBot
from src.ui.profession_config import FUNCTION_DEFINITIONS
from src.utils.common import load_yaml


class RetiredFeatureTests(unittest.TestCase):
    def test_auto_pickup_and_lie_detector_are_absent_from_default_config(self):
        cfg = load_yaml("config/config_default.yaml")
        self.assertNotIn("auto_pickup", cfg)
        self.assertNotIn("lie_detector", cfg)

    def test_pickup_is_absent_from_keyboard_functions(self):
        function_ids = [definition[0] for definition in FUNCTION_DEFINITIONS]
        self.assertNotIn("pickup", function_ids)

    def test_engine_has_no_lie_detector_emergency_logout(self):
        self.assertFalse(hasattr(MapleStoryAutoBot, "emergency_logout_for_lie_detector"))


if __name__ == "__main__":
    unittest.main()
