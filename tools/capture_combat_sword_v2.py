# -*- coding: utf-8 -*-
"""Post-opt 剑客 monitor: balanced stand/move, diff 0.28, sky filter y-90, 170x100."""
from __future__ import annotations
from pathlib import Path
import time, ctypes, sys, json
from ctypes import wintypes
import cv2
import numpy as np
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "_live_diag" / "combat_sword_v2"
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

# config peek
prof = yaml.safe_load((ROOT / "dist" / "config" / "config_professions.yaml").read_text(encoding="utf-8"))
print("selected", prof.get("selected_profession"))
md = prof["professions"]["剑客"]["overrides"]["monster_detect"]
print("sword md", md)

DIFF = float(md.get("diff_thres", 0.28))
MAX_ABOVE = float(md.get("max_above_player_y", 90))
RANGE_X, RANGE_Y = 170, 100  # attack box half-extents for monitor viz
# Engine uses range_y as full height (half each side). Monitor both.
ENG_HALF_Y = RANGE_Y // 2  # 50 — what get_attack_range actually uses

wins = list_game()
print("game", wins)
if not wins:
    raise SystemExit("no game window")
_, l, tp, r, b = wins[0]
frames = []
t0 = time.time()
for i in range(20):
    img = grab(l, tp, r, b)
    p = OUT / f"f_{i:02d}.png"
    cv2.imencode(".png", img)[1].tofile(str(p))
    frames.append((p, img, time.time() - t0))
    time.sleep(0.25)
print(f"captured {len(frames)} frames in {time.time()-t0:.2f}s")

from utils.nametag import (
    prepare_nametag_template, nametag_match_mask, find_nametag_match_candidates,
    pick_nametag_candidate,
)
from utils.monster_templates import load_monster_template

tmpl = imread(ROOT / "assets" / "nametag" / "日丁.png")
track = prepare_nametag_template(tmpl, layers=1)
mask_t = nametag_match_mask(track)
scales_nt = ((0.95, 0.90), (0.95, 0.95), (1.0, 1.0))

