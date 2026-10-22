# -*- coding: utf-8 -*-
from pathlib import Path

UI = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py")
text = UI.read_text(encoding="utf-8")
start = text.find("def _sword_profile")
if start < 0:
    raise SystemExit("no _sword_profile")
# find return { ... } of the method — next method at same indent
end = text.find("\n    @staticmethod", start + 1)
if end < 0:
    end = text.find("\n    def ", start + 1)
block = text[start:end]
print("OLD BLOCK LEN", len(block))
print(block[:800])

NEW = '''def _sword_profile():
        """Built-in 剑客 combat tuning; kept even if YAML was overwritten by an older save."""
        return {
            "main_attack_type": "directional",
            "jump_attack": False,
            "bindings": {
                "add_hp": "a",
                "add_mp": "s",
                "aoe_attack": "c",
                "buff": "b",
                "dialog": "f",
                "jump": "space",
                "main_attack": "x",
                "pet_food": "`",
            },
            "intervals": {
                "buff": 60,
                "experience_coupon": 3600,
                "pet_food": 600,
            },
            "overrides": {
                "combat": {
                    "monster_track_enable": True,
                    "monster_track_ttl_sec": 0.5,
                },
                "directional_attack": {
                    "character_turn_delay": 0.03,
                    "cooldown": 0.35,
                    "range_x": 170,
                    "range_y": 100,
                    "skip_turn_if_facing": True,
                },
                "monster_detect": {
                    "detect_every_n_frames": 2,
                    "diff_thres": 0.28,
                    "max_above_player_y": 90,
                    "template_max_files_per_monster": 6,
                    "template_name_prefixes": ["stand", "move"],
                },
            },
        }
'''
# replace from def _sword_profile through end of method (preserve leading spaces before def)
# block starts at "def _sword_profile" without indent - text[start] is 'd'
indent = "    "
new_block = indent + NEW
text2 = text[:start] + new_block + text[end:]
UI.write_text(text2, encoding="utf-8")
print("updated _sword_profile")

# Also improve ensure to merge missing monster_detect keys into existing overrides
ensure_marker = "if not sword.get(\"overrides\"):"
if "diff_thres" not in text2[text2.find("_ensure_builtin"):text2.find("_ensure_builtin")+800]:
    old_ensure = '''        else:
            # Keep user keybinds; refresh combat overrides if empty.
            if not sword.get("overrides"):
                sword["overrides"] = self._sword_profile()["overrides"]
        return data'''
    new_ensure = '''        else:
            # Keep user keybinds; refresh combat overrides if empty or stale.
            builtin_ov = self._sword_profile()["overrides"]
            if not sword.get("overrides"):
                sword["overrides"] = builtin_ov
            else:
                md = sword["overrides"].setdefault("monster_detect", {})
                for k, v in builtin_ov.get("monster_detect", {}).items():
                    if k not in md:
                        md[k] = v
        return data'''
    if old_ensure in text2:
        text2 = text2.replace(old_ensure, new_ensure, 1)
        UI.write_text(text2, encoding="utf-8")
        print("updated _ensure_builtin merge")
    else:
        print("ensure block not exact match; skip merge tweak")
