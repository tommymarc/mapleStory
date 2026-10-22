# -*- coding: utf-8 -*-
from __future__ import annotations
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = None
for c in [HERE.parents[1], HERE.parents[0], Path.cwd()]:
    if (c / "src" / "engine" / "MapleStoryAutoLevelUp.py").exists():
        ROOT = c
        break
if ROOT is None:
    raise SystemExit("project root not found")

MAP = {
    "MapleStoryAutoLevelUp.py": ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py",
    "config_default.yaml": ROOT / "config" / "config_default.yaml",
}

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + ".bak_dual_nametag")
        if not bak.exists():
            shutil.copy2(p, bak)
            print("backup", bak)

for name, dest in MAP.items():
    src = HERE / name
    if not src.exists():
        raise SystemExit(f"missing {src}")
    backup(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print("installed", dest)

dist_cfg = ROOT / "dist" / "config" / "config_default.yaml"
if dist_cfg.exists():
    backup(dist_cfg)
    shutil.copy2(HERE / "config_default.yaml", dist_cfg)
    print("installed", dist_cfg)

# merge tommy
import runpy
runpy.run_path(str(HERE / "merge_tommy_nametag.py"), run_name="__main__")
print("OK dual nametag installed")
