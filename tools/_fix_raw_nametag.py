# -*- coding: utf-8 -*-
from pathlib import Path
import ast
import json
import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
RAW = ROOT / "tools" / "日丁_user_raw.png"

HELPER = r'''
def nametag_match_mask(image):
    """Build match mask without requiring a green-matted template file.

    If pure chroma green is present (legacy assets), ignore those pixels.
    Otherwise treat corner-similar sandy/terrain pixels as background and keep
    the natural name/guild/medal pixels from the user's original crop.
    """
    bgr = as_bgr(image)
    if bgr is None or bgr.size == 0:
        return None
    height, width = bgr.shape[:2]
    green = (
        (bgr[:, :, 0] <= 20)
        & (bgr[:, :, 1] >= 230)
        & (bgr[:, :, 2] <= 20)
    )
    if float(green.mean()) >= 0.02:
        return ((~green).astype(np.uint8) * 255)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.int16)
    bg = np.zeros((height, width), dtype=np.uint8)
    for y, x in ((0, 0), (0, width - 1), (height - 1, 0), (height - 1, width - 1)):
        c = hsv[y, x]
        dh = np.minimum(np.abs(hsv[:, :, 0] - c[0]), 180 - np.abs(hsv[:, :, 0] - c[0]))
        ds = np.abs(hsv[:, :, 1] - c[1])
        dv = np.abs(hsv[:, :, 2] - c[2])
        near = (dh <= 18) & (ds <= 45) & (dv <= 45)
        bg[near] = 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bg = cv2.morphologyEx(bg, cv2.MORPH_CLOSE, kernel, iterations=1)
    plates = plate_mask(bgr)
    keep = cv2.bitwise_or(cv2.bitwise_not(bg), plates)
    if float(keep.mean()) < 8:
        return np.full((height, width), 255, dtype=np.uint8)
    return keep


'''


def main():
    assert RAW.exists(), RAW
    img = cv2.imdecode(np.fromfile(str(RAW), dtype=np.uint8), cv2.IMREAD_COLOR)
    print("raw", img.shape)
    targets = [
        ROOT / "assets" / "nametag" / "日丁.png",
        ROOT / "nametag" / "日丁.png",
        ROOT / "dist" / "assets" / "nametag" / "日丁.png",
        ROOT / "dist" / "nametag" / "日丁.png",
    ]
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(".png", img)
        assert ok
        buf.tofile(str(t))
        side = t.with_name("日丁.layers.json")
        side.write_text(json.dumps({"layers": 3}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", t)

    nt_path = ROOT / "src" / "utils" / "nametag.py"
    nt = nt_path.read_text(encoding="utf-8")
    if "def nametag_match_mask" not in nt:
        anchor = "def _iter_boxes_from_mask("
        if anchor not in nt:
            raise SystemExit("anchor missing")
        nt = nt.replace(anchor, HELPER + anchor, 1)
        print("inserted nametag_match_mask")
    else:
        print("nametag_match_mask already present")

    old_green = (
        "            if layers is not None:\n"
        "                name_crop = crop_nametag_to_layers(name_crop, min(int(layers), 1) or 1)\n"
        "            return _on_green_chroma(name_crop, pad=2)"
    )
    new_green = (
        "            if layers is not None:\n"
        "                name_crop = crop_nametag_to_layers(name_crop, min(int(layers), 1) or 1)\n"
        "            return name_crop"
    )
    if old_green in nt:
        nt = nt.replace(old_green, new_green, 1)
        print("removed green chroma wrap")
    else:
        print("green wrap path not found")

    nt_path.write_text(nt, encoding="utf-8")

    eng_path = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"
    eng = eng_path.read_text(encoding="utf-8")
    if "nametag_match_mask" not in eng:
        if "prepare_nametag_template," in eng:
            eng = eng.replace(
                "prepare_nametag_template,",
                "prepare_nametag_template,\n    nametag_match_mask,",
                1,
            )
            print("import added")
        else:
            raise SystemExit("cannot find nametag import")

    old_mask = "mask = get_mask(self.img_nametag, (0, 255, 0))"
    count = eng.count(old_mask)
    eng = eng.replace(old_mask, "mask = nametag_match_mask(self.img_nametag)")
    print("mask replacements", count)
    eng_path.write_text(eng, encoding="utf-8")

    g = ((img[:, :, 1] > 230) & (img[:, :, 0] < 20) & (img[:, :, 2] < 20)).mean()
    print("installed green frac", float(g))
    ast.parse(nt_path.read_text(encoding="utf-8"))
    ast.parse(eng_path.read_text(encoding="utf-8"))
    print("syntax ok")


if __name__ == "__main__":
    main()
