# -*- coding: utf-8 -*-
from pathlib import Path
lines = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\ui.py").read_text(encoding="utf-8").splitlines()
for j in range(639, 700):
    print(f"{j+1}: {lines[j]}")
