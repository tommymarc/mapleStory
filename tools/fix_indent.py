# -*- coding: utf-8 -*-
from pathlib import Path

UI = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py")
text = UI.read_text(encoding="utf-8")
# Find broken region
start = text.find("def _sword_profile")
# include possible bad indent before def
while start > 0 and text[start-1] in " \t":
    start -= 1
# find previous newline
nl = text.rfind("\n", 0, start)
start = nl + 1
# end at next top-level method of class (4 spaces + @ or def at class level)
# look for "\n    def " or "\n    @" after start+10 that is NOT more indented body
i = start + 10
end = None
while True:
    n1 = text.find("\n    @staticmethod", i)
    n2 = text.find("\n    def ", i)
    candidates = [c for c in (n1, n2) if c != -1]
    if not candidates:
        raise SystemExit("cannot find end")
    end = min(candidates)
    # ensure this is class-level (exactly 4 spaces after newline)
    break

NEW = '''    @staticmethod
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

'''
# If we already have @staticmethod before def in the slice, include it in replacement start
# Adjust start to include @staticmethod if present just above
prev = text.rfind("@staticmethod", 0, start + 20)
if prev != -1 and text[prev:start+20].count("\n") <= 2:
    # include from @staticmethod line
    start = text.rfind("\n", 0, prev) + 1

print("replacing from", repr(text[start:start+60]), "to", repr(text[end:end+40]))
text2 = text[:start] + NEW + text[end+1:]  # end points at \n before next method; keep that newline via NEW ending
# Actually end is index of \n    @staticmethod — we should keep from end inclusive
text2 = text[:start] + NEW + text[end+1:]
# Wait: end is "\n    @staticmethod" — if we do text[end+1:] we drop the newline and keep "    @staticmethod"
# Better: text2 = text[:start] + NEW + text[end+1:] where NEW ends with newline and text[end+1:] starts with "    @staticmethod"
UI.write_text(text2, encoding="utf-8")
# compile check
compile(text2, str(UI), "exec")
print("syntax OK")
