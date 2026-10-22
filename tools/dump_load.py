# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\engine\MapleStoryAutoLevelUp.py")
lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
for j in range(300, 380):
    print(f"{j+1}: {lines[j]}")
print("--- attack filter ---")
# find where range_x used for monster in attack
for i, line in enumerate(lines):
    if "range_x" in line or "range_y" in line:
        if "directional" in line.lower() or "monster" in line.lower() or "attack" in line.lower() or "cx" in line or "abs(" in line:
            print(f"{i+1}: {line}")
