# -*- coding: utf-8 -*-
"""Install shutdown-monitor feature into MapleStoryAutoLevelUp on Windows."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# tools/shutdown_monitor_payload/... -> repo root
ROOT = HERE.parents[1] if HERE.parent.name.lower() in {"tools", "shutdown_monitor_payload"} else HERE.parents[0]
# Prefer: <repo>/tools/shutdown_monitor_payload/_install... -> parents[1] = repo
# Also support running from payload next to sources during box testing
candidates = [
    HERE.parents[1],  # tools/xxx -> root
    HERE.parents[0],
    Path.cwd(),
]
ROOT = None
for c in candidates:
    if (c / "src" / "ui" / "ui.py").exists() and (c / "src" / "engine" / "MapleStoryAutoLevelUp.py").exists():
        ROOT = c
        break
if ROOT is None:
    # fallback: walk up
    p = HERE
    for _ in range(5):
        if (p / "src" / "ui" / "ui.py").exists():
            ROOT = p
            break
        p = p.parent
if ROOT is None:
    raise SystemExit("Cannot locate project root (src/ui/ui.py missing)")

MAP = {
    "ui.py": ROOT / "src" / "ui" / "ui.py",
    "MapleStoryAutoLevelUp.py": ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py",
    "config_default.yaml": ROOT / "config" / "config_default.yaml",
}

def backup(path: Path):
    if not path.exists():
        return
    bak = path.with_suffix(path.suffix + ".bak_shutdown_monitor")
    if not bak.exists():
        shutil.copy2(path, bak)
        print("backup", bak)

def main():
    print("ROOT", ROOT)
    for name, dest in MAP.items():
        src = HERE / name
        if not src.exists():
            raise SystemExit(f"missing payload file: {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup(dest)
        shutil.copy2(src, dest)
        print("installed", dest)

    # Also ensure dist/config has the key if dist config_default exists
    dist_cfg = ROOT / "dist" / "config" / "config_default.yaml"
    if dist_cfg.exists():
        backup(dist_cfg)
        shutil.copy2(HERE / "config_default.yaml", dist_cfg)
        print("installed", dist_cfg)

    print("OK: shutdown monitor files installed. Rebuild with tools\\build_exe.bat")

if __name__ == "__main__":
    main()
