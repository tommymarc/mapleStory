# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT / "src"))
from ui.profession_config import ProfessionConfigStore
s = ProfessionConfigStore(ROOT / "dist" / "config" / "config_professions.yaml")
print("names", s.list_names())
p = s.get("剑客") or {}
print("overrides", p.get("overrides"))
print("selected", s.selected_name())
