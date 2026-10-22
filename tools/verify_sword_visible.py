# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
from src.ui.profession_config import ProfessionConfigStore
for path in ("dist/config/config_professions.yaml", "config/config_professions.yaml"):
    s = ProfessionConfigStore(str(ROOT / path))
    print(path, "names=", s.names(), "selected=", s.selected_name())
    p = s.get("剑客") or {}
    print("  overrides=", bool(p.get("overrides")), "keys=", list((p.get("overrides") or {}).keys()))
