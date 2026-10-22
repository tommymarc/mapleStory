# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\engine\MapleStoryAutoLevelUp.py")
lines = p.read_text(encoding="utf-8").splitlines()
for a,b in [(900, 1220)]:
    for j in range(a-1, min(b, len(lines))):
        print(f"{j+1}: {lines[j]}")
