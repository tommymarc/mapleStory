# -*- coding: utf-8 -*-
import os
root = r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src"
keys = ("template_max_files", "template_name_prefixes", "diff_thres", "detect_every_n", "monster_track", "range_x")
for dp, dns, fns in os.walk(root):
    for f in fns:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        hits = [k for k in keys if k in t]
        if hits:
            print(p, "->", ",".join(hits))
