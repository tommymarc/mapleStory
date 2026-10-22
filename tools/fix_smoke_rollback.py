# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\tools\smoke_profession_store.py")
text = p.read_text(encoding="utf-8")
old = '''        ov = profile.get("overrides") or {}
        md = ov.get("monster_detect") or {}
        assert "diff_thres" in md, md
        assert "max_above_player_y" in md, md
'''
new = '''        ov = profile.get("overrides") or {}
        md = ov.get("monster_detect") or {}
        assert "detect_every_n_frames" in md, md
        assert "template_name_prefixes" in md, md
        assert "stand" in md.get("template_name_prefixes", []), md
'''
if old not in text:
    if "diff_thres" not in text:
        print("smoke already updated")
    else:
        raise SystemExit("smoke assert block not found")
else:
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("smoke updated for pre-balance sword overrides")
