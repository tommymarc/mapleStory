# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
lines = (ROOT/"src/ui/ui.py").read_text(encoding="utf-8").splitlines()
# print open_keyboard_config and refresh_profession_selector fully
for name in ("def open_keyboard_config", "def refresh_profession_selector", "def apply_config_to_ui"):
    for i, line in enumerate(lines):
        if line.startswith(f"    {name}") or line.startswith(f"    def {name.split()[-1]}"):
            # print until next def at same indent
            print(f"\n===== {name} @ {i+1} =====")
            for j in range(i, len(lines)):
                print(f"{j+1}: {lines[j]}")
                if j > i and lines[j].startswith("    def "):
                    break
            break

# Also check if home widgets used in update_cfg exist - AttributeError common cause
for needle in ("home_attack_cooldown", "home_hp_percent", "window_title_edit", "profession_combo", "selected_map"):
    hits = [i+1 for i,l in enumerate(lines) if needle in l]
    print(needle, "count", len(hits), "first", hits[:5])
