# -*- coding: utf-8 -*-
from pathlib import Path
import yaml
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
for rel in [
    "config/config_tommy.yaml",
    "dist/config/config_tommy.yaml",
    "config/config_professions.yaml",
    "dist/config/config_professions.yaml",
]:
    p = ROOT / rel
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        print(rel, "OK", type(d).__name__, list(d)[:10] if isinstance(d, dict) else d)
    except Exception as e:
        print(rel, "FAIL", e)
