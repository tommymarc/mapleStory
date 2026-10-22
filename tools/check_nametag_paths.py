# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
for rel in ["assets/nametag", "dist/assets/nametag"]:
    d = ROOT / rel
    print("===", rel, "exists", d.exists())
    if d.exists():
        for f in sorted(d.iterdir()):
            print(" ", f.name, f.stat().st_size)
