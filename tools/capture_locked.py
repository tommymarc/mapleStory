# -*- coding: utf-8 -*-
"""Capture game frames + run monster detect near player; report latency factors."""
from __future__ import annotations
from pathlib import Path
import time, ctypes, sys, json
from ctypes import wintypes
import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "_live_diag" / "combat_locked"
OUT.mkdir(parents=True, exist_ok=True)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

def list_game():
    out = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value or ""
        if "怀旧" in title:
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 200:
                out.append((title, r.left, r.top, r.right, r.bottom))
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out

def grab(left, top, right, bottom):
    w, h = right - left, bottom - top
    hwnd_desk = user32.GetDesktopWindow()
    hdc = user32.GetWindowDC(hwnd_desk)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, left, top, 0x00CC0020)
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]
    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem); user32.ReleaseDC(hwnd_desk, hdc)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)

# --- capture ---
wins = list_game()
print("game", wins)
if not wins:
    raise SystemExit("no game window")
_, l, tp, r, b = wins[0]
frames = []
t0 = time.time()
for i in range(30):
    img = grab(l, tp, r, b)
    p = OUT / f"f_{i:02d}.png"
    cv2.imencode(".png", img)[1].tofile(str(p))
    frames.append((p, img, time.time() - t0))
    time.sleep(0.25)
print(f"captured {len(frames)} frames in {time.time()-t0:.2f}s")

# --- nametag + monster detect using project utils ---
from utils.nametag import (
    prepare_nametag_template, nametag_match_mask, find_nametag_match_candidates,
    pick_nametag_candidate, find_best_nametag_match, plate_support,
)
from utils.monster_templates import load_monster_template
from utils.common import find_pattern_sqdiff, nms

tmpl = imread(ROOT / "assets" / "nametag" / "日丁.png")
track = prepare_nametag_template(tmpl, layers=1)
mask_t = nametag_match_mask(track)
scales_nt = ((0.95, 0.90), (0.95, 0.95), (1.0, 1.0))

