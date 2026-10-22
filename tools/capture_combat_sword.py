# -*- coding: utf-8 -*-
"""Sword (剑客) live combat monitor: 20 frames, 170x100 vs 130x80 attack boxes."""
from __future__ import annotations
from pathlib import Path
import time, ctypes, sys, json
from ctypes import wintypes
import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "_live_diag" / "combat_sword"
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

wins = list_game()
print("game", wins)
if not wins:
    raise SystemExit("no game window containing 怀旧")
_, l, tp, r, b = wins[0]
frames = []
t0 = time.time()
N_FRAMES = 20
INTERVAL = 0.25
for i in range(N_FRAMES):
    img = grab(l, tp, r, b)
    p = OUT / f"f_{i:02d}.png"
    cv2.imencode(".png", img)[1].tofile(str(p))
    frames.append((p, img, time.time() - t0))
    time.sleep(INTERVAL)
print(f"captured {len(frames)} frames in {time.time()-t0:.2f}s")

from utils.nametag import (
    prepare_nametag_template, nametag_match_mask, find_nametag_match_candidates,
    pick_nametag_candidate,
)
from utils.monster_templates import load_monster_template

tmpl = imread(ROOT / "assets" / "nametag" / "日丁.png")
if tmpl is None:
    raise SystemExit("missing nametag assets/nametag/日丁.png")
track = prepare_nametag_template(tmpl, layers=1)
mask_t = nametag_match_mask(track)
scales_nt = ((0.95, 0.90), (0.95, 0.95), (1.0, 1.0))

