# -*- coding: utf-8 -*-
"""Install nametag layer-choice + minimap reacquire patch on Windows.

Place this folder's files via CopyFromBox, then run:
  .venv\Scripts\python.exe tools\_install_nametag_layers.py
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# When run as tools/_install_*.py, patch files live next to this script OR in tools/nametag_layers_patch/
CANDIDATES = [
    Path(__file__).resolve().parent / "nametag_layers_payload",
    Path(__file__).resolve().parent,
    ROOT / "tools" / "nametag_layers_payload",
    Path(r"/workspace/nametag_layers_patch"),
]

def find_payload() -> Path:
    for c in CANDIDATES:
        if (c / "nametag.py").is_file() and (c / "ui.py").is_file():
            return c
    raise SystemExit("payload not found (need nametag.py + ui.py)")

def backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak_before_nametag_layers")
    if path.is_file() and not bak.is_file():
        shutil.copy2(path, bak)
        print("backup", bak)

def main() -> int:
    payload = find_payload()
    print("payload", payload)
    mapping = [
        (payload / "nametag.py", ROOT / "src" / "utils" / "nametag.py"),
        (payload / "ui.py", ROOT / "src" / "ui" / "ui.py"),
        (payload / "MapleStoryAutoLevelUp.py", ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"),
    ]
    for src, dst in mapping:
        if not src.is_file():
            print("MISSING", src)
            return 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup(dst)
        shutil.copy2(src, dst)
        print("installed", dst)

    # CHANGELOG
    entry = (payload / "CHANGELOG_ENTRY.md").read_text(encoding="utf-8")
    for cl in (ROOT / "docs" / "CHANGELOG.md", ROOT / "CHANGELOG.md"):
        if cl.is_file():
            backup(cl)
            text = cl.read_text(encoding="utf-8")
            if "一层 / 两层 / 三层" not in text:
                if text.startswith("#"):
                    nl = text.find("\n")
                    text = text[: nl + 1] + "\n" + entry + "\n" + text[nl + 1 :]
                else:
                    text = entry + "\n" + text
                cl.write_text(text, encoding="utf-8")
                print("changelog", cl)
            break

    # Sync 日丁 3-row template if present in payload
    for name in ("日丁.png", "日丁_3row.png"):
        src = payload / name
        if src.is_file():
            for dest_dir in (ROOT / "assets" / "nametag", ROOT / "dist" / "nametag", ROOT / "nametag"):
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / "日丁.png"
                if not (dest.with_suffix(dest.suffix + ".bak_before_guild3row")).exists() and dest.exists():
                    shutil.copy2(dest, dest.with_suffix(dest.suffix + ".bak_before_guild3row"))
                shutil.copy2(src, dest)
                print("template", dest)

    # Write default layers sidecar for 日丁 as 三层 recommendation
    import json
    for dest_dir in (ROOT / "assets" / "nametag", ROOT / "dist" / "nametag", ROOT / "nametag"):
        if dest_dir.is_dir():
            meta = dest_dir / "日丁.layers.json"
            meta.write_text(json.dumps({"layers": 3}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("sidecar", meta)

    print("DONE install. Rebuild next.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
