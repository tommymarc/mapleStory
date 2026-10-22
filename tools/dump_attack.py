# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\engine\MapleStoryAutoLevelUp.py")
lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
for a,b in [(1560,1620),(1740,1860),(2520,2580)]:
    print(f"\n===== {a}-{b} =====")
    for j in range(a-1, min(b, len(lines))):
        print(f"{j+1}: {lines[j]}")
# tommy diff
import yaml
for cfgp in [
    Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\dist\config\config_tommy.yaml"),
    Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\config\config_tommy.yaml"),
]:
    if cfgp.exists():
        d = yaml.safe_load(cfgp.read_text(encoding="utf-8"))
        md = (d or {}).get("monster_detect") or {}
        print(cfgp.name, "diff_thres", md.get("diff_thres"), "detect_every", md.get("detect_every_n_frames"), "max", md.get("template_max_files_per_monster"), "pref", md.get("template_name_prefixes"))