# balanced stand+move like engine
mob_dir = ROOT / "assets" / "monster" / "野猪"
all_files = [f for f in sorted(mob_dir.glob("*")) if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")]
stands = [f for f in all_files if f.name.lower().startswith("stand")][:3]
moves = [f for f in all_files if f.name.lower().startswith("move")][:3]
mob_files = stands + moves
templates = []
for f in mob_files:
    img, mask = load_monster_template(str(f), alpha_threshold=32)
    templates.append((f.name, img, mask))
    print("tmpl", f.name, img.shape)

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
        return [], 0.0, 0
    px, py = player
    margin = 50
    x0 = max(0, px - RANGE_X - margin)
    y0 = max(0, py - RANGE_Y - margin)
    x1 = min(frame.shape[1], px + RANGE_X + margin)
    y1 = min(frame.shape[0], py + RANGE_Y + margin)
    crop = frame[y0:y1, x0:x1]
    hits = []
    sky_rej = 0
    t1 = time.perf_counter()
    for name, timg, tmask in templates:
        th, tw = timg.shape[:2]
        if crop.shape[0] < th or crop.shape[1] < tw:
            continue
        for img_use, mask_use in ((timg, tmask), (cv2.flip(timg, 1), cv2.flip(tmask, 1))):
            res = cv2.matchTemplate(crop, img_use, cv2.TM_SQDIFF_NORMED, mask=mask_use)
            res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
            flat = res.reshape(-1)
            if flat.size == 0:
                continue
            idxs = np.argpartition(flat, min(5, flat.size - 1))[:5]
            for idx in idxs:
                score = float(flat[idx])
                if score >= DIFF:
                    continue
                yy, xx = np.unravel_index(int(idx), res.shape)
                loc = (x0 + int(xx), y0 + int(yy))
                cy = loc[1] + th // 2
                if cy < py - MAX_ABOVE:
                    sky_rej += 1
                    continue
                hits.append((name, loc, score, (th, tw)))
    ms = (time.perf_counter() - t1) * 1000
    hits.sort(key=lambda h: h[2])
    kept = []
    for h in hits:
        if any(abs(h[1][0] - k[1][0]) < 40 and abs(h[1][1] - k[1][1]) < 40 for k in kept):
            continue
        kept.append(h)
        if len(kept) >= 8:
            break
    return kept, ms, sky_rej

rows = []
sky_total = 0
for i, (p, frame, trel) in enumerate(frames):
    player, nt_score, nt_loc = locate_player(frame)
    mobs, ms, sky_rej = detect_mobs(frame, player)
    sky_total += sky_rej
    in170 = []
    in_eng = []  # engine attack box: ±range_x horizontal one side, ± range_y/2 vertical
    if player:
        px, py = player
        for name, loc, score, (th, tw) in mobs:
            cx, cy = loc[0] + tw // 2, loc[1] + th // 2
            if abs(cx - px) <= RANGE_X and abs(cy - py) <= RANGE_Y:
                in170.append({"side": "L" if cx < px else "R", "name": name, "score": round(score, 3), "c": [cx, cy]})
            if abs(cx - px) <= RANGE_X and abs(cy - py) <= ENG_HALF_Y:
                in_eng.append({"side": "L" if cx < px else "R", "name": name, "score": round(score, 3), "c": [cx, cy]})
    rows.append({
        "i": i, "t": round(trel, 2),
        "player": list(player) if player else None,
        "nt": None if nt_score is None else round(nt_score, 4),
        "detect_ms": round(ms, 1),
        "mobs": len(mobs),
        "sky_rej": sky_rej,
        "in170": in170,
        "in_eng_half_y": in_eng,
        "best": None if not mobs else {"name": mobs[0][0], "score": round(mobs[0][2], 3), "loc": list(mobs[0][1])},
    })
    vis = frame.copy()
    if player:
        cv2.circle(vis, player, 6, (0, 255, 0), -1)
        cv2.rectangle(vis, (player[0]-RANGE_X, player[1]-RANGE_Y),
                      (player[0]+RANGE_X, player[1]+RANGE_Y), (0, 0, 255), 2)
        cv2.rectangle(vis, (player[0]-RANGE_X, player[1]-ENG_HALF_Y),
                      (player[0]+RANGE_X, player[1]+ENG_HALF_Y), (255, 128, 0), 2)
        cv2.line(vis, (0, player[1]-int(MAX_ABOVE)), (vis.shape[1], player[1]-int(MAX_ABOVE)), (255, 0, 255), 1)
    for name, loc, score, (th, tw) in mobs[:6]:
        cv2.rectangle(vis, loc, (loc[0]+tw, loc[1]+th), (0, 255, 255), 2)
        cv2.putText(vis, f"{score:.2f}", (loc[0], loc[1]-4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.imencode(".png", vis)[1].tofile(str(OUT / f"viz_{i:02d}.png"))
    print(f"f{i:02d}", rows[-1])

agg = {
    "n_frames": len(rows),
    "player_ok": sum(1 for r in rows if r["player"]),
    "player_ok_rate": round(sum(1 for r in rows if r["player"]) / len(rows), 3),
    "player_y_span": (max(r["player"][1] for r in rows if r["player"]) - min(r["player"][1] for r in rows if r["player"])) if any(r["player"] for r in rows) else None,
    "avg_detect_ms": round(float(np.mean([r["detect_ms"] for r in rows])), 1),
    "in170_frames": sum(1 for r in rows if r["in170"]),
    "in_eng_frames": sum(1 for r in rows if r["in_eng_half_y"]),
    "sky_rej_total": sky_total,
    "best_scores": [r["best"]["score"] for r in rows if r["best"]],
    "templates": [f.name for f in mob_files],
    "diff_thres": DIFF,
    "max_above": MAX_ABOVE,
    "selected": prof.get("selected_profession"),
}
print("=== AGG ===")
print(json.dumps(agg, ensure_ascii=False, indent=2))
(OUT / "summary.json").write_text(json.dumps({"agg": agg, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", OUT)
