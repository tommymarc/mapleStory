# -*- coding: utf-8 -*-
"""Analyze burst_long frames with P0/P1 simulation; write summary + overlay."""
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
sys.path.insert(0, str(ROOT / "src"))
from utils.nametag import (
    prepare_nametag_template, nametag_match_mask, find_nametag_match_candidates,
    pick_nametag_candidate, find_best_nametag_match, plate_support,
)

def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)

BURST = ROOT / "_live_diag" / "burst_long"
OUT = ROOT / "_live_diag" / "burst_long_report"
OUT.mkdir(parents=True, exist_ok=True)

tmpl = imread(ROOT / "assets" / "nametag" / "日丁.png")
track = prepare_nametag_template(tmpl, layers=1)
verify = prepare_nametag_template(tmpl, layers=3)
mask_t = nametag_match_mask(track)
mask_v = nametag_match_mask(verify)
scales = ((0.95, 0.90), (0.95, 0.95), (1.0, 1.0))
search_top, search_left = 100, 140
threshold = 0.18
hold_good_score_max = 0.12
hold_good_frames = 12
max_jump_y = 30
jump_reject_score = 0.15
verify_require = 0.18

hold_remaining = 0
hold_loc = None
results = []
frames = sorted(BURST.glob("g_*.png"))

for i, fp in enumerate(frames):
    frame = imread(fp)
    h, w = frame.shape[:2]
    roi = frame[: int(h * 0.85)]
    box = (search_left, search_top, roi.shape[1], roi.shape[0])
    cands = find_nametag_match_candidates(
        roi, track, mask_t, scales, box, require_plate=True, top_k=8, max_keep=6
    )
    gated = pick_nametag_candidate(
        cands, prefer_box=box, threshold=0.18, accept_thres=0.40, min_peak_sep=90
    )
    decision = "none"
    final_loc = None
    track_score = None
    verify_score = None
    raw_loc = None

    if gated is None:
        if hold_remaining > 0 and hold_loc is not None:
            hold_remaining -= 1
            decision = f"hold(no_match,{hold_remaining})"
            final_loc = hold_loc
        else:
            decision = "lost"
    else:
        loc, score, size, scale = gated
        raw_loc, track_score = loc, float(score)
        accept = score < threshold
        if not accept:
            roi_m = roi[loc[1] : loc[1] + size[0], loc[0] : loc[0] + size[1]]
            accept = score < 0.40 and plate_support(roi_m) >= 0.22
        if not accept:
            if hold_remaining > 0 and hold_loc is not None:
                hold_remaining -= 1
                decision = f"hold(score,{hold_remaining})"
                final_loc = hold_loc
            else:
                decision = "reject_score"
        else:
            jumped = False
            if hold_loc is not None:
                dy = abs(loc[1] - hold_loc[1])
                if dy > max_jump_y and score > jump_reject_score:
                    jumped = True
                    if hold_remaining > 0:
                        hold_remaining -= 1
                        decision = f"hold(yjump{dy},{hold_remaining})"
                        final_loc = hold_loc
                    else:
                        decision = f"reject_yjump{dy}"
            if not jumped:
                sx, sy = scale
                vh, vw = verify.shape[:2]
                vbox = (
                    max(0, loc[0] - 12),
                    max(0, loc[1] - 12),
                    min(roi.shape[1], loc[0] + int(vw * sx) + 12),
                    min(roi.shape[0], loc[1] + int(vh * sy) + 12),
                )
                vhit = find_best_nametag_match(
                    roi, verify, mask_v, (scale, (1, 1), (0.95, 0.95)), vbox, require_plate=True
                )
                if vhit is None:
                    ok, verify_score = False, 1.0
                else:
                    verify_score = float(vhit[1])
                    ok = verify_score < 0.28
                    if not ok and verify_score < 0.40:
                        crop = roi[
                            loc[1] : loc[1] + int(vh * sy),
                            loc[0] : loc[0] + int(vw * sx),
                        ]
                        if crop.size and plate_support(crop) >= 0.22:
                            ok = True
                if not ok:
                    if hold_remaining > 0 and hold_loc is not None:
                        hold_remaining -= 1
                        tag = "verify_weak" if score > verify_require else "verify"
                        decision = f"hold({tag},{hold_remaining})"
                        final_loc = hold_loc
                    else:
                        decision = "reject_verify"
                else:
                    decision = "lock"
                    final_loc = loc
                    if score <= hold_good_score_max:
                        hold_remaining = hold_good_frames
                        hold_loc = loc

    results.append(
        {
            "i": i,
            "track": None if track_score is None else round(track_score, 4),
            "raw": raw_loc,
            "verify": None if verify_score is None else round(float(verify_score), 4),
            "decision": decision,
            "final": final_loc,
        }
    )

# overlay last interesting frame
for r in results:
    print(
        f"{r['i']:02d} track={r['track']} raw={r['raw']} v={r['verify']} -> {r['decision']} final={r['final']}"
    )

raw_ys = [r["raw"][1] for r in results if r["raw"]]
fin_ys = [r["final"][1] for r in results if r["final"]]
print("RAW_Y_SPAN", (min(raw_ys), max(raw_ys), max(raw_ys) - min(raw_ys)) if raw_ys else None)
print("FINAL_Y_SPAN", (min(fin_ys), max(fin_ys), max(fin_ys) - min(fin_ys)) if fin_ys else None)
holds = sum(1 for r in results if str(r["decision"]).startswith("hold"))
locks = sum(1 for r in results if r["decision"] == "lock")
lost = sum(1 for r in results if r["decision"] in ("lost", "reject_score", "reject_verify") or str(r["decision"]).startswith("reject_"))
print("COUNTS lock", locks, "hold", holds, "reject_or_lost", lost)

# draw comparison on a hold frame if any
hold_i = next((r["i"] for r in results if str(r["decision"]).startswith("hold")), None)
pick = hold_i if hold_i is not None else 0
frame = imread(frames[pick])
r = results[pick]
if r["raw"]:
    cv2.rectangle(frame, r["raw"], (r["raw"][0] + 116, r["raw"][1] + 24), (0, 0, 255), 2)
    cv2.putText(frame, f"raw {r['track']}", (r["raw"][0], r["raw"][1] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
if r["final"]:
    cv2.rectangle(frame, r["final"], (r["final"][0] + 116, r["final"][1] + 24), (0, 200, 255), 2)
    cv2.putText(frame, r["decision"], (r["final"][0], r["final"][1] + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
outp = OUT / f"overlay_{pick:02d}.png"
cv2.imencode(".png", frame)[1].tofile(str(outp))
print("OVERLAY", outp)
(OUT / "summary.txt").write_text(
    "\n".join(
        f"{r['i']:02d} track={r['track']} raw={r['raw']} v={r['verify']} -> {r['decision']} final={r['final']}"
        for r in results
    )
    + f"\nRAW_Y_SPAN {min(raw_ys) if raw_ys else None}-{max(raw_ys) if raw_ys else None}\n"
    + f"FINAL_Y_SPAN {min(fin_ys) if fin_ys else None}-{max(fin_ys) if fin_ys else None}\n"
    + f"lock={locks} hold={holds} reject_or_lost={lost}\n",
    encoding="utf-8",
)
print("OK")
