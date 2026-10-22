# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
for rel in ["src/ui/ui.py", "src/ui/profession_config.py", "src/ui/resource_tabs.py", "src/ui/map_manage.py"]:
    p = ROOT / rel
    if not p.exists():
        continue
    lines = p.read_text(encoding="utf-8").splitlines()
    print("====", rel)
    for i, line in enumerate(lines):
        if any(x in line for x in ("保存", "QPushButton", "save_", "triggered.connect", "clicked.connect")):
            if any(x in line for x in ("保存", "save", "Save", "写入")):
                print(f"{i+1}: {line}")
