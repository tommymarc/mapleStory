# -*- coding: utf-8 -*-
from pathlib import Path
import os
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
keys = ("保存配置", "save_config", "on_save", "btn_save", "save_cfg", "save_yaml", "Save")
for dp, dns, fns in os.walk(ROOT / "src"):
    for f in fns:
        if not f.endswith(".py"):
            continue
        p = Path(dp) / f
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        hits = [k for k in keys if k in t]
        if hits:
            print(str(p.relative_to(ROOT)), "->", ",".join(hits))
