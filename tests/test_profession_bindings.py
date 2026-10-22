import unittest

from src.ui.profession_config import ProfessionConfigStore
from src.utils.profession_bindings import (
    apply_profession_profile,
    collect_buff_skill_slots,
    reset_profession_overrides,
    resolve_profession_binding,
)


def base_cfg():
    return {
        "bot": {"attack": "directional"},
        "key": {
            "aoe_skill": "q",
            "directional_attack": "w",
            "teleport": "e",
            "jump": "space",
            "add_hp": "1",
            "add_mp": "2",
        },
        "buff_skill": {"keys": [], "cooldown": []},
    }


class ProfessionBindingsTests(unittest.TestCase):
    def test_retired_pickup_binding_is_removed_from_old_profiles(self):
        data = {
            "professions": {
                "旧职业": {
                    "bindings": {"main_attack": "a", "pickup": "z"},
                    "intervals": {},
                }
            }
        }

        ProfessionConfigStore._migrate_legacy_bindings(data)

        self.assertEqual(
            data["professions"]["旧职业"]["bindings"],
            {"main_attack": "a"},
        )

    def test_all_labelled_bindings_are_available_at_runtime(self):
        cfg = base_cfg()
        profile = {
            "main_attack_type": "directional",
            "bindings": {
                "main_attack": "a",
                "aoe_attack": "s",
                "secondary_attack_1": "d",
            },
            "intervals": {},
        }

        apply_profession_profile(cfg, "战士", profile)

        self.assertEqual(resolve_profession_binding(cfg, "secondary_attack_1"), "d")
        self.assertEqual(resolve_profession_binding(cfg, "aoe_attack"), "s")
        self.assertEqual(cfg["key"]["directional_attack"], "a")
        self.assertEqual(cfg["key"]["aoe_skill"], "s")

    def test_aoe_main_attack_is_fallback_for_aoe_action(self):
        cfg = base_cfg()
        profile = {
            "main_attack_type": "aoe_skill",
            "bindings": {"main_attack": "r"},
            "intervals": {},
        }

        apply_profession_profile(cfg, "法师", profile)

        self.assertEqual(resolve_profession_binding(cfg, "aoe_attack"), "r")
        self.assertEqual(cfg["key"]["aoe_skill"], "r")

    def test_hybrid_profile_keeps_distinct_main_and_aoe_keys(self):
        cfg = base_cfg()
        profile = {
            "main_attack_type": "hybrid",
            "bindings": {"main_attack": "x", "aoe_attack": "c"},
            "intervals": {},
        }

        apply_profession_profile(cfg, "冰雷", profile)

        self.assertEqual(cfg["bot"]["attack"], "hybrid")
        self.assertEqual(cfg["key"]["directional_attack"], "x")
        self.assertEqual(cfg["key"]["aoe_skill"], "c")

    def test_unknown_action_has_no_binding(self):
        cfg = base_cfg()
        apply_profession_profile(
            cfg,
            "弓箭手",
            {"main_attack_type": "directional", "bindings": {}, "intervals": {}},
        )

        self.assertEqual(resolve_profession_binding(cfg, "unknown_action"), "")

    def test_buff_and_pet_food_are_independent_bindings(self):
        cfg = base_cfg()
        profile = {
            "main_attack_type": "directional",
            "bindings": {"buff": "b", "pet_food": "f"},
            "intervals": {"buff": 90, "pet_food": 600},
        }

        apply_profession_profile(cfg, "弓箭手", profile)

        self.assertEqual(cfg["buff_skill"]["keys"], ["b"])
        self.assertEqual(cfg["buff_skill"]["cooldown"], [90])
        self.assertEqual(resolve_profession_binding(cfg, "pet_food"), "f")

    def test_numbered_buffs_are_applied_in_order(self):
        cfg = base_cfg()
        profile = {
            "main_attack_type": "directional",
            "bindings": {
                "buff": "b",
                "buff2": "v",
                "buff1": "n",
            },
            "intervals": {"buff": 60, "buff1": 120, "buff2": 180},
        }

        apply_profession_profile(cfg, "法师", profile)

        self.assertEqual(cfg["buff_skill"]["keys"], ["b", "n", "v"])
        self.assertEqual(cfg["buff_skill"]["cooldown"], [60, 120, 180])
        self.assertEqual(resolve_profession_binding(cfg, "buff1"), "n")
        slots = collect_buff_skill_slots(
            profile["bindings"], profile["intervals"]
        )
        self.assertEqual([item[0] for item in slots], ["buff", "buff1", "buff2"])

    def test_legacy_combined_binding_still_maps_to_buff(self):
        cfg = base_cfg()
        profile = {
            "main_attack_type": "directional",
            "bindings": {"buff_pet_food": "b"},
            "intervals": {"buff_pet_food": 75},
        }

        apply_profession_profile(cfg, "旧职业", profile)

        self.assertEqual(cfg["buff_skill"]["keys"], ["b"])
        self.assertEqual(cfg["buff_skill"]["cooldown"], [75])

    def test_runtime_profile_is_optional_for_default_actions(self):
        cfg = base_cfg()

        self.assertEqual(resolve_profession_binding(cfg, "main_attack"), "w")
        self.assertEqual(resolve_profession_binding(cfg, "aoe_attack"), "q")
        self.assertEqual(resolve_profession_binding(cfg, "jump"), "space")

    def test_switching_professions_restores_defaults_for_missing_bindings(self):
        defaults = base_cfg()
        cfg = base_cfg()
        apply_profession_profile(
            cfg,
            "法师",
            {
                "main_attack_type": "aoe_skill",
                "bindings": {"main_attack": "r", "jump": "v"},
                "intervals": {},
            },
            defaults,
        )
        apply_profession_profile(
            cfg,
            "战士",
            {
                "main_attack_type": "directional",
                "bindings": {"main_attack": "a"},
                "intervals": {},
            },
            defaults,
        )

        self.assertEqual(cfg["key"]["directional_attack"], "a")
        self.assertEqual(cfg["key"]["jump"], "space")
        self.assertEqual(cfg["key"]["aoe_skill"], "q")

    def test_no_profession_uses_default_bindings(self):
        defaults = base_cfg()
        cfg = base_cfg()
        apply_profession_profile(
            cfg,
            "法师",
            {
                "main_attack_type": "aoe_skill",
                "bindings": {"main_attack": "r"},
                "intervals": {},
            },
            defaults,
        )

        apply_profession_profile(cfg, "", None, defaults)

        self.assertEqual(resolve_profession_binding(cfg, "main_attack"), "w")
        self.assertEqual(resolve_profession_binding(cfg, "aoe_attack"), "q")

    def test_reset_removes_runtime_profile(self):
        defaults = base_cfg()
        cfg = base_cfg()
        apply_profession_profile(
            cfg,
            "法师",
            {"main_attack_type": "aoe_skill", "bindings": {"main_attack": "r"}},
        )

        reset_profession_overrides(cfg, defaults)

        self.assertNotIn("profession", cfg)
        self.assertEqual(cfg["bot"]["attack"], "directional")


if __name__ == "__main__":
    unittest.main()
