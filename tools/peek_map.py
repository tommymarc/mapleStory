# -*- coding: utf-8 -*-
from pathlib import Path
import yaml
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
for name in ["dist/config/config_tommy.yaml", "config/config_tommy.yaml"]:
    p = ROOT / name
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    bot = d.get("bot") or {}
    print(name, "map=", bot.get("map"), "mode=", bot.get("mode"), "attack=", bot.get("attack"))
    md = d.get("monster_detect") or {}
    print("  monster_detect keys sample", {k: md.get(k) for k in ["diff_thres","mode","detect_every_n_frames","template_name_prefixes","template_max_files_per_monster"]})
# map mobs mapping
data = None
for cand in [ROOT/"src/data", ROOT/"data", ROOT/"assets"]:
    pass
# find map_mobs
import os
for dp,dns,fns in os.walk(ROOT/"src"):
    for f in fns:
        if "mob" in f.lower() or "map" in f.lower():
            if f.endswith((".yaml",".yml",".json",".py")):
                print("cand", Path(dp)/f)
