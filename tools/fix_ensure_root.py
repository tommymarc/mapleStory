# -*- coding: utf-8 -*-
"""Permanently restore ProfessionConfigStore builtin ensure + harden _load."""
from pathlib import Path
import py_compile

UI = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py")
text = UI.read_text(encoding="utf-8")

# Remove any broken/orphan partial defs if present
# We'll replace from after _migrate_legacy_bindings through _sword_profile / empty_profile cleanly.

marker_migrate_end = '        data["version"] = 2\n'
idx = text.find(marker_migrate_end)
if idx < 0:
    raise SystemExit("migrate end not found")
idx_after = idx + len(marker_migrate_end)

# Find empty_profile — keep from there onward
empty_at = text.find("\n    @staticmethod\n    def empty_profile(", idx_after)
if empty_at < 0:
    empty_at = text.find("\n    def empty_profile(", idx_after)
if empty_at < 0:
    raise SystemExit("empty_profile not found")

SWORD_AND_ENSURE = r'''

    @staticmethod
    def _sword_profile():
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

    def _ensure_builtin_profiles(self, data):
        """Always keep 剑客 present with combat overrides (survives old saves)."""
        professions = data.get("professions")
        if not isinstance(professions, dict):
            data["professions"] = {}
            professions = data["professions"]
        builtin = self._sword_profile()
        sword = professions.get("剑客")
        if not isinstance(sword, dict):
            professions["剑客"] = builtin
            return data
        # Keep user keybinds / intervals; guarantee overrides exist and have required keys.
        if not isinstance(sword.get("bindings"), dict) or not sword.get("bindings"):
            sword["bindings"] = dict(builtin["bindings"])
        if not isinstance(sword.get("intervals"), dict):
            sword["intervals"] = dict(builtin["intervals"])
        sword.setdefault("main_attack_type", builtin["main_attack_type"])
        sword.setdefault("jump_attack", builtin["jump_attack"])
        overrides = sword.get("overrides")
        if not isinstance(overrides, dict):
            sword["overrides"] = builtin["overrides"]
        else:
            for section, section_vals in builtin["overrides"].items():
                dst = overrides.setdefault(section, {})
                if not isinstance(dst, dict):
                    overrides[section] = dict(section_vals)
                    continue
                for key, value in section_vals.items():
                    if key not in dst:
                        dst[key] = value
        return data

'''

text2 = text[:idx_after] + SWORD_AND_ENSURE + text[empty_at:]

# Harden _load: inline safety net so missing method can never crash startup again.
OLD_LOAD = '''    def _load(self):
        if os.path.exists(self.path):
            data = load_yaml(self.path)
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("version", 1)
        data.setdefault("selected_profession", "")
        data.setdefault("professions", {})
        self._migrate_legacy_bindings(data)
        self._ensure_builtin_profiles(data)
        return data'''

NEW_LOAD = '''    def _load(self):
        if os.path.exists(self.path):
            data = load_yaml(self.path)
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("version", 1)
        data.setdefault("selected_profession", "")
        data.setdefault("professions", {})
        self._migrate_legacy_bindings(data)
        # Prefer the dedicated helper; if a bad edit deletes it, still seed 剑客 inline
        # so the app never crashes on AttributeError at startup.
        ensure = getattr(self, "_ensure_builtin_profiles", None)
        if callable(ensure):
            ensure(data)
        else:
            professions = data.setdefault("professions", {})
            if "剑客" not in professions or not isinstance(professions.get("剑客"), dict):
                professions["剑客"] = ProfessionConfigStore._sword_profile()
        return data'''

if OLD_LOAD not in text2:
    # try flexible: if already partially hardened
    if "getattr(self, \"_ensure_builtin_profiles\"" in text2 or "getattr(self, '_ensure_builtin_profiles'" in text2:
        print("_load already hardened")
    else:
        raise SystemExit("_load block not found for harden")
else:
    text2 = text2.replace(OLD_LOAD, NEW_LOAD, 1)
    print("_load hardened")

UI.write_text(text2, encoding="utf-8")
py_compile.compile(str(UI), doraise=True)
print("syntax OK")

# structural asserts
assert "def _ensure_builtin_profiles" in text2
assert "def _sword_profile" in text2
assert text2.count("def _ensure_builtin_profiles") == 1
assert text2.count("def _sword_profile") == 1
print("structure OK")
