# -*- coding: utf-8 -*-
"""Install 日丁 3-row (name+guild+medal) nametag template and harden match logic.

Run on Windows:
  .\\.venv\\Scripts\\python.exe tools\\_install_3row_nametag.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) > 1:
    ROOT = Path(sys.argv[1])

SRC_PNG = Path(__file__).resolve().parent / "riding_3row_final.png"
# When copied to tools/, look beside script or in tools/
CANDIDATES = [
    SRC_PNG,
    Path(__file__).resolve().parent / "日丁_3row.png",
    ROOT / "tools" / "riding_3row_final.png",
    ROOT / "tools" / "日丁_3row.png",
]

NAME = "日丁"


def imread_unicode(path: Path):
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path: Path, image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise SystemExit(f"encode failed: {path}")
    buf.tofile(str(path))


def find_src() -> Path:
    for p in CANDIDATES:
        if p.exists():
            return p
    raise SystemExit("3-row png not found next to script")


def install_template(src: Path) -> tuple[tuple[int, int], tuple[int, int]]:
    img = imread_unicode(src)
    if img is None:
        raise SystemExit(f"cannot read {src}")
    new_hw = (img.shape[0], img.shape[1])

    targets = [
        ROOT / "assets" / "nametag" / f"{NAME}.png",
        ROOT / "nametag" / f"{NAME}.png",
        ROOT / "dist" / "nametag" / f"{NAME}.png",
        ROOT / "dist" / "assets" / "nametag" / f"{NAME}.png",
    ]
    old_hw = None
    for t in targets:
        if not t.parent.exists() and "assets" in t.parts:
            # assets layout may or may not exist
            continue
        if t.parent.exists() or t == targets[0]:
            t.parent.mkdir(parents=True, exist_ok=True)
        else:
            continue
        if t.exists():
            bak = t.with_suffix(".png.bak_before_guild3row")
            if not bak.exists():
                shutil.copy2(t, bak)
                print("backup", bak)
            old = imread_unicode(t)
            if old is not None and old_hw is None:
                old_hw = (old.shape[0], old.shape[1])
        imwrite_unicode(t, img)
        print("wrote", t, f"{new_hw[1]}x{new_hw[0]}")
    return old_hw or (0, 0), new_hw


def patch_nametag_py() -> bool:
    """Require ALL secondary bands (guild+medal) when template has 2+ secondaries."""
    path = ROOT / "src" / "utils" / "nametag.py"
    if not path.exists():
        print("skip code patch; missing", path)
        return False
    text = path.read_text(encoding="utf-8")
    bak = path.with_suffix(".py.bak_before_guild3row")
    if not bak.exists():
        shutil.copy2(path, bak)
        print("backup", bak)

    old = '''def _hard_secondary_ok(image, template, mask, bands, loc, scale_x, scale_y):
    """True when at least one secondary band matches under the candidate.

    Used only for hard two-row templates (name + medal/guild). A missing or
    mismatched medal rejects the candidate so other players / pet tags cannot
    lock on the name row alone.
    """
    secondary = list(_secondary_bands(bands))
    if not secondary:
        return True
    for _key, band in secondary:
        score = _band_score(
            image, template, mask, band, loc, scale_x, scale_y
        )
        if score < SECONDARY_ROW_MATCH_THRES:
            return True
    return False
'''
    new = '''def _hard_secondary_ok(image, template, mask, bands, loc, scale_x, scale_y):
    """Validate secondary bands under a hard multi-row candidate.

    - 1 secondary (classic name+medal): that band must match.
    - 2+ secondaries (name+guild+medal): **all** template secondary bands must
      match so a taller guild plate cannot lock on an obsolete 2-row template
      alignment, and short-name 日丁 stays unique with guild equipped.
    """
    secondary = list(_secondary_bands(bands))
    if not secondary:
        return True
    require_all = len(secondary) >= 2
    ok_any = False
    for _key, band in secondary:
        score = _band_score(
            image, template, mask, band, loc, scale_x, scale_y
        )
        hit = score < SECONDARY_ROW_MATCH_THRES
        if require_all and not hit:
            return False
        if hit:
            ok_any = True
    return ok_any
'''
    if old in text:
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")
        print("patched _hard_secondary_ok -> require-all when 3-row")
        return True

    # Already patched?
    if "require_all = len(secondary) >= 2" in text:
        print("nametag.py already has 3-row require-all secondary logic")
        return False

    # Try alternate wording (at least one) variants
    if "at least one secondary band" in text:
        # replace just the loop body logic via marker
        marker = "secondary = list(_secondary_bands(bands))\n    if not secondary:\n        return True\n"
        idx = text.find(marker)
        if idx < 0:
            raise SystemExit("cannot find secondary loop in nametag.py")
        # find end of function - next def
        end = text.find("\n\ndef ", idx)
        func_start = text.rfind("\ndef _hard_secondary_ok", 0, idx)
        if func_start < 0:
            func_start = text.rfind("def _hard_secondary_ok", 0, idx)
        if func_start < 0 or end < 0:
            raise SystemExit("cannot bound _hard_secondary_ok")
        # include leading newline
        text = text[:func_start] + "\n" + new + text[end:]
        path.write_text(text, encoding="utf-8")
        print("patched _hard_secondary_ok (alt path)")
        return True

    raise SystemExit("nametag.py _hard_secondary_ok block not found; inspect manually")


def touch_changelog() -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    if not path.exists():
        print("no CHANGELOG")
        return
    text = path.read_text(encoding="utf-8")
    entry = (
        "## 2026-09-22\n"
        "- nametag「日丁」: install 3-row template (云名「日丁」+ 公会「比比拉布」+「新手冒险家勋章」);"
        " hard match requires all secondary bands when guild+medal present;"
        " offset still from name-row top.\n\n"
    )
    if "比比拉布" in text and "2026-09-22" in text[:800]:
        print("CHANGELOG already mentions guild 3-row")
        return
    path.write_text(entry + text, encoding="utf-8")
    print("updated", path)


def verify(src_shape) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from utils import nametag as nt  # type: ignore

    path = None
    for p in [
        ROOT / "assets" / "nametag" / f"{NAME}.png",
        ROOT / "nametag" / f"{NAME}.png",
        ROOT / "dist" / "nametag" / f"{NAME}.png",
    ]:
        if p.exists():
            path = p
            break
    assert path is not None
    img = imread_unicode(path)
    bands = nt.parse_nametag_row_bands(img)
    print("verify bands", bands)
    assert bands.get("guild"), "guild band missing"
    assert bands.get("medal"), "medal band missing"
    g = (img[:, :, 1] > 250) & (img[:, :, 0] < 5) & (img[:, :, 2] < 5)
    mask = (~g).astype(np.uint8) * 255
    if mask.mean() < 1:
        mask = np.full(img.shape[:2], 255, np.uint8)
    h, w = img.shape[:2]
    pad = 40
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), (0, 255, 0), np.uint8)
    canvas[pad : pad + h, pad : pad + w] = img
    res = nt.find_best_nametag_match(
        canvas,
        img,
        mask,
        scales=[(1.0, 1.0)],
        search_box=(0, 0, canvas.shape[1], canvas.shape[0]),
        require_plate=True,
        min_plate_support=0.08,
    )
    print("verify self-match", res)
    assert res is not None and res[1] < 0.05, res


def main():
    print("ROOT", ROOT)
    src = find_src()
    print("src", src)
    old_hw, new_hw = install_template(src)
    print("size old HxW", old_hw, "-> new", new_hw)
    code_changed = patch_nametag_py()
    touch_changelog()
    try:
        verify(new_hw)
    except Exception as e:
        print("VERIFY WARN", e)
    print("CODE_CHANGED", code_changed)
    print("DONE — rebuild exe if CODE_CHANGED else restart bot to load new PNG")


if __name__ == "__main__":
    main()
