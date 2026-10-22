# -*- coding: utf-8 -*-
"""
Lock first 怀旧 window, capture 30 frames over ~8s @0.25s.
Nametag: 日丁. Monsters: 野猪. Attack box: 140x160 (engine L/R + half_y).
Simulates soft sticky-track (TTL 0.5s) and flags weak SQDIFF (>0.25).
Writes overlays + summary.txt under _live_diag/combat_recheck/.
Run on Windows machineId 148c257b-8928-4713-9332-f127c4a90ae8 (not on box).
"""
from __future__ import annotations

from pathlib import Path
import time
import ctypes
import sys
import json
from ctypes import wintypes

import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "_live_diag" / "combat_recheck"
OUT.mkdir(parents=True, exist_ok=True)

# 剑客 current target range (after patch_sword_attack / user note)
RANGE_X = 140
RANGE_Y = 160
HALF_Y = RANGE_Y // 2  # engine get_attack_range uses range_y//2
TTL_SEC = 0.5
WEAK_SCORE = 0.25  # SQDIFF: higher = weaker match
DIFF_KEEP = 0.35
N_FRAMES = 30
INTERVAL = 0.25

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def list_huaijiu():
    out = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lparam):
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
                out.append((hwnd, title, r.left, r.top, r.right, r.bottom))
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
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", ctypes.c_uint32 * 3),
        ]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd_desk, hdc)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


class StickyTrack:
    """Minimal soft-track mirror of MonsterTracker TTL behaviour."""

    def __init__(self, ttl_sec=TTL_SEC, match_dist=80.0):
        self.ttl = ttl_sec
        self.match_dist = match_dist
        self._next_id = 1
        self._tracks = {}

    def update(self, detections, now):
        dets = list(detections or [])
        tids = list(self._tracks.keys())
        cands = []
        for di, det in enumerate(dets):
            dcx, dcy = det["cx"], det["cy"]
            for tid in tids:
                t = self._tracks[tid]
                dist = ((dcx - t["cx"]) ** 2 + (dcy - t["cy"]) ** 2) ** 0.5
                if dist <= self.match_dist:
                    cands.append((dist, di, tid))
        cands.sort(key=lambda x: x[0])
        used_d, used_t = set(), set()
        det_to = {}
        for _d, di, tid in cands:
            if di in used_d or tid in used_t:
                continue
            used_d.add(di)
            used_t.add(tid)
            det_to[di] = tid

        live, live_ids = [], set()
        for di, det in enumerate(dets):
            tid = det_to.get(di)
            if tid is None:
                tid = self._next_id
                self._next_id += 1
            self._tracks[tid] = {
                "id": tid,
                "cx": det["cx"],
                "cy": det["cy"],
                "loc": det["loc"],
                "size": det["size"],
                "score": det["score"],
                "name": det["name"],
                "last_seen": now,
                "miss": 0,
            }
            live_ids.add(tid)
            live.append({**det, "track_id": tid, "is_soft": False})

        soft = []
        expired = []
        for tid, tr in list(self._tracks.items()):
            if tid in live_ids:
                continue
            age = now - float(tr["last_seen"])
            tr["miss"] = int(tr.get("miss", 0)) + 1
            if age > self.ttl:
                expired.append(tid)
                continue
            soft.append(
                {
                    "name": tr["name"],
                    "loc": tr["loc"],
                    "size": tr["size"],
                    "score": tr["score"],
                    "cx": tr["cx"],
                    "cy": tr["cy"],
                    "track_id": tid,
                    "is_soft": True,
                    "age": round(age, 3),
                    "miss": tr["miss"],
                }
            )
        for tid in expired:
            self._tracks.pop(tid, None)
        return live, soft


def in_engine_box(px, py, cx, cy, side):
    """Engine directional box: left = [px-RANGE_X, px], right = [px, px+RANGE_X], y ± HALF_Y."""
    if abs(cy - py) > HALF_Y:
        return False
    if side == "L":
        return (px - RANGE_X) <= cx <= px
    return px <= cx <= (px + RANGE_X)