# load 野猪 templates
mob_dir = ROOT / "assets" / "monster" / "野猪"
mob_files = sorted(mob_dir.glob("*")) if mob_dir.exists() else []
mob_files = [f for f in mob_files if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")]
# prefer stand
mob_files = sorted(mob_files, key=lambda p: (0 if p.name.lower().startswith("stand") else 1, p.name))[:4]
templates = []
for f in mob_files:
    try:
        img, mask = load_monster_template(str(f), alpha_threshold=32)
        templates.append((f.name, img, mask))
        print("mob tmpl", f.name, img.shape)
    except Exception as e:
        print("skip", f, e)

# also check other mapped monsters folders
for other in ["铁野猪", "野猪"]:
    pass

range_x, range_y = 130, 80
margin = 50
diff_thres = 0.8  # for contour/color notes; template matching often uses this inverted - check engine
# In this codebase SQDIFF: lower better. monster_detect.diff_thres 0.8 means score < 0.8

def locate_player(frame):
    h, w = frame.shape[:2]
    roi = frame[: int(h * 0.85)]
    box = (140, 100, roi.shape[1], roi.shape[0])
    cands = find_nametag_match_candidates(
        roi, track, mask_t, scales_nt, box, require_plate=True, top_k=6, max_keep=4
    )
    gated = pick_nametag_candidate(cands, prefer_box=box, threshold=0.18, accept_thres=0.40, min_peak_sep=90)
    if gated is None:
        return None, None, None
    loc, score, size, scale = gated
    player = (loc[0] + size[1] // 2, loc[1] - 24)
    return player, float(score), loc

def detect_mobs(frame, player):
    """Template match near player; return list of (name, loc, score, wh) and ms cost."""
    if player is None or not templates:
        return [], 0.0
    px, py = player
    x0 = max(0, px - range_x - margin)
    y0 = max(0, py - range_y - margin)
    x1 = min(frame.shape[1], px + range_x + margin)
    y1 = min(frame.shape[0], py + range_y + margin)
    crop = frame[y0:y1, x0:x1]
    hits = []
    t1 = time.perf_counter()
    for name, timg, tmask in templates:
        th, tw = timg.shape[:2]
        if crop.shape[0] < th or crop.shape[1] < tw:
            continue
        # try both sides / raw
        for img_use, mask_use, flip in ((timg, tmask, False), (cv2.flip(timg, 1), cv2.flip(tmask, 1), True)):
            res = cv2.matchTemplate(crop, img_use, cv2.TM_SQDIFF_NORMED, mask=mask_use)
            res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
            # top few
            flat = res.reshape(-1)
            if flat.size == 0:
                continue
            idxs = np.argpartition(flat, min(5, flat.size - 1))[:5]
            for idx in idxs:
                score = float(flat[idx])
                if score >= 0.35:  # keep relatively good candidates for report
                    continue
                yy, xx = np.unravel_index(int(idx), res.shape)
                hits.append((name, (x0 + int(xx), y0 + int(yy)), score, (th, tw), flip))
    ms = (time.perf_counter() - t1) * 1000
    # nms-ish by location
    hits.sort(key=lambda h: h[2])
    kept = []
    for h in hits:
        if any(abs(h[1][0] - k[1][0]) < 40 and abs(h[1][1] - k[1][1]) < 40 for k in kept):
            continue
        kept.append(h)
        if len(kept) >= 8:
            break
    return kept, ms

rows = []
for i, (p, frame, trel) in enumerate(frames):
    player, nt_score, nt_loc = locate_player(frame)
    mobs, ms = detect_mobs(frame, player)
    in_atk = []
    if player:
        px, py = player
        for name, loc, score, (th, tw), flip in mobs:
            cx, cy = loc[0] + tw // 2, loc[1] + th // 2
            if abs(cx - px) <= range_x and abs(cy - py) <= range_y:
                side = "L" if cx < px else "R"
                in_atk.append((side, name, round(score, 3), (cx, cy)))
    h, w = frame.shape[:2]
    chat_zone = False
    if nt_loc is not None:
        chat_zone = nt_loc[0] > int(w * 0.7) and nt_loc[1] > int(h * 0.55)
    weak_in = [x for x in in_atk if x[2] >= 0.25]
    strong_in = [x for x in in_atk if x[2] < 0.20]
    rows.append({
        "i": i, "t": round(trel, 2),
        "player": player, "nt": None if nt_score is None else round(nt_score, 4),
        "nt_loc": nt_loc, "chat_zone": chat_zone,
        "detect_ms": round(ms, 1),
        "mobs": len(mobs),
        "in_atk": in_atk,
        "strong_in": len(strong_in), "weak_in": len(weak_in),
        "best": None if not mobs else (mobs[0][0], round(mobs[0][2], 3), mobs[0][1]),
    })
    # draw
    vis = frame.copy()
    if player:
        cv2.circle(vis, player, 6, (0, 255, 0), -1)
        cv2.rectangle(vis, (player[0]-range_x, player[1]-range_y),
                      (player[0]+range_x, player[1]+range_y), (0, 0, 255), 2)
    for name, loc, score, (th, tw), flip in mobs[:6]:
        col = (0, 255, 255) if any(abs(loc[0]+tw//2-player[0])<=range_x and abs(loc[1]+th//2-player[1])<=range_y for player in ([player] if player else [])) else (255, 200, 0)
        cv2.rectangle(vis, loc, (loc[0]+tw, loc[1]+th), col, 2)
        cv2.putText(vis, f"{score:.2f}", (loc[0], loc[1]-4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    cv2.imencode(".png", vis)[1].tofile(str(OUT / f"viz_{i:02d}.png"))

print("=== COMBAT MONITOR ===")
for r in rows:
    print(r)

atk_frames = sum(1 for r in rows if r["in_atk"])
strong_frames = sum(1 for r in rows if r.get("strong_in"))
empty_with_player = sum(1 for r in rows if r["player"] and not r["in_atk"])
print(f"frames_with_mob_in_attack_box={atk_frames}/{len(rows)}")
print(f"frames_with_STRONG_mob_in_box(score<0.20)={strong_frames}/{len(rows)}")
print(f"player_ok_but_empty_box={empty_with_player}/{len(rows)}")
print(f"chat_zone_locks={sum(1 for r in rows if r.get('chat_zone'))}/{len(rows)}")
print(f"avg_detect_ms={np.mean([r['detect_ms'] for r in rows]):.1f}")
print(f"player_ok={sum(1 for r in rows if r['player'])}/{len(rows)}")

# estimate command pipeline delay given config
print("PIPELINE_HINT turn_delay=0.06 cooldown=0.4 detect_every_n=2(default) attack=directional")
(OUT / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", OUT)
