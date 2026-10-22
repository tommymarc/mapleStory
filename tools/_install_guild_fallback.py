# -*- coding: utf-8 -*-
"""Install guild-layer nametag fallback + monster_detect.detect_every_n_frames=1.

On Windows (cmd, project root):
  taskkill /F /IM MapleStory.exe 2>nul
  .venv/Scripts/python.exe tools/_install_guild_fallback.py
  py -3 C:/Users/Administrator/do_rebuild_ms.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [
    Path(__file__).resolve().parent / "guild_fb_payload",
    Path(__file__).resolve().parent,
    ROOT / "tools" / "guild_fb_payload",
    Path(r"/workspace/guild_fb/payload"),
]


def find_payload() -> Path:
    for c in CANDIDATES:
        if (c / "nametag.py").is_file() and (c / "MapleStoryAutoLevelUp.py").is_file():
            return c
    raise SystemExit("payload not found (need nametag.py + MapleStoryAutoLevelUp.py)")


def backup(path: Path) -> None:
    if not path.is_file():
        return
    bak = path.with_suffix(path.suffix + ".bak_before_guild_fb")
    if not bak.is_file():
        shutil.copy2(path, bak)
        print("backup", bak)


def upsert_keys(path: Path, section: str, keys: dict) -> None:
    if not path.is_file():
        print("skip missing", path)
        return
    text = path.read_text(encoding="utf-8")
    orig = text
    m = re.search(rf"(?m)^({re.escape(section)}:\n)((?:  .*\n)*)", text)
    if not m:
        print("WARN no section", section, "in", path)
        return
    head, body = m.group(1), m.group(2)
    for key, value in keys.items():
        pat = re.compile(rf"(?m)^  {re.escape(key)}:.*$")
        repl = f"  {key}: {value}"
        if pat.search(body):
            body = pat.sub(repl, body, count=1)
        else:
            if body and not body.endswith("\n"):
                body += "\n"
            body += repl + "\n"
    text = text[: m.start()] + head + body + text[m.end() :]
    if text != orig:
        backup(path)
        path.write_text(text, encoding="utf-8")
        print("yaml", path, "->", list(keys))
    else:
        print("yaml", path, "ok")


def main() -> int:
    payload = find_payload()
    print("payload", payload)

    pairs = [
        (payload / "nametag.py", ROOT / "src" / "utils" / "nametag.py"),
        (
            payload / "MapleStoryAutoLevelUp.py",
            ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py",
        ),
        (
            payload / "config_default.yaml",
            ROOT / "config" / "config_default.yaml",
        ),
    ]
    for src, dst in pairs:
        if not src.is_file():
            print("MISSING", src)
            return 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup(dst)
        shutil.copy2(src, dst)
        print("installed", dst)

    dist_default = ROOT / "dist" / "config" / "config_default.yaml"
    dist_default.parent.mkdir(parents=True, exist_ok=True)
    backup(dist_default)
    shutil.copy2(payload / "config_default.yaml", dist_default)
    print("installed", dist_default)

    nametag_keys = {
        "guild_fallback_enable": "true",
        "guild_fallback_after_misses": "2",
    }
    monster_keys = {
        "detect_every_n_frames": "1",
        "template_max_files_per_monster": "10",
    }

    for custom in (
        ROOT / "config" / "config_custom.yaml",
        ROOT / "dist" / "config" / "config_custom.yaml",
    ):
        if not custom.is_file() and (payload / "config_custom.yaml").is_file():
            custom.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(payload / "config_custom.yaml", custom)
            print("seeded", custom)
        upsert_keys(custom, "nametag", nametag_keys)
        upsert_keys(custom, "monster_detect", monster_keys)

    for default in (
        ROOT / "config" / "config_default.yaml",
        ROOT / "dist" / "config" / "config_default.yaml",
    ):
        upsert_keys(default, "monster_detect", monster_keys)
        upsert_keys(default, "nametag", nametag_keys)

    print("DONE. Next: py -3 C:\\Users\\Administrator\\do_rebuild_ms.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
