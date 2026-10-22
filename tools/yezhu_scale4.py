# -*- coding: utf-8 -*-
"""Estimate screen/minimap scale via background scroll between two frames."""
import sys
from pathlib import Path
import numpy as np
import cv2
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def imread_unicode(path: Path):
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def main():
    cfg = yaml.safe_load((ROOT / "dist/config/.config_tmp.yaml").read_text(encoding="utf-8"))
    from src.utils.common import get_minimap_loc_size, get_player_location_on_minimap

    player_color = tuple((cfg.get("minimap") or {}).get("player_color") or [0, 255, 255])
    paths = [
        ROOT / "dist/screenshot/2026-09-21_00-21-54_img_frame.png",
        ROOT / "dist/screenshot/2026-09-21_01-11-20_img_frame.png",
    ]
    frames = []
    mpos = []
    for p in paths:
        fr = imread_unicode(p)
        x, y, w, h = get_minimap_loc_size(fr)
        crop = fr[y : y + h, x : x + w]
        pl = get_player_location_on_minimap(crop, minimap_player_color=player_color)
        frames.append(fr)
        mpos.append(pl)
        print(p.name, "minimap_player", pl, "minimap", w, h)

    a, b = frames
    # Playfield ROI: exclude minimap/HUD top and bottom UI
    y0, y1 = 120, 560
    x0, x1 = 80, 1210
    ra = a[y0:y1, x0:x1]
    rb = b[y0:y1, x0:x1]
    # Use phase correlation / template: take a patch from A left of center, find in B
    ph, pw = ra.shape[:2]
    # several patches
    scales = []
    for cx, cy, tw, th in [
        (200, 200, 160, 100),
        (400, 180, 160, 100),
        (600, 220, 160, 100),
        (250, 300, 140, 90),
        (500, 320, 140, 90),
    ]:
        if cy + th >= ph or cx + tw >= pw:
            continue
        patch = ra[cy : cy + th, cx : cx + tw]
        res = cv2.matchTemplate(rb, patch, cv2.TM_CCOEFF_NORMED)
        minv, maxv, minl, maxl = cv2.minMaxLoc(res)
        if maxv < 0.55:
            print(f"patch({cx},{cy}) weak match {maxv:.3f}")
            continue
        dx = maxl[0] - cx
        dy = maxl[1] - cy
        print(f"patch({cx},{cy}) match={maxv:.3f} scroll_screen=({dx},{dy})")
        scales.append((dx, dy, maxv))

    dmx = mpos[1][0] - mpos[0][0]
    dmy = mpos[1][1] - mpos[0][1]
    print(f"delta minimap player = ({dmx}, {dmy})")
    # Camera-follow: when player moves right on minimap, world scrolls left on screen
    # so screen_scroll_x ≈ -scale * dmx  => scale = -dx / dmx
    if abs(dmx) >= 3 and scales:
        # weighted by match score
        sx = []
        sy = []
        for dx, dy, sc in scales:
            sx.append((-dx / dmx, sc))
            if abs(dmy) >= 3:
                sy.append((-dy / dmy, sc))
        def wavg(pairs):
            num = sum(v * w for v, w in pairs)
            den = sum(w for _, w in pairs)
            return num / den
        scale_x = wavg(sx)
        print(f"estimated scale X (screen_px per minimap_px) = {scale_x:.3f}")
        if sy:
            print(f"estimated scale Y (screen_px per minimap_px) = {wavg(sy):.3f}")
        else:
            print("Y: minimap delta too small; X-only estimate")
        print(
            "Interpretation: walking 1 minimap pixel moves background ~"
            f"{abs(scale_x):.3f} screen pixels (camera follow)."
        )


if __name__ == "__main__":
    main()
