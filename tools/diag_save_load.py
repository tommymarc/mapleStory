# -*- coding: utf-8 -*-
from pathlib import Path
import re
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")

def show(p: Path):
    print("===", p.relative_to(ROOT) if p.exists() else p, "size", p.stat().st_size if p.exists() else "MISSING")
    if not p.exists() or p.stat().st_size == 0:
        return None
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(d, dict):
        print(" not dict", type(d))
        return d
    print(" top keys:", list(d.keys()))
    for k in ["bot", "attack", "nametag", "name_tag", "player", "health_monitor", "game_window", "monster", "key", "party"]:
        if k in d:
            v = d[k]
            if isinstance(v, dict):
                print(f"  {k}: dict keys={list(v.keys())[:20]}")
            else:
                print(f"  {k}:", v)
    return d

files = [
    ROOT / "config/config_custom.yaml",
    ROOT / "dist/config/config_custom.yaml",
    ROOT / "config/config_tommy.yaml",
    ROOT / "dist/config/config_tommy.yaml",
    ROOT / "config/config.yaml",
    ROOT / "dist/config/config.yaml",
]
for f in files:
    show(f)

ui = (ROOT / "src/ui/ui.py").read_text(encoding="utf-8")
for name in ["save_current_config", "_write_current_config", "get_cfg_diff", "load_config", "load_custom", "open_config", "选择", "加载", "apply_cfg", "update_ui", "update_cfg_from_main_ui", "path_cfg_custom"]:
    idxs = [m.start() for m in re.finditer(re.escape(name), ui)]
    print(f"ui mentions {name!r}: {len(idxs)}")

# extract key defs
for pat in [r"def save_current_config[\s\S]*?(?=\n    def )", r"def _write_current_config[\s\S]*?(?=\n    def )", r"def load_[\w]+[\s\S]*?(?=\n    def )", r"def .*[Ll]oad.*[\s\S]{0,80}"]:
    pass

# find load-related methods
for m in re.finditer(r"def (\w*(?:load|Load|open|Open|import|Import)\w*)\(", ui):
    print("def", m.group(1), "at", m.start())

# print save/write bodies
for fn in ["save_current_config", "_write_current_config", "load_config_file", "load_cfg", "on_load", "browse_config"]:
    i = ui.find(f"def {fn}")
    if i < 0:
        continue
    j = ui.find("\n    def ", i + 1)
    print("\n########", fn)
    print(ui[i:j][:2500])
