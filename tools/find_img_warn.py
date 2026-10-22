# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
keys = ["找不到图片", "找不到", "Image not found", "图片", "QMessageBox", "nametag", "load_image", "FileNotFoundError"]
for rel in ["src/ui/ui.py", "src/utils/common.py", "src/utils/nametag.py", "src/engine/MapleStoryAutoLevelUp.py", "src/main.py"]:
    p = ROOT / rel
    if not p.exists():
        print("missing", rel)
        continue
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = []
    for i, line in enumerate(lines, 1):
        if any(k in line for k in ("找不到图片", "找不到", "Image not found", "无法读取", "图片不存在", "Image not found")):
            hits.append((i, line.strip()[:160]))
    print("===", rel, "hits", len(hits))
    for i, l in hits[:40]:
        print(f"  {i}: {l}")
