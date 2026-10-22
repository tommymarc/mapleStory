# -*- coding: utf-8 -*-
"""Diagnose why mobs scored empty: show best raw SQDIFF near player with looser gate."""
from pathlib import Path
import sys, cv2, numpy as np
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT / "src"))
from utils.monster_templates import load_monster_template
from utils.nametag import prepare_nametag_template, nametag_match_mask, find_nametag_match_candidates, pick_nametag_candidate

frame = cv2.imdecode(np.fromfile(str(ROOT / "_live_diag/combat_sword_v2/f_00.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
tmpl = cv2.imdecode(np.fromfile(str(ROOT / "assets/nametag/日丁.png"), dtype=np.uint8), cv2.IMREAD_COLOR)
track = prepare_nametag_template(tmpl, layers=1)
mask_t = nametag_match_mask(track)
h, w = frame.shape[:2]
roi = frame[: int(h * 0.85)]
box = (140, 100, roi.shape[1], roi.shape[0])
cands = find_nametag_match_candidates(roi, track, mask_t, ((0.95,0.90),(0.95,0.95),(1.0,1.0)), box, require_plate=True, top_k=6, max_keep=4)
gated = pick_nametag_candidate(cands, prefer_box=box, threshold=0.18, accept_thres=0.40, min_peak_sep=90)
print("player gated", gated)
if not gated:
    raise SystemExit(0)
loc, score, size, scale = gated
player = (loc[0] + size[1]//2, loc[1]-24)
print("player", player, "nt", score)

# load all stand/move/and also check other monster folders present
mon_root = ROOT / "assets/monster"
print("monster folders", [p.name for p in mon_root.iterdir() if p.is_dir()][:30])

px, py = player
RANGE_X, RANGE_Y, margin = 220, 160, 80
x0,y0 = max(0,px-RANGE_X-margin), max(0,py-RANGE_Y-margin)
x1,y1 = min(w,px+RANGE_X+margin), min(h,py+RANGE_Y+margin)
crop = frame[y0:y1, x0:x1]
print("search crop", crop.shape, "box", x0,y0,x1,y1)

def best_for(folder_name, prefixes=("stand","move"), limit=6):
    d = mon_root / folder_name
    if not d.exists():
        return []
    files = [f for f in d.iterdir() if f.suffix.lower() in (".png",".jpg",".jpeg",".bmp")]
    files = [f for f in files if any(f.name.lower().startswith(p) for p in prefixes)]
    stands = sorted([f for f in files if f.name.lower().startswith("stand")])[:3]
    moves = sorted([f for f in files if f.name.lower().startswith("move")])[:3]
    files = stands + moves
    out = []
    for f in files:
        img, mask = load_monster_template(str(f), alpha_threshold=32)
        th, tw = img.shape[:2]
        if crop.shape[0] < th or crop.shape[1] < tw:
            continue
        for flip in (False, True):
            iu = cv2.flip(img,1) if flip else img
            mu = cv2.flip(mask,1) if flip else mask
            res = cv2.matchTemplate(crop, iu, cv2.TM_SQDIFF_NORMED, mask=mu)
            res = np.nan_to_num(res, nan=1.0)
            mn = float(res.min())
            yy, xx = np.unravel_index(int(res.argmin()), res.shape)
            out.append((mn, f.name, flip, (x0+xx, y0+yy)))
    out.sort(key=lambda t: t[0])
    return out[:8]

for name in ["野猪", "铁野猪", "黑木妖", "木妖", "斧木妖"]:
    hits = best_for(name)
    if hits:
        print(name, "top:", [(round(s,3), n, fl, loc) for s,n,fl,loc in hits[:5]])
    else:
        print(name, "no templates or no folder")
