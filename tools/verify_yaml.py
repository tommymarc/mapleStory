# -*- coding: utf-8 -*-
from pathlib import Path
import yaml, py_compile
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
py_compile.compile(str(ROOT / "src" / "ui" / "profession_config.py"), doraise=True)
py_compile.compile(str(ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"), doraise=True)
print("compile OK")
for p in [ROOT / "config" / "config_professions.yaml", ROOT / "dist" / "config" / "config_professions.yaml"]:
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    ov = d["professions"]["剑客"]["overrides"]["monster_detect"]
    print(p.name, "selected=", d.get("selected_profession"), "md=", ov)
    assert ov["detect_every_n_frames"] == 2
    assert ov["diff_thres"] == 0.28
    assert ov["max_above_player_y"] == 90
# engine markers
eng = (ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py").read_text(encoding="utf-8")
assert "_select_balanced_monster_files" in eng
assert "max_above_player_y" in eng
print("all checks passed")
