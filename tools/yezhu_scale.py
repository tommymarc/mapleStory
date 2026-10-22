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
    print("bot:", cfg.get("bot"))
    print("character:", cfg.get("character"))
    for k in cfg:
        if "map" in k.lower():
            print(f"cfg.{k}=", cfg[k])

    import src.utils.common as common

    names = [a for a in dir(common) if "minimap" in a.lower()]
    print("minimap helpers:", names)

    mp = imread_unicode(ROOT / "dist/assets/minimaps/yezhulingtu/map.png")
    print("yezhulingtu map.png shape (H,W,C):", None if mp is None else mp.shape)
    if mp is not None:
        h, w = mp.shape[:2]
        print(f"map.png WxH = {w}x{h}")
        print("minimap↔map.png scale (bot): 1.000 x 1.000")

    shots = sorted((ROOT / "dist/screenshot").glob("*_img_frame.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    # locate minimap on newest few frames
    locate = None
    for name in names:
        fn = getattr(common, name)
        if callable(fn):
            print("try", name)

    # Prefer known APIs from prior diagnosis
    for cand in [
        "get_minimap_location",
        "locate_minimap",
        "find_minimap",
        "get_minimap_frame",
        "detect_minimap",
    ]:
        if hasattr(common, cand):
            locate = getattr(common, cand)
            print("using", cand)
            break

    # Fallback: inspect source for def
    src = (ROOT / "src/utils/common.py").read_text(encoding="utf-8", errors="ignore")
    import re

    for m in re.finditer(r"^def (\w*minimap\w*)\(", src, re.M):
        print("def", m.group(1))

    # Analyze top screenshots: yellow player + estimated minimap rect
    for shot in shots[:5]:
        fr = imread_unicode(shot)
        if fr is None:
            print("fail read", shot.name)
            continue
        fh, fw = fr.shape[:2]
        print("\n===", shot.name, f"frame={fw}x{fh} ===")
        # match full map.png into top-left region
        if mp is not None and fh > mp.shape[0] and fw > mp.shape[1]:
            roi = fr[: min(fh, mp.shape[0] + 120), : min(fw, mp.shape[1] + 80)]
            if roi.shape[0] >= mp.shape[0] and roi.shape[1] >= mp.shape[1]:
                res = cv2.matchTemplate(roi, mp, cv2.TM_SQDIFF_NORMED)
                minv, _, minl, _ = cv2.minMaxLoc(res)
                print(f"full map.png in TL ROI SQDIFF={minv:.3f} at {minl}")

        # Yellow player dots BGR ~ (0,255,255)
        b, g, r = cv2.split(fr)
        yellow = ((b > 200) & (g > 200) & (r < 90)).astype(np.uint8) * 255
        ys, xs = np.where(yellow[:280, :360] > 0)
        if len(xs):
            print(
                f"yellow TL n={len(xs)} bbox=({xs.min()},{ys.min()})-({xs.max()},{ys.max()}) "
                f"cent=({xs.mean():.1f},{ys.mean():.1f})"
            )
        else:
            print("no yellow in TL")

    print(
        "\nNOTE: screen↔minimap pixel scale is NOT stored for yezhulingtu; "
        "need paired walk calibration (Δscreen / Δminimap)."
    )


if __name__ == "__main__":
    main()
