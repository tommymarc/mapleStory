# -*- coding: utf-8 -*-
"""Install nametag FP-gate patch + tight 日丁 template on Windows project."""
from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "src").is_dir():
    # tools/nametag_fp_gate_payload/_install... → parents[2] = project
    ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = Path(__file__).resolve().parent

FILES = {
    "nametag.py": ROOT / "src" / "utils" / "nametag.py",
    "MapleStoryAutoLevelUp.py": ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py",
    "ui.py": ROOT / "src" / "ui" / "ui.py",
}

TEMPLATE_TARGETS = [
    ROOT / "assets" / "nametag" / "日丁.png",
    ROOT / "nametag" / "日丁.png",
    ROOT / "dist" / "assets" / "nametag" / "日丁.png",
    ROOT / "dist" / "nametag" / "日丁.png",
]


def main() -> int:
    print("ROOT", ROOT)
    if not (ROOT / "src").is_dir():
        print("ERROR: project root not found", file=sys.stderr)
        return 2

    for name, dest in FILES.items():
        src = PAYLOAD / name
        if not src.is_file():
            print("ERROR missing", src, file=sys.stderr)
            return 2
        dest.parent.mkdir(parents=True, exist_ok=True)
        # backup once
        bak = dest.with_suffix(dest.suffix + ".bak_fp_gate")
        if dest.is_file() and not bak.exists():
            shutil.copy2(dest, bak)
            print("backup", bak)
        shutil.copy2(src, dest)
        ast.parse(dest.read_text(encoding="utf-8"))
        print("installed", dest)

    tmpl = PAYLOAD / "日丁.png"
    side = PAYLOAD / "日丁.layers.json"
    if not tmpl.is_file():
        print("ERROR missing template", tmpl, file=sys.stderr)
        return 2
    meta = {"layers": 3}
    if side.is_file():
        meta = json.loads(side.read_text(encoding="utf-8"))
    for dest in TEMPLATE_TARGETS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmpl, dest)
        dest.with_name("日丁.layers.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("template", dest)

    # CHANGELOG
    entry = (PAYLOAD / "CHANGELOG_ENTRY.md").read_text(encoding="utf-8")
    clog = ROOT / "docs" / "CHANGELOG.md"
    clog.parent.mkdir(parents=True, exist_ok=True)
    if clog.is_file():
        text = clog.read_text(encoding="utf-8")
        if "名片定位防误锁" not in text and "nametag FP-gate" not in text:
            # Insert after title
            lines = text.splitlines(True)
            if lines and lines[0].lstrip().startswith("#"):
                # after first blank line following title block
                insert_at = 1
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
                while insert_at < len(lines) and not lines[insert_at].startswith("#"):
                    # keep going past intro paragraph until next ## or end of intro
                    if lines[insert_at].startswith("##"):
                        break
                    insert_at += 1
                lines.insert(insert_at, "\n" + entry.rstrip() + "\n\n")
                clog.write_text("".join(lines), encoding="utf-8")
            else:
                clog.write_text(entry.rstrip() + "\n\n" + text, encoding="utf-8")
            print("changelog updated", clog)
        else:
            print("changelog already has entry")
    else:
        clog.write_text("# Changelog / 迭代日记\n\n" + entry.rstrip() + "\n", encoding="utf-8")
        print("changelog created", clog)

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
