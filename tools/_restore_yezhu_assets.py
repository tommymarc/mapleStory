# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
import zipfile
import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
MAP_SRC = ROOT / "tools" / "_yezhulingtu_map.png"
PATROL_SRC = Path(r"C:\Users\Administrator\.maplebot\maps\yezhulingtu")
ZIP_PATH = Path(r"C:\Users\Administrator\Downloads\野猪.zip")


def write_png(path: Path, img) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise SystemExit(f"encode failed {path}")
    buf.tofile(str(path))


def main() -> None:
    img = cv2.imdecode(np.fromfile(str(MAP_SRC), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit("map png missing")
    print("map", img.shape)

    for base in [
        ROOT / "assets" / "minimaps" / "yezhulingtu",
        ROOT / "dist" / "assets" / "minimaps" / "yezhulingtu",
    ]:
        write_png(base / "map.png", img)
        for name in ("patrol.yaml", "ropes.yaml"):
            src = PATROL_SRC / name
            if src.exists():
                shutil.copy2(src, base / name)
                print("copied", name, "->", base)
        print("map folder", base, "files", [p.name for p in base.iterdir()])

    if not ZIP_PATH.exists():
        raise SystemExit(f"missing {ZIP_PATH}")
    for base in [
        ROOT / "assets" / "monster" / "野猪",
        ROOT / "dist" / "assets" / "monster" / "野猪",
    ]:
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ZIP_PATH) as zf:
            zf.extractall(base)
        print("monster", base, sorted(p.name for p in base.iterdir()))

    # Merge yezhulingtu into source config overrides (keep existing maps)
    ov = ROOT / "config" / "config_resource_overrides.yaml"
    text = ov.read_text(encoding="utf-8") if ov.exists() else ""
    if "yezhulingtu" not in text:
        # append mapping blocks carefully
        extra = (
            "\n"
            "  yezhulingtu: yezhulingtu\n"
            "  yezhudelingdi: yezhudelingdi\n"
            "  野猪: 野猪\n"
        )
        if "eng_to_cn:" in text:
            text = text.replace("eng_to_cn:\n", "eng_to_cn:\n" + extra.lstrip("\n"), 1)
        else:
            text += "\neng_to_cn:\n" + extra
        if "map_mobs_mapping:" in text:
            text += (
                "  yezhulingtu:\n"
                "  - 野猪\n"
                "  - 刺骨头木妖\n"
                "  yezhudelingdi:\n"
                "  - 野猪\n"
                "  - 刺骨头木妖\n"
            )
            # fix if wrong monster name - check existing folders
        else:
            text += (
                "\nmap_mobs_mapping:\n"
                "  yezhulingtu:\n"
                "  - 野猪\n"
            )
        ov.write_text(text, encoding="utf-8")
        print("updated", ov)
    else:
        print("overrides already mention yezhulingtu")

    # Fix monster name in mapping to match actual folders
    monsters = [p.name for p in (ROOT / "assets" / "monster").iterdir() if p.is_dir()]
    print("monster folders:", monsters)

    # Sync dist overrides map_mobs for yezhulingtu if file is the fat one
    dov = ROOT / "dist" / "config" / "config_resource_overrides.yaml"
    if dov.exists() and "yezhulingtu" in dov.read_text(encoding="utf-8"):
        print("dist overrides already has yezhulingtu")
    print("DONE")


if __name__ == "__main__":
    main()
