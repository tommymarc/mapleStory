# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\engine\MapleStoryAutoLevelUp.py")
lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
needles = [
    "template_max_files",
    "template_name_prefixes",
    "diff_thres",
    "detect_every_n_frames",
    "monster_track",
    "load_monster",
    "skip_turn_if_facing",
]
for i, line in enumerate(lines, 1):
    if any(n in line for n in needles):
        start = max(1, i - 2)
        end = min(len(lines), i + 8)
        print(f"\n===== around L{i} =====")
        for j in range(start, end + 1):
            print(f"{j}: {lines[j-1]}")
