# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\engine\MapleStoryAutoLevelUp.py")
lines = p.read_text(encoding="utf-8").splitlines()
# find update_player / nametag return / pick candidate sections
needles = ["def update_player", "def _update_player", "pick_nametag_candidate", "search_left", "loc_player", "hold_good", "biased_box"]
for i, line in enumerate(lines):
    for n in needles:
        if n in line and ("def " in line or "nametag" in line.lower() or "search_" in line or "biased" in line or "hold_good" in line):
            print(f"{i+1}: {line}")
            break
print("--- find_player / get_player ---")
for i, line in enumerate(lines):
    if "def " in line and ("player" in line.lower() or "nametag" in line.lower()) and "def _" in line:
        if any(k in line for k in ("nametag", "player_loc", "locate", "find_player", "get_player")):
            print(f"{i+1}: {line}")
