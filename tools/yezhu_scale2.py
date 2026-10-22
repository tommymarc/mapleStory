# -*- coding: utf-8 -*-
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
    print("map=", cfg.get("bot", {}).get("map"))
    print("mode=", cfg.get("bot", {}).get("mode"))
    print("character WxH=", cfg.get("character", {}).get("width"), cfg.get("character", {}).get("height"))
    mmcfg = cfg.get("minimap") or {}
    print("minimap offset=", mmcfg.get("offset"), "debug_upscale=", mmcfg.get("debug_window_upscale"))

    mp = imread_unicode(ROOT / "dist/assets/minimaps/yezhulingtu/map.png")
    mh, mw = mp.shape[:2]
    print(f"yezhulingtu map.png = {mw}x{mh}")
    print("minimap-to-map.png scale X=1.000 Y=1.000")

    from src.utils.common import get_minimap_loc_size, get_player_location_on_minimap

    player_color = tuple(mmcfg.get("player_color") or [0, 255, 255])
    shots = sorted(
        (ROOT / "dist/screenshot").glob("*_img_frame.png"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    rows = []
    for shot in shots[:8]:
        fr = imread_unicode(shot)
        if fr is None:
            continue
        fh, fw = fr.shape[:2]
        loc_size = get_minimap_loc_size(fr)
        print(f"\n{shot.name} frame={fw}x{fh} minimap_loc_size={loc_size}")
        if not loc_size:
            continue
        x, y, w, h = loc_size
        crop = fr[y : y + h, x : x + w]
        pl = get_player_location_on_minimap(crop, minimap_player_color=player_color)
        print(f"  player_on_minimap={pl} minimap={w}x{h}")
        # naive: if camera FOV roughly equals character-centered view,
        # cannot derive scale from one point. Record sizes for report.
        rows.append((fw, fh, w, h, pl))
        # Compare live minimap size vs full map.png
        print(f"  live/full W={w/mw:.3f} H={h/mh:.3f}")

    if rows:
        fw, fh, w, h, pl = rows[0]
        # These naive ratios assume 1 minimap px of FULL map equals screen/full_map * live
        # WRONG for FOV - only report as upper-bound if live minimap == full map
        if w == mw and h == mh:
            print(f"\nnaive screen/minimap if full map on screen: X={fw/mw:.3f} Y={fh/mh:.3f}")
        else:
            print(
                "\nlive minimap is a viewport, not full map.png; "
                "screen-per-minimap-pixel needs walk calibration."
            )
            print(f"sizes only: screen {fw}x{fh}, live minimap {w}x{h}, map.png {mw}x{mh}")


if __name__ == "__main__":
    main()