mob_dir = ROOT / "assets" / "monster" / "野猪"
mob_files = sorted(mob_dir.glob("*")) if mob_dir.exists() else []
mob_files = [f for f in mob_files if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")]
# stand + move prefixes, up to 6
pref = ("stand", "move")
mob_files = [f for f in mob_files if f.name.lower().startswith(pref)]
mob_files = sorted(
    mob_files,
    key=lambda p: (0 if p.name.lower().startswith("stand") else 1, p.name),
)[:6]
templates = []
for f in mob_files:
    try:
        img, mask = load_monster_template(str(f), alpha_threshold=32)
        templates.append((f.name, img, mask))
        print("mob tmpl", f.name, img.shape)
    except Exception as e:
        print("skip", f, e)
print(f"loaded {len(templates)} stand+move templates")

RANGE_NEW = (170, 100)
RANGE_OLD = (130, 80)
margin = 50
SEARCH_RX, SEARCH_RY = RANGE_NEW

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
    if player is None or not templates:
        return [], 0.0
    px, py = player
    x0 = max(0, px - SEARCH_RX - margin)
    y0 = max(0, py - SEARCH_RY - margin)
    x1 = min(frame.shape[1], px + SEARCH_RX + margin)
    y1 = min(frame.shape[0], py + SEARCH_RY + margin)
    crop = frame[y0:y1, x0:x1]
    hits = []
    t1 = time.perf_counter()
    for name, timg, tmask in templates:
        th, tw = timg.shape[:2]
        if crop.shape[0] < th or crop.shape[1] < tw:
            continue
        for img_use, mask_use, flip in ((timg, tmask, False), (cv2.flip(timg, 1), cv2.flip(tmask, 1), True)):
            res = cv2.matchTemplate(crop, img_use, cv2.TM_SQDIFF_NORMED, mask=mask_use)
            res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
            flat = res.reshape(-1)
            if flat.size == 0:
                continue
            idxs = np.argpartition(flat, min(5, flat.size - 1))[:5]
            for idx in idxs:
                score = float(flat[idx])
                if score >= 0.35:
                    continue
                yy, xx = np.unravel_index(int(idx), res.shape)
                hits.append((name, (x0 + int(xx), y0 + int(yy)), score, (th, tw), flip))
    ms = (time.perf_counter() - t1) * 1000
    hits.sort(key=lambda h: h[2])
    kept = []
    for h in hits:
        if any(abs(h[1][0] - k[1][0]) < 40 and abs(h[1][1] - k[1][1]) < 40 for k in kept):
            continue
        kept.append(h)
        if len(kept) >= 8:
            break
    return kept, ms

def in_box(player, loc, th, tw, rx, ry):
    px, py = player
    cx, cy = loc[0] + tw // 2, loc[1] + th // 2
    return abs(cx - px) <= rx and abs(cy - py) <= ry, (cx, cy)

rows = []
for i, (p, frame, trel) in enumerate(frames):
    player, nt_score, nt_loc = locate_player(frame)
    mobs, ms = detect_mobs(frame, player)
    in_atk_170 = []
    in_atk_130 = []
    if player:
        for name, loc, score, (th, tw), flip in mobs:
            ok170, cxy = in_box(player, loc, th, tw, *RANGE_NEW)
            ok130, _ = in_box(player, loc, th, tw, *RANGE_OLD)
            side = "L" if cxy[0] < player[0] else "R"
            entry = (side, name, round(score, 3), cxy)
            if ok170:
                in_atk_170.append(entry)
            if ok130:
                in_atk_130.append(entry)
    rows.append({
        "i": i, "t": round(trel, 2),
        "player": list(player) if player else None,
        "nt": None if nt_score is None else round(nt_score, 4),
        "detect_ms": round(ms, 1),
        "mobs": len(mobs),
        "in_atk_170": in_atk_170,
        "in_atk_130": in_atk_130,
        "best": None if not mobs else {
            "name": mobs[0][0], "score": round(mobs[0][2], 3), "loc": list(mobs[0][1])
        },
    })
    print(
        f"f{i:02d} player={player} nt={None if nt_score is None else round(nt_score,4)} "
        f"detect_ms={ms:.1f} mobs={len(mobs)} in170={len(in_atk_170)} in130={len(in_atk_130)} "
        f"best={rows[-1]['best']}"
    )
    vis = frame.copy()
    if player:
        cv2.circle(vis, player, 6, (0, 255, 0), -1)
        cv2.rectangle(
            vis,
            (player[0] - RANGE_NEW[0], player[1] - RANGE_NEW[1]),
            (player[0] + RANGE_NEW[0], player[1] + RANGE_NEW[1]),
            (0, 0, 255), 2,
        )
        cv2.rectangle(
            vis,
            (player[0] - RANGE_OLD[0], player[1] - RANGE_OLD[1]),
            (player[0] + RANGE_OLD[0], player[1] + RANGE_OLD[1]),
            (255, 128, 0), 1,
        )
        cv2.putText(vis, "170x100", (player[0] - RANGE_NEW[0], player[1] - RANGE_NEW[1] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
        cv2.putText(vis, "130x80", (player[0] - RANGE_OLD[0], player[1] - RANGE_OLD[1] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 128, 0), 1)
    for name, loc, score, (th, tw), flip in mobs[:6]:
        ok170, _ = (False, None)
        if player:
            ok170, _ = in_box(player, loc, th, tw, *RANGE_NEW)
        col = (0, 255, 255) if ok170 else (255, 200, 0)
        cv2.rectangle(vis, loc, (loc[0] + tw, loc[1] + th), col, 2)
        cv2.putText(vis, f"{score:.2f}", (loc[0], max(12, loc[1] - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    cv2.imencode(".png", vis)[1].tofile(str(OUT / f"viz_{i:02d}.png"))

player_ok = sum(1 for r in rows if r["player"])
ys = [r["player"][1] for r in rows if r["player"]]
y_span = (max(ys) - min(ys)) if ys else None
avg_ms = float(np.mean([r["detect_ms"] for r in rows])) if rows else 0.0
cov170 = sum(1 for r in rows if r["in_atk_170"])
cov130 = sum(1 for r in rows if r["in_atk_130"])
scores = [r["best"]["score"] for r in rows if r.get("best")]
agg = {
    "n_frames": len(rows),
    "player_ok": player_ok,
    "player_ok_rate": round(player_ok / max(1, len(rows)), 3),
    "player_y_span": y_span,
    "avg_detect_ms": round(avg_ms, 2),
    "in_atk_170_frames": cov170,
    "in_atk_130_frames": cov130,
    "in_atk_170_rate": round(cov170 / max(1, len(rows)), 3),
    "in_atk_130_rate": round(cov130 / max(1, len(rows)), 3),
    "best_score_avg": None if not scores else round(float(np.mean(scores)), 4),
    "best_score_min": None if not scores else round(float(np.min(scores)), 4),
    "best_score_max": None if not scores else round(float(np.max(scores)), 4),
    "templates": [t[0] for t in templates],
    "range_new": list(RANGE_NEW),
    "range_old": list(RANGE_OLD),
    "window": wins[0][0] if wins else None,
}

print("=== COMBAT SWORD AGGREGATE ===")
print(json.dumps(agg, ensure_ascii=False, indent=2))
summary = {"aggregate": agg, "frames": rows}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", OUT / "summary.json")
