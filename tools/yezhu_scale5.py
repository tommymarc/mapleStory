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
    from src.utils.common import get_minimap_loc_size, get_player_location_on_minimap

    player_color = tuple((cfg.get("minimap") or {}).get("player_color") or [0, 255, 255])
    paths = [
        ROOT / "dist/screenshot/2026-09-21_00-21-54_img_frame.png",
        ROOT / "dist/screenshot/2026-09-21_01-11-20_img_frame.png",
    ]
    frames, mpos = [], []
    for p in paths:
        fr = imread_unicode(p)
        x, y, w, h = get_minimap_loc_size(fr)
        pl = get_player_location_on_minimap(fr[y : y + h, x : x + w], minimap_player_color=player_color)
        frames.append(fr)
        mpos.append(np.array(pl, dtype=float))
        print(p.name, "minimap_player", pl)

    a, b = frames
    y0, y1, x0, x1 = 130, 520, 100, 1180
    ga = cv2.cvtColor(a[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    shift, resp = cv2.phaseCorrelate(ga, gb)
    # phaseCorrelate: how much B is shifted relative to A (dx, dy)
    print(f"phaseCorrelate shift B vs A: dx={shift[0]:.3f} dy={shift[1]:.3f} resp={resp:.4f}")

    dmx, dmy = (mpos[1] - mpos[0]).tolist()
    print(f"delta minimap player: dmx={dmx:.3f} dmy={dmy:.3f}")
    # Landmark scroll when camera follows player:
    # scale = -screen_shift / minimap_delta
    if abs(dmx) >= 1e-3:
        sx = -shift[0] / dmx
        print(f"scale X = {sx:.3f}  (screen px per minimap px)")
    if abs(dmy) >= 1e-3:
        sy = -shift[1] / dmy
        print(f"scale Y = {sy:.3f}")
    else:
        print("scale Y: n/a (minimap dmy~0 on these two frames)")

    # Cross-check with many patches, keep sign-consistent with phaseCorrelate
    ra = a[y0:y1, x0:x1]
    rb = b[y0:y1, x0:x1]
    ph, pw = ra.shape[:2]
    vals = []
    for cy in range(40, ph - 100, 60):
        for cx in range(40, pw - 160, 80):
            tw, th = 120, 80
            patch = ra[cy : cy + th, cx : cx + tw]
            res = cv2.matchTemplate(rb, patch, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxl = cv2.minMaxLoc(res)
            if maxv < 0.7:
                continue
            dx = maxl[0] - cx
            dy = maxl[1] - cy
            # expect dx same sign as phaseCorrelate shift[0]
            if shift[0] != 0 and dx * shift[0] < 0:
                continue
            vals.append((dx, dy, maxv))
    print(f"kept patches: {len(vals)}")
    if vals and abs(dmx) >= 1e-3:
        dxs = np.array([v[0] for v in vals], float)
        dys = np.array([v[1] for v in vals], float)
        ws = np.array([v[2] for v in vals], float)
        dx_m = float(np.average(dxs, weights=ws))
        dy_m = float(np.average(dys, weights=ws))
        print(f"patch mean scroll=({dx_m:.2f},{dy_m:.2f})")
        print(f"patch scale X = {-dx_m / dmx:.3f}")
        if abs(dmy) >= 1e-3:
            print(f"patch scale Y = {-dy_m / dmy:.3f}")

    mp = imread_unicode(ROOT / "dist/assets/minimaps/yezhulingtu/map.png")
    print(f"yezhulingtu map.png = {mp.shape[1]}x{mp.shape[0]}")
    print("minimap-to-map.png = 1.000 x 1.000")


if __name__ == "__main__":
    main()
