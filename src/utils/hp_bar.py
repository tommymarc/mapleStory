"""Detect MapleStory Artale monster HP bars (green fill, black outline).

Untouched monsters have no bar. After a hit, a thin green bar with a black
background appears above the head. Template matching often misses hit/die
poses, so the bar is used as an auxiliary locator for in-range combat.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

# Neon fill sampled from Artale debug frames: BGR (0, 243, 0).
HP_BAR_GREEN_BGR = (0, 243, 0)
HP_BAR_SCORE = 0.12
DEFAULT_BODY_SIZE = (56, 52)  # (width, height) of the guessed sprite under the bar


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_dark_pixel(pixel, thresh=45) -> bool:
    return (
        int(pixel[0]) <= thresh
        and int(pixel[1]) <= thresh
        and int(pixel[2]) <= thresh
    )


def _green_fill_mask(img_bgr: np.ndarray) -> np.ndarray:
    """Neon-green fill: high G, almost no R/B. Rejects grass and UI teal."""
    b = img_bgr[:, :, 0].astype(np.int16)
    g = img_bgr[:, :, 1].astype(np.int16)
    r = img_bgr[:, :, 2].astype(np.int16)
    return (
        (g >= 200)
        & (r <= 50)
        & (b <= 50)
        & (g >= r + 120)
        & (g >= b + 120)
    ).astype(np.uint8) * 255


def _dark_ratio(img_bgr: np.ndarray, y: int, x0: int, x1: int, thresh=45) -> float:
    height, width = img_bgr.shape[:2]
    if y < 0 or y >= height:
        return 0.0
    xa = max(0, min(width, x0))
    xb = max(0, min(width, x1))
    if xb <= xa:
        return 0.0
    row = img_bgr[y, xa:xb]
    dark = np.all(row <= thresh, axis=1)
    return float(np.count_nonzero(dark)) / float(row.shape[0])


def _column_dark(img_bgr: np.ndarray, x: int, y0: int, y1: int, thresh=45) -> bool:
    height, width = img_bgr.shape[:2]
    if x < 0 or x >= width:
        return False
    ya = max(0, min(height, y0))
    yb = max(0, min(height, y1))
    if yb <= ya:
        return False
    col = img_bgr[ya:yb, x]
    dark = np.all(col <= thresh, axis=1)
    return float(np.count_nonzero(dark)) >= 0.6 * float(col.shape[0])


def _expand_black_bar(
    img_bgr: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    max_width: int,
) -> Tuple[int, int]:
    """Grow left/right through the black empty-HP / outline so center is not left-biased."""
    height, width = img_bgr.shape[:2]
    left = x
    right = x + w
    y1 = min(height, y + h)
    while left > 0 and (right - left) < max_width:
        if not _column_dark(img_bgr, left - 1, y, y1):
            break
        if y > 0 and not _is_dark_pixel(img_bgr[y - 1, left - 1]):
            # Roof should stay black while we are still on the bar.
            if _dark_ratio(img_bgr, y - 1, left - 1, right) < 0.4:
                break
        left -= 1
    while right < width and (right - left) < max_width:
        if not _column_dark(img_bgr, right, y, y1):
            break
        if y > 0 and not _is_dark_pixel(img_bgr[y - 1, min(width - 1, right)]):
            if _dark_ratio(img_bgr, y - 1, left, right + 1) < 0.4:
                break
        right += 1
    return left, right - left


def _looks_like_hp_bar(
    img_bgr: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    area: int,
) -> bool:
    """Require a thin bar sitting on a black roof with at least one black cap."""
    if h < 2 or h > 6:
        return False
    if w < 8 or w > 70:
        return False
    if w < h * 3:
        return False
    box_area = max(1, w * h)
    if area < max(8, int(box_area * 0.35)):
        return False
    height, width = img_bgr.shape[:2]
    mid_y = min(height - 1, y + h // 2)
    left_cap = _column_dark(img_bgr, x - 1, y, y + h) if x > 0 else False
    right_cap = _column_dark(img_bgr, x + w, y, y + h) if (x + w) < width else False
    roof = _dark_ratio(img_bgr, y - 1, x, x + w) if y > 0 else 0.0
    if roof < 0.45:
        return False
    if not (left_cap or right_cap):
        return False
    return True


def detect_monster_hp_bars(
    img_bgr: np.ndarray,
    origin: Sequence[int] = (0, 0),
    body_size: Optional[Sequence[int]] = None,
    body_gap: int = 4,
) -> List[Dict[str, Any]]:
    """Find HP bars and return monster-shaped dicts for the sprite under each bar.

    Args:
        img_bgr: BGR frame or ROI (no debug overlay).
        origin: Top-left of the ROI in full-frame coordinates.
        body_size: (width, height) guessed sprite box under the bar.
        body_gap: Pixels from bar bottom to sprite top.
    """
    if img_bgr is None or img_bgr.size == 0:
        return []
    if img_bgr.ndim != 3 or img_bgr.shape[2] < 3:
        return []

    ox, oy = int(origin[0]), int(origin[1])
    if body_size is None:
        body_w, body_h = DEFAULT_BODY_SIZE
    else:
        body_w = max(24, _to_int(body_size[0], DEFAULT_BODY_SIZE[0]))
        body_h = max(24, _to_int(body_size[1], DEFAULT_BODY_SIZE[1]))
    body_gap = max(0, _to_int(body_gap, 4))

    mask = _green_fill_mask(img_bgr)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    frame_h, frame_w = img_bgr.shape[:2]
    monsters: List[Dict[str, Any]] = []
    for i in range(1, num_labels):
        x, y, w, h, area = (int(v) for v in stats[i])
        if not _looks_like_hp_bar(img_bgr, x, y, w, h, area):
            continue
        full_x, full_w = _expand_black_bar(img_bgr, x, y, w, h, max_width=70)
        full_w = max(w, full_w)
        fill_ratio = min(1.0, float(w) / float(max(1, full_w)))
        bar_x = ox + full_x
        bar_y = oy + y
        bar_w = full_w
        bar_h = h

        sprite_w = max(body_w, bar_w + 8)
        sprite_h = body_h
        body_x = int(round(bar_x + bar_w / 2.0 - sprite_w / 2.0))
        body_y = bar_y + bar_h + body_gap
        body_x = max(ox, min(ox + frame_w - 1, body_x))
        body_y = max(oy, min(oy + frame_h - 1, body_y))

        monsters.append({
            "name": "Health Bar",
            "position": (int(body_x), int(body_y)),
            "size": (int(sprite_w), int(sprite_h)),
            "score": HP_BAR_SCORE,
            "source": "hp_bar",
            "has_hp_bar": True,
            "hp_bar": (int(bar_x), int(bar_y), int(bar_w), int(bar_h)),
            "hp_fill_ratio": fill_ratio,
        })
    return monsters


def hp_bar_matches_monster(
    hp_monster: Dict[str, Any],
    monster: Dict[str, Any],
) -> bool:
    """True when the bar sits on/near the head of an existing template box."""
    bar = hp_monster.get("hp_bar")
    if not bar or len(bar) < 4:
        return False
    bx, by, bw, bh = (int(v) for v in bar[:4])
    bar_cx = bx + bw * 0.5
    bar_bottom = by + bh
    try:
        mx, my = monster["position"]
        mw, mh = monster["size"]
    except (KeyError, TypeError, ValueError):
        return False
    m_cx = mx + mw * 0.5
    x_tol = max(24.0, mw * 0.6, bw * 0.85)
    if abs(bar_cx - m_cx) > x_tol:
        return False
    if bar_bottom < my - 22:
        return False
    if by > my + min(28.0, max(12.0, mh * 0.45)):
        return False
    return True


def merge_hp_bar_detections(
    template_monsters: Iterable[Dict[str, Any]],
    hp_monsters: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Attach HP bars to overlapping templates; keep unmatched bars as extra targets."""
    merged: List[Dict[str, Any]] = []
    used_hp = set()
    hp_list = list(hp_monsters or [])
    for monster in template_monsters or []:
        item = dict(monster)
        for idx, hp_monster in enumerate(hp_list):
            if idx in used_hp:
                continue
            if hp_bar_matches_monster(hp_monster, item):
                used_hp.add(idx)
                item["has_hp_bar"] = True
                item["hp_bar"] = hp_monster.get("hp_bar")
                item["hp_fill_ratio"] = hp_monster.get("hp_fill_ratio")
                break
        merged.append(item)
    for idx, hp_monster in enumerate(hp_list):
        if idx not in used_hp:
            merged.append(dict(hp_monster))
    return merged


def hp_bar_in_attack_box(
    monster: Dict[str, Any],
    box: Sequence[int],
    extra_top: int = 56,
) -> bool:
    """Auxiliary in-range test: bar center X inside the attack box, Y near the box."""
    if not (monster.get("has_hp_bar") or monster.get("source") == "hp_bar"):
        return False
    bar = monster.get("hp_bar")
    if not bar or len(bar) < 4:
        return False
    x0, y0, x1, y1 = (int(v) for v in box[:4])
    bx, by, bw, bh = (int(v) for v in bar[:4])
    bar_cx = bx + bw * 0.5
    bar_cy = by + bh * 0.5
    if not (x0 <= bar_cx <= x1):
        return False
    return (y0 - max(0, extra_top)) <= bar_cy <= (y1 + 12)
