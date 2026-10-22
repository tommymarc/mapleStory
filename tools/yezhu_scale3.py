# -*- coding: utf-8 -*-
"""Estimate screen:minimap scale from two yezhulingtu frames with different minimap X."""
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
    from src.utils import nametag as nt

    player_color = tuple((cfg.get("minimap") or {}).get("player_color") or [0, 255, 255])
    ncfg = cfg.get("nametag") or {}

    # load template
    tpath = None
    for cand in [
        ROOT / "dist/assets/nametag/日丁.png",
        ROOT / "assets/nametag/日丁.png",
        ROOT / "dist/assets/nametags/日丁.png",
    ]:
        if cand.exists():
            tpath = cand
            break
    # glob
    if tpath is None:
        for p in (ROOT / "dist/assets").rglob("*.png"):
            if "丁" in p.name or "nametag" in str(p).lower():
                print("cand", p)
        for p in ROOT.rglob("*丁*.png"):
            print("tag", p)

    shots = [
        ROOT / "dist/screenshot/2026-09-21_00-21-54_img_frame.png",
        ROOT / "dist/screenshot/2026-09-21_01-11-20_img_frame.png",
    ]

    # Try engine nametag locate if template exists
    results = []
    for shot in shots:
        fr = imread_unicode(shot)
        loc = get_minimap_loc_size(fr)
        x, y, w, h = loc
        crop = fr[y : y + h, x : x + w]
        pl = get_player_location_on_minimap(crop, minimap_player_color=player_color)
        # Heuristic screen player: search cyan/cloud plate OR use center-ish
        # Use party/name cyan-ish mask in play field
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        # cyan plate
        mask = cv2.inRange(hsv, (80, 40, 120), (110, 255, 255))
        # ignore top HUD
        mask[:120, :] = 0
        mask[:, :200] = 0
        ys, xs = np.where(mask > 0)
        screen_xy = None
        if len(xs) > 30:
            # largest blob centroid
            num, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
            best = None
            for i in range(1, num):
                area = stats[i, cv2.CC_STAT_AREA]
                if area < 40:
                    continue
                cx, cy = cents[i]
                if best is None or area > best[0]:
                    best = (area, cx, cy)
            if best:
                screen_xy = (best[1], best[2])
        print(f"{shot.name}: minimap_player={pl} screen_cyan_cent={screen_xy} minimap={w}x{h}")
        results.append((pl, screen_xy, (w, h), fr.shape[1], fr.shape[0]))

    if len(results) >= 2 and results[0][0] and results[1][0] and results[0][1] and results[1][1]:
        (mx0, my0), (sx0, sy0), _, fw, fh = results[0]
        (mx1, my1), (sx1, sy1), _, _, _ = results[1]
        dmx = mx1 - mx0
        dmy = my1 - my0
        dsx = sx1 - sx0
        dsy = sy1 - sy0
        print(f"delta minimap=({dmx},{dmy}) screen=({dsx:.1f},{dsy:.1f})")
        if abs(dmx) >= 5:
            print(f"scale X screen_px / minimap_px = {dsx/dmx:.3f}")
        if abs(dmy) >= 5:
            print(f"scale Y screen_px / minimap_px = {dsy/dmy:.3f}")
        elif abs(dmx) >= 5:
            print("Y delta too small for reliable Y scale")
    else:
        print("could not pair both frames with screen+minimap points")


if __name__ == "__main__":
    main()