def main():
    wins = list_huaijiu()
    print("huaijiu windows:", [(t, l, tp, r, b) for _, t, l, tp, r, b in wins])
    if not wins:
        raise SystemExit("no 怀旧 window — lock failed")
    hwnd, title, left, top, right, bottom = wins[0]
    print(f"LOCKED first window: {title!r} hwnd={hwnd} rect=({left},{top},{right},{bottom})")

    frames = []
    t0 = time.time()
    for i in range(N_FRAMES):
        img = grab(left, top, right, bottom)
        p = OUT / f"f_{i:02d}.png"
        cv2.imencode(".png", img)[1].tofile(str(p))
        frames.append((p, img, time.time() - t0))
        time.sleep(INTERVAL)
    print(f"captured {len(frames)} frames in {time.time() - t0:.2f}s")

    from utils.nametag import (
        prepare_nametag_template,
        nametag_match_mask,
        find_nametag_match_candidates,
        pick_nametag_candidate,
    )
    from utils.monster_templates import load_monster_template

    tmpl = imread(ROOT / "assets" / "nametag" / "日丁.png")
    if tmpl is None:
        raise SystemExit("missing assets/nametag/日丁.png")
    track = prepare_nametag_template(tmpl, layers=1)
    mask_t = nametag_match_mask(track)
    scales_nt = ((0.95, 0.90), (0.95, 0.95), (1.0, 1.0))

    mob_dir = ROOT / "assets" / "monster" / "野猪"
    all_files = [
        f
        for f in sorted(mob_dir.glob("*"))
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")
    ]
    stands = [f for f in all_files if f.name.lower().startswith("stand")][:3]
    moves = [f for f in all_files if f.name.lower().startswith("move")][:3]
    # Prefer stand+move; do NOT require balanced opt — use what exists
    mob_files = stands + moves
    if not mob_files:
        mob_files = all_files[:4]
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
        gated = pick_nametag_candidate(
            cands, prefer_box=box, threshold=0.18, accept_thres=0.40, min_peak_sep=90
        )
        if gated is None:
            return None, None, None
        loc, score, size, _scale = gated
        player = (loc[0] + size[1] // 2, loc[1] - 24)
        return player, float(score), loc

    def detect_mobs(frame, player):
        if player is None or not templates:
            return [], 0.0
        px, py = player
        margin = 50
        x0 = max(0, px - RANGE_X - margin)
        y0 = max(0, py - RANGE_Y - margin)
        x1 = min(frame.shape[1], px + RANGE_X + margin)
        y1 = min(frame.shape[0], py + RANGE_Y + margin)
        crop = frame[y0:y1, x0:x1]
        hits = []
        t1 = time.perf_counter()
        for name, timg, tmask in templates:
            th, tw = timg.shape[:2]
            if crop.shape[0] < th or crop.shape[1] < tw:
                continue
            for img_use, mask_use in (
                (timg, tmask),
                (cv2.flip(timg, 1), cv2.flip(tmask, 1)),
            ):
                res = cv2.matchTemplate(
                    crop, img_use, cv2.TM_SQDIFF_NORMED, mask=mask_use
                )
                res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
                flat = res.reshape(-1)
                if flat.size == 0:
                    continue
                k = min(5, flat.size - 1)
                idxs = np.argpartition(flat, k)[: k + 1]
                for idx in idxs:
                    score = float(flat[idx])
                    if score >= DIFF_KEEP:
                        continue
                    yy, xx = np.unravel_index(int(idx), res.shape)
                    loc = (x0 + int(xx), y0 + int(yy))
                    hits.append(
                        {
                            "name": name,
                            "loc": loc,
                            "score": score,
                            "size": (tw, th),
                            "cx": loc[0] + tw // 2,
                            "cy": loc[1] + th // 2,
                        }
                    )
        ms = (time.perf_counter() - t1) * 1000
        hits.sort(key=lambda h: h["score"])
        kept = []
        for h in hits:
            if any(
                abs(h["cx"] - k["cx"]) < 40 and abs(h["cy"] - k["cy"]) < 40
                for k in kept
            ):
                continue
            kept.append(h)
            if len(kept) >= 8:
                break
        return kept, ms

    tracker = StickyTrack(ttl_sec=TTL_SEC)
    rows = []
    lines = []
    lines.append("=== combat_recheck capture ===")
    lines.append(f"window={title!r}")
    lines.append(f"range={RANGE_X}x{RANGE_Y} half_y={HALF_Y} ttl={TTL_SEC} weak>{WEAK_SCORE}")
    lines.append(f"templates={[t[0] for t in templates]}")
    lines.append("")

    for i, (_p, frame, trel) in enumerate(frames):
        now = time.time()
        player, nt_score, nt_loc = locate_player(frame)
        mobs, ms = detect_mobs(frame, player)
        live, soft = tracker.update(mobs, now)

        in_box = []
        weak_in_box = False
        if player:
            px, py = player
            for m in live:
                for side in ("L", "R"):
                    if in_engine_box(px, py, m["cx"], m["cy"], side):
                        in_box.append(
                            {
                                "side": side,
                                "name": m["name"],
                                "score": round(m["score"], 3),
                                "xy": (m["cx"], m["cy"]),
                                "soft": False,
                                "tid": m["track_id"],
                            }
                        )
                        if m["score"] > WEAK_SCORE:
                            weak_in_box = True
            for m in soft:
                for side in ("L", "R"):
                    if in_engine_box(px, py, m["cx"], m["cy"], side):
                        in_box.append(
                            {
                                "side": side,
                                "name": m["name"],
                                "score": round(m["score"], 3),
                                "xy": (m["cx"], m["cy"]),
                                "soft": True,
                                "tid": m["track_id"],
                                "age": m.get("age"),
                                "miss": m.get("miss"),
                            }
                        )

        soft_note = ""
        if soft:
            soft_note = "sticky=" + ",".join(
                f"#{s['track_id']}age={s['age']}miss={s['miss']}" for s in soft
            )
        elif live:
            soft_note = "live_only"
        else:
            soft_note = "no_track"

        # phantom risk: soft in box with no live
        phantom_risk = bool(soft) and not live
        # idle risk: player present, soft/live near but nothing in engine box
        near = live + soft
        idle_risk = bool(player) and bool(near) and not in_box

        row = {
            "i": i,
            "t": round(trel, 2),
            "player": player,
            "nt_score": None if nt_score is None else round(nt_score, 4),
            "nt_loc": nt_loc,
            "detect_ms": round(ms, 1),
            "mobs_live": [
                {
                    "name": m["name"],
                    "score": round(m["score"], 3),
                    "xy": (m["cx"], m["cy"]),
                    "tid": m["track_id"],
                }
                for m in live
            ],
            "mobs_soft": [
                {
                    "name": m["name"],
                    "score": round(m["score"], 3),
                    "xy": (m["cx"], m["cy"]),
                    "tid": m["track_id"],
                    "age": m.get("age"),
                    "miss": m.get("miss"),
                }
                for m in soft
            ],
            "in_box": in_box,
            "weak_in_box": weak_in_box,
            "sticky_note": soft_note,
            "phantom_risk": phantom_risk,
            "idle_risk": idle_risk,
        }
        rows.append(row)

        line = (
            f"f{i:02d} t={trel:.2f}s player={player} nt={row['nt_score']} "
            f"live={len(live)} soft={len(soft)} in_box={in_box} "
            f"weak={weak_in_box} {soft_note} "
            f"phantom_risk={phantom_risk} idle_risk={idle_risk} ms={ms:.0f}"
        )
        lines.append(line)
        print(line)

        vis = frame.copy()
        if player:
            px, py = player
            cv2.circle(vis, player, 6, (0, 255, 0), -1)
            # engine L/R boxes
            cv2.rectangle(
                vis,
                (px - RANGE_X, py - HALF_Y),
                (px, py + HALF_Y),
                (0, 0, 255),
                2,
            )
            cv2.rectangle(
                vis,
                (px, py - HALF_Y),
                (px + RANGE_X, py + HALF_Y),
                (255, 0, 0),
                2,
            )
            cv2.putText(
                vis,
                f"nt={row['nt_score']}",
                (px + 8, py - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
        for m in live:
            loc, (tw, th) = m["loc"], m["size"]
            col = (0, 255, 255)
            cv2.rectangle(vis, loc, (loc[0] + tw, loc[1] + th), col, 2)
            cv2.putText(
                vis,
                f"L{m['score']:.2f}#{m['track_id']}",
                (loc[0], loc[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                col,
                1,
            )
        for m in soft:
            loc, (tw, th) = m["loc"], m["size"]
            col = (0, 165, 255)  # orange soft
            cv2.rectangle(vis, loc, (loc[0] + tw, loc[1] + th), col, 2)
            cv2.putText(
                vis,
                f"S{m['score']:.2f}#{m['track_id']}a{m.get('age')}",
                (loc[0], loc[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                col,
                1,
            )
        cv2.putText(
            vis,
            soft_note[:60],
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )
        cv2.imencode(".png", vis)[1].tofile(str(OUT / f"viz_{i:02d}.png"))

    # summary
    lines.append("")
    lines.append("--- totals ---")
    lines.append(
        f"player_ok={sum(1 for r in rows if r['player'])}/{len(rows)}"
    )
    lines.append(
        f"frames_with_live_in_box="
        f"{sum(1 for r in rows if any(not x.get('soft') for x in r['in_box']))}/{len(rows)}"
    )
    lines.append(
        f"frames_with_soft_in_box="
        f"{sum(1 for r in rows if any(x.get('soft') for x in r['in_box']))}/{len(rows)}"
    )
    lines.append(
        f"weak_in_box_frames={sum(1 for r in rows if r['weak_in_box'])}/{len(rows)}"
    )
    lines.append(
        f"phantom_risk_frames={sum(1 for r in rows if r['phantom_risk'])}/{len(rows)}"
    )
    lines.append(
        f"idle_risk_frames={sum(1 for r in rows if r['idle_risk'])}/{len(rows)}"
    )
    lines.append(
        f"avg_detect_ms={np.mean([r['detect_ms'] for r in rows]):.1f}"
    )
    lines.append("")
    lines.append(
        "HINT: phantom_risk=soft TTL holds dead mob → swing; "
        "idle_risk=track near but outside L/R±half_y box → stand; "
        "walk-past=mob crosses box during turn_delay/cooldown."
    )

    summary_txt = "\n".join(lines) + "\n"
    (OUT / "summary.txt").write_text(summary_txt, encoding="utf-8")
    (OUT / "summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary_txt)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
