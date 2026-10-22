"""Nametag template cleanup and matching helpers for Artale and CMS nameplates."""

import json
import os
import re

import cv2
import numpy as np


# Artale in-world nameplates are cyan/teal pills with dark text.
PLATE_HSV_LO = (50, 40, 110)
PLATE_HSV_HI = (115, 220, 255)
# CMS (国服) nameplates are dark brown rounded pills with white text.
# Tuned from 雀雀被雷电 sample: plate body ~H 13-22, S 90-135, V 80-100.
CMS_BROWN_HSV_LO = (10, 40, 40)
CMS_BROWN_HSV_HI = (25, 160, 120)
DEFAULT_NAMETAG_DIR = "nametag"
NAMETAG_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
SKIP_NAMETAG_NAMES = {"example"}
CHROMA_GREEN_BGR = (0, 255, 0)

# Tight user crops (name / name+guild+medal) stay unchanged by prepare_*.
TIGHT_NAMETAG_MAX_WIDTH = 200
TIGHT_NAMETAG_MAX_HEIGHT = 120

# Hard multi-row mode follows the *imported* template (一层/两层/三层):
# 0 secondary → name-only; 1 secondary → that band must match; 2+ → ALL
# secondaries. Import UI crops the stored PNG to the chosen layer count.
SECONDARY_ROW_MATCH_THRES = 0.36
NAME_BAND_MATCH_THRES = 0.34


def safe_nametag_name(name):
    safe_name = re.sub(
        r"[^0-9A-Za-z_\u4e00-\u9fff-]+",
        "_",
        str(name).strip(),
    ).strip("_")
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("角色名图片名称不包含可用字符。")
    return safe_name


def nametag_image_path(name, directory=DEFAULT_NAMETAG_DIR):
    return os.path.join(directory, f"{name}.png")


def list_saved_nametags(directory=DEFAULT_NAMETAG_DIR):
    """Return saved nametag (name, path) pairs, newest first."""
    if not os.path.isdir(directory):
        return []

    entries = []
    for filename in os.listdir(directory):
        stem, extension = os.path.splitext(filename)
        if extension.lower() not in NAMETAG_IMAGE_EXTENSIONS:
            continue
        if stem.lower() in SKIP_NAMETAG_NAMES:
            continue
        # Human-only reference crops (e.g. 雀雀被雷电_full.png), not engine templates.
        if stem.lower().endswith("_full"):
            continue
        path = os.path.join(directory, filename)
        if not os.path.isfile(path):
            continue
        entries.append((stem, path, os.path.getmtime(path)))

    entries.sort(key=lambda item: (-item[2], item[0].lower()))
    return [(name, path) for name, path, _mtime in entries]


def delete_saved_nametag(name, directory=DEFAULT_NAMETAG_DIR):
    """Delete a saved nametag image. Returns the removed path."""
    safe_name = safe_nametag_name(name)
    removed_path = None
    for extension in NAMETAG_IMAGE_EXTENSIONS:
        path = os.path.join(directory, safe_name + extension)
        if os.path.isfile(path):
            os.remove(path)
            removed_path = path
    if removed_path is None:
        raise FileNotFoundError(f"找不到角色名图片: {safe_name}")
    boxes_meta = os.path.join(directory, safe_name + ".boxes.json")
    if os.path.isfile(boxes_meta):
        os.remove(boxes_meta)
    return removed_path


def as_bgr(image):
    if image is None:
        return None
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image


def cyan_plate_mask(image):
    """Binary mask for Artale cyan/teal nameplate pills."""
    bgr = as_bgr(image)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, PLATE_HSV_LO, PLATE_HSV_HI)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)


def brown_plate_mask(image):
    """Binary mask for CMS dark-brown nameplate pills.

    Open removes sand speckles, then a horizontal close joins the pill without
    bridging the 1px gap between stacked CMS name/guild rows (an elliptical
    close would merge those rows).
    """
    bgr = as_bgr(image)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, CMS_BROWN_HSV_LO, CMS_BROWN_HSV_HI)
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_open, iterations=1)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_h, iterations=1)


def plate_mask(image):
    """Union of Artale cyan and CMS brown nameplate masks."""
    return cv2.bitwise_or(cyan_plate_mask(image), brown_plate_mask(image))


def plate_support(image):
    """Fraction of pixels that look like a nameplate (cyan OR brown)."""
    if image is None or getattr(image, "size", 0) == 0:
        return 0.0
    return float(plate_mask(image).mean() / 255.0)


def cyan_plate_support(image):
    if image is None or getattr(image, "size", 0) == 0:
        return 0.0
    return float(cyan_plate_mask(image).mean() / 255.0)


def brown_plate_support(image):
    if image is None or getattr(image, "size", 0) == 0:
        return 0.0
    return float(brown_plate_mask(image).mean() / 255.0)


def _iter_boxes_from_mask(
    mask,
    min_width=28,
    max_width=220,
    min_height=8,
    max_height=40,
):
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        if not (min_width <= width <= max_width and min_height <= height <= max_height):
            continue
        if width < height * 2:
            continue
        if area < width * height * 0.30:
            continue
        yield int(x), int(y), int(width), int(height), int(area)


def iter_plate_boxes(
    image,
    min_width=28,
    max_width=220,
    min_height=8,
    max_height=40,
):
    """Yield plate boxes from Artale cyan and CMS brown masks separately.

    Running connected components on the OR-union can glue a CMS medal (cyan-
    tinted) to nearby brown speckles and invent a fake wide plate. Matching
    still uses ``plate_mask`` / ``plate_support`` (union) for ROI checks.
    """
    bgr = as_bgr(image)
    seen = set()
    for mask in (cyan_plate_mask(bgr), brown_plate_mask(bgr)):
        for box in _iter_boxes_from_mask(
            mask,
            min_width=min_width,
            max_width=max_width,
            min_height=min_height,
            max_height=max_height,
        ):
            key = box[:4]
            if key in seen:
                continue
            seen.add(key)
            yield box


def _select_name_plate_box(boxes, width, height):
    """Pick the character-name plate: topmost among horizontally centered boxes.

    CMS stacks guild/medal under the name; matching must key off the top row,
    which is always present. Artale usually has a single cyan plate.
    """
    if not boxes:
        return None
    center_x = width / 2.0
    max_dx = max(width * 0.35, 40.0)
    centered = [
        box
        for box in boxes
        if abs((box[0] + box[2] / 2.0) - center_x) <= max_dx
    ]
    candidates = centered or list(boxes)
    # Topmost first; break ties by larger area.
    return min(candidates, key=lambda box: (box[1], -box[4]))


def _on_green_chroma(crop, pad=1):
    """Place a BGR crop on pure green (0,255,0) for get_mask chroma keying."""
    bgr = as_bgr(crop)
    if bgr is None or bgr.size == 0:
        return crop
    height, width = bgr.shape[:2]
    canvas = np.empty((height + 2 * pad, width + 2 * pad, 3), dtype=np.uint8)
    canvas[:] = CHROMA_GREEN_BGR
    canvas[pad : pad + height, pad : pad + width] = bgr
    return canvas


def _extend_for_medal(bgr, image, x, y, box_w, box_h, pad=1):
    """Grow crop downward to include an Artale medal/title bar under the plate."""
    height, width = bgr.shape[:2]
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(width, x + box_w + pad)
    y1 = min(height, y + box_h + pad)

    # Only scan near the plate's x-range so surrounding terrain does not
    # inflate the template to the full screenshot width.
    scan_x0 = max(0, x - 8)
    scan_x1 = min(width, x + box_w + 8)
    medal_scan = min(height, y1 + max(28, box_h + 12))
    if medal_scan > y1 and scan_x1 > scan_x0:
        region = bgr[y1:medal_scan, scan_x0:scan_x1]
        green = (
            (region[:, :, 0] <= 20)
            & (region[:, :, 1] >= 230)
            & (region[:, :, 2] <= 20)
        )
        content = ~green
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        content = content & ((hsv[:, :, 1] > 25) | (hsv[:, :, 2] < 200))
        if content.any():
            ys, xs = np.where(content)
            # Always grow downward for a medal/title bar.
            y1 = min(height, y1 + int(ys.max()) + 1 + pad)
            # Only widen horizontally when the extra content looks like a bar
            # under the name (not full-width terrain filling the scan).
            span = int(xs.max()) - int(xs.min()) + 1
            # Medals are only slightly wider than the name; full-scan terrain
            # spans nearly the whole band and must not inflate the crop.
            if span <= int(box_w * 1.15) + 4:
                x0 = min(x0, max(0, scan_x0 + int(xs.min()) - pad))
                x1 = max(x1, min(width, scan_x0 + int(xs.max()) + 1 + pad))

    cropped = image[y0:y1, x0:x1]
    if cropped.size == 0:
        return image
    return cropped


def _collect_stack_boxes(name_box, boxes, max_gap=14):
    """Boxes stacked under the name plate (guild / medal), top-to-bottom."""
    stack = [name_box]
    bottom = name_box[1] + name_box[3]
    name_cx = name_box[0] + name_box[2] / 2.0
    candidates = sorted(
        [box for box in boxes if box[:4] != name_box[:4]],
        key=lambda box: box[1],
    )
    for box in candidates:
        x, y, width, height, _area = box
        if y < name_box[1]:
            continue
        if y > bottom + max_gap:
            break
        cx = x + width / 2.0
        if abs(cx - name_cx) > max(name_box[2], width) * 0.8 + 8:
            continue
        stack.append(box)
        bottom = max(bottom, y + height)
    return stack


def _union_box_bounds(boxes, pad, width, height):
    x0 = max(0, min(box[0] for box in boxes) - pad)
    y0 = max(0, min(box[1] for box in boxes) - pad)
    x1 = min(width, max(box[0] + box[2] for box in boxes) + pad)
    y1 = min(height, max(box[1] + box[3] for box in boxes) + pad)
    return x0, y0, x1, y1



def nametag_match_mask(image):
    """Runtime match mask, driven by the auto-measured boxes.

    Kept (map-independent pixels only):
      - name / medal plates: per-row span between the plate's outermost
        plate/white pixels (opaque plate incl. rim, text, dark divider),
      - guild row: white guild text pixels only (the rgba(0,0,0,~0.8) box
        takes the map colour and is ignored),
      - elsewhere: white / blue / pink decoration (clouds, plate outlines).
    Green matte and yellow pet plates are always ignored. Mask is computed at
    match time (cached); the saved PNG is never rewritten.
    """
    bgr = as_bgr(image)
    if bgr is None or bgr.size == 0:
        return None
    key = ("mask", _image_key(bgr))
    cached = _BOXES_CACHE.get(key)
    if cached is not None:
        return cached
    height, width = bgr.shape[:2]
    m = _nametag_color_masks(bgr)
    deco = m["white"] | m["plate"]
    keep = deco.copy()
    boxes = measure_nametag_boxes(bgr)
    if boxes is not None:
        # Outside the measured boxes only white/plate pixels hugging a plate
        # (outline rows, cloud tops) count; stray terrain specks do not.
        near = np.zeros_like(keep)
        for k in ("name", "medal"):
            box = boxes.get(k)
            if box:
                x, y, w, h = box
                near[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] = True
        keep &= near
        for k in ("name", "medal"):
            box = boxes.get(k)
            if not box:
                continue
            x, y, w, h = box
            sub = (deco | m["brown"])[y:y + h, x:x + w]
            for r in range(sub.shape[0]):
                cols = np.flatnonzero(sub[r])
                if cols.size:
                    keep[y + r, x + cols[0]:x + cols[-1] + 1] = True
        g = boxes.get("guild")
        if g:
            x, y, w, h = g
            keep[y:y + h, x:x + w] = m["white"][y:y + h, x:x + w]
    keep &= ~m["pet"]
    keep &= ~m["green"]
    out = keep.astype(np.uint8) * 255
    if float(keep.mean()) < 0.03:
        out = ((~m["green"]).astype(np.uint8) * 255)
    if len(_BOXES_CACHE) >= _BOXES_CACHE_MAX:
        _BOXES_CACHE.clear()
    _BOXES_CACHE[key] = out
    return out


def _peak_distance(a, b):
    return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


def _point_in_box(loc, box):
    if loc is None or box is None:
        return False
    x, y = int(loc[0]), int(loc[1])
    x0, y0, x1, y1 = box
    return x0 <= x < x1 and y0 <= y < y1


def pick_nametag_candidate(
    candidates,
    prefer_box=None,
    threshold=0.18,
    accept_thres=None,
    min_peak_sep=90,
):
    """Choose among ranked nametag candidates with ROI + ambiguity gates.

    ``candidates``: iterable of (loc, score, size, scale) sorted best-first
    (lower score is better). ``prefer_box`` is the minimap-biased ROI.

    Rules:
    1. Prefer / require hits inside ``prefer_box`` when any acceptable in-ROI
       candidate exists — a good out-of-ROI score loses to an in-ROI hit.
    2. If best and a distant second peak are both under ``threshold``, prefer
       the one inside ``prefer_box``.
    3. If nothing acceptable is in-ROI, fall back to the global best.
    """
    cands = [c for c in (candidates or []) if c is not None]
    if not cands:
        return None
    if accept_thres is None:
        accept_thres = max(float(threshold) + 0.08, 0.28)

    def _score(c):
        return float(c[1])

    def _in(c):
        return prefer_box is None or _point_in_box(c[0], prefer_box)

    # Deduplicate near-duplicate peaks.
    uniq = []
    for c in sorted(cands, key=_score):
        if any(_peak_distance(c[0], u[0]) < 24 for u in uniq):
            continue
        uniq.append(c)
    cands = uniq
    best = cands[0]

    in_roi = [c for c in cands if _in(c) and _score(c) < accept_thres]
    if prefer_box is not None and in_roi:
        best_in = min(in_roi, key=_score)
        # Ambiguity: distant second under hard threshold → prefer ROI.
        under = [c for c in cands if _score(c) < float(threshold)]
        if len(under) >= 2:
            a, b = under[0], under[1]
            if _peak_distance(a[0], b[0]) >= int(min_peak_sep):
                a_in, b_in = _in(a), _in(b)
                if b_in and not a_in:
                    return b[:4]
                if a_in and not b_in:
                    return a[:4]
                if a_in and b_in:
                    return min([a, b], key=_score)[:4]
        # Reject out-of-ROI winner when an acceptable in-ROI exists.
        if not _in(best):
            return best_in[:4]
        return best[:4]

    # No usable in-ROI hit — allow full-frame fallback.
    return best[:4]


# ---- auto-measured box geometry (computed from the imported crop) ----------
# Nothing here is hard-coded per character: plate boxes come from colour masks
# refined row-by-row; the guild box (rgba(0,0,0,~0.8), invisible on dark maps)
# comes from its white text bbox. Only the game's CSS-like layout ratio between
# guild text height and its box padding is used when the box itself is not
# visible (measured on a crop where it is visible: pad_y=5/12, pad_x=4/12 of
# text height).
NAMETAG_BOXES_META_SUFFIX = ".boxes.json"
NAMETAG_BOXES_VERSION = 1
GUILD_PAD_Y_PER_TEXT_H = 5.0 / 12.0
GUILD_PAD_X_PER_TEXT_H = 4.0 / 12.0
# Native game client height vs bot working height (1366x768 -> 1296x700).
NAMETAG_NATIVE_PLATE_MIN_H = 19.5  # 20px native name plate, ~18px after resize
_BOXES_CACHE = {}
_BOXES_CACHE_MAX = 64


def _nametag_color_masks(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)
    white = (s <= 50) & (v >= 200)
    blue = (h >= 90) & (h <= 135) & (s >= 60) & (v >= 90)
    pink = ((h >= 140) | (h <= 8)) & (s >= 60) & (v >= 120)
    cyan = cv2.inRange(hsv, PLATE_HSV_LO, PLATE_HSV_HI) > 0
    brown = cv2.inRange(hsv, CMS_BROWN_HSV_LO, CMS_BROWN_HSV_HI) > 0
    green = (bgr[:, :, 0] <= 20) & (bgr[:, :, 1] >= 230) & (bgr[:, :, 2] <= 20)
    plate = (blue | pink | cyan) & ~green
    return {
        "white": white & ~green,
        "plate": plate,
        "brown": brown & ~green,
        "pet": (h >= 15) & (h <= 40) & (s >= 90) & (v >= 130),
        "green": green,
    }


def _refine_plate_box(masks, box, height, frac=0.30):
    """Trim/extend an opaque plate box row-wise (incl. full bottom edge)."""
    x, y, w, h = [int(v) for v in box[:4]]
    plate = masks["plate"] | masks["brown"]
    pw = plate | masks["white"]
    xs = slice(x, x + w)

    def rf(m, row):
        return float(m[row, xs].mean()) if 0 <= row < height else 0.0

    while h > 4 and rf(pw, y) < frac:
        y += 1
        h -= 1
    while h > 4 and rf(pw, y + h - 1) < frac:
        h -= 1
    while y > 0 and rf(plate, y - 1) >= frac:
        y -= 1
        h += 1
    while y + h < height and rf(plate, y + h) >= frac:
        h += 1
    return [x, y, w, h]


def _skip_outline_rows(white, y, step, x0, x1, limit, frac=0.5):
    """Skip white plate-outline rows adjacent to a plate edge."""
    n = 0
    while 0 <= y < white.shape[0] and n < limit:
        if float(white[y, x0:x1].mean()) < frac:
            break
        y += step
        n += 1
    return y


def _text_bbox(white, y0, y1, x0, x1, min_rows=6, min_px=24):
    """Largest contiguous (gap<=1) white-text row run inside a region."""
    if y1 - y0 < min_rows or x1 <= x0:
        return None
    region = white[y0:y1, x0:x1]
    counts = region.sum(axis=1)
    runs = []
    start = None
    gap = 0
    for i, c in enumerate(counts):
        if c >= 2:
            if start is None:
                start = i
            gap = 0
            end = i
        elif start is not None:
            gap += 1
            if gap > 1:
                runs.append((start, end))
                start = None
                gap = 0
    if start is not None:
        runs.append((start, end))
    best = None
    for a, b in runs:
        px = int(counts[a:b + 1].sum())
        if b - a + 1 >= min_rows and px >= min_px:
            if best is None or px > best[2]:
                best = (a, b, px)
    if best is None:
        return None
    a, b, _ = best
    ys, xs = np.where(region[a:b + 1])
    return [
        int(x0 + xs.min()),
        int(y0 + a),
        int(xs.max() - xs.min() + 1),
        int(b - a + 1),
    ]


def _box_band(box, height, pad=1):
    if not box:
        return None
    return [max(0, int(box[1]) - pad), min(height, int(box[1]) + int(box[3]) + pad)]


def _image_key(bgr):
    import hashlib
    return (bgr.shape, hashlib.md5(np.ascontiguousarray(bgr).tobytes()).hexdigest())


def measure_nametag_boxes(image, layers=None):
    """Auto-measure name / guild / medal boxes on a nametag crop.

    Returns a JSON-able dict (boxes are [x, y, w, h] in crop pixels):
      name, guild, guild_text, medal, second_kind ('guild'|'medal'|None),
      bands {name, guild, medal} as [y0, y1], guild_dy, layers,
      source_scale ('native'|'resized'). Returns None when no name plate.
    ``layers`` (1/2/3) limits which secondary rows are kept; None = infer.
    """
    bgr = as_bgr(image)
    if bgr is None or getattr(bgr, "size", 0) == 0:
        return None
    key = (_image_key(bgr), layers)
    cached = _BOXES_CACHE.get(key)
    if cached is not None:
        return cached
    height, width = bgr.shape[:2]
    masks = _nametag_color_masks(bgr)
    raw = list(iter_plate_boxes(bgr))
    if not raw:
        return None
    # Name plate must be an opaque (blue/pink/cyan/brown) plate, not the
    # translucent guild box.
    name_raw = _select_name_plate_box(raw, width, height)
    if name_raw is None:
        return None
    name = _refine_plate_box(masks, name_raw, height)
    nx, ny, nw, nh = name
    name_bottom = ny + nh

    # Opaque lower plates (medal/tag) under the name, horizontally related.
    lower = []
    dark_boxes = []
    ncx = nx + nw / 2.0
    for b in raw:
        if b[:4] == tuple(name_raw[:4]):
            continue
        if b[1] < name_bottom:
            continue
        bx, by, bw, bh = b[:4]
        if abs((bx + bw / 2.0) - ncx) > max(nw, bw) * 0.8 + 8:
            continue
        roi = masks["plate"][by:by + bh, bx:bx + bw]
        if float(roi.mean()) >= 0.35:
            lower.append(_refine_plate_box(masks, b, height))
        else:
            dark_boxes.append([int(bx), int(by), int(bw), int(bh)])
    lower.sort(key=lambda b: b[1])

    # Guild text between name plate and first opaque lower plate.
    white = masks["white"]
    gx0 = max(0, int(nx - nw * 0.35))
    gx1 = min(width, int(nx + nw * 1.35))
    ty0 = _skip_outline_rows(white, name_bottom, 1, nx, nx + nw, 2)
    ty1 = lower[0][1] if lower else height
    if lower:
        m = lower[0]
        ty1 = _skip_outline_rows(white, m[1] - 1, -1, m[0], m[0] + m[2], 2) + 1
    guild_text = _text_bbox(white, ty0, ty1, gx0, gx1)
    guild = None
    if guild_text is not None:
        tx, ty, tw, th = guild_text
        # Visible translucent box (light maps / matte fill): use it directly.
        for d in dark_boxes:
            if d[0] <= tx and d[1] <= ty and d[0] + d[2] >= tx + tw and d[1] + d[3] >= ty + th:
                guild = list(d)
                break
        if guild is None:
            py = int(round(th * GUILD_PAD_Y_PER_TEXT_H))
            px = int(round(th * GUILD_PAD_X_PER_TEXT_H))
            guild = [
                max(0, tx - px),
                max(0, ty - py),
                0,
                0,
            ]
            guild[2] = min(width, tx + tw + px) - guild[0]
            guild[3] = min(height, ty + th + py) - guild[1]
    medal = None
    if lower:
        top = lower[0][1]
        # A medal must sit below the guild row when a guild row exists.
        cands = [b for b in lower if guild is None or b[1] >= guild[1] + guild[3] - 1]
        if cands:
            medal = list(cands[0])
            # Union with stacked tag rows directly under the medal.
            for b in cands[1:]:
                if b[1] <= medal[1] + medal[3] + 2:
                    x0 = min(medal[0], b[0]); y0 = medal[1]
                    x1 = max(medal[0] + medal[2], b[0] + b[2])
                    y1 = max(medal[1] + medal[3], b[1] + b[3])
                    medal = [x0, y0, x1 - x0, y1 - y0]
        del top

    if layers is not None:
        layers = normalize_nametag_layers(layers, default=3)
        if layers <= 1:
            guild = guild_text = medal = None
        elif layers == 2:
            if guild is not None:
                medal = None
    if guild is not None:
        second_kind = "guild"
    elif medal is not None:
        second_kind = "medal"
    else:
        second_kind = None
    n_layers = 1 + int(guild is not None) + int(medal is not None)

    name_band = [0 if ny <= 2 else max(0, ny - 1), min(height, name_bottom + 1)]
    guild_band = _box_band(guild, height)
    medal_band = _box_band(medal, height)
    if medal_band is not None:
        medal_band[0] = max(medal_band[0], guild_band[1] if guild_band else name_band[1] - 1)
    second_band = guild_band or medal_band
    result = {
        "version": NAMETAG_BOXES_VERSION,
        "size": [int(width), int(height)],
        "layers": int(n_layers),
        "name": [int(v) for v in name],
        "guild": guild,
        "guild_text": guild_text,
        "medal": medal,
        "second_kind": second_kind,
        "bands": {"name": name_band, "guild": guild_band, "medal": medal_band},
        "guild_dy": int(second_band[0]) if second_band else None,
        "source_scale": "native" if nh >= NAMETAG_NATIVE_PLATE_MIN_H else "resized",
    }
    if len(_BOXES_CACHE) >= _BOXES_CACHE_MAX:
        _BOXES_CACHE.clear()
    _BOXES_CACHE[key] = result
    return result


def nametag_boxes_meta_path(name, directory=DEFAULT_NAMETAG_DIR):
    safe = safe_nametag_name(name)
    return os.path.join(directory, f"{safe}{NAMETAG_BOXES_META_SUFFIX}")


def save_nametag_boxes(name, image, layers=None, directory=DEFAULT_NAMETAG_DIR):
    """Measure boxes on the stored crop and write <name>.boxes.json."""
    boxes = measure_nametag_boxes(image, layers=layers)
    if boxes is None:
        return None, None
    path = nametag_boxes_meta_path(name, directory)
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(boxes, fh, ensure_ascii=False, indent=2)
    return path, boxes


def load_nametag_boxes(name, directory=DEFAULT_NAMETAG_DIR, image=None,
                       layers=None, write_if_missing=True):
    """Load <name>.boxes.json; (re)compute + write when missing/stale."""
    path = nametag_boxes_meta_path(name, directory)
    data = None
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = None
    if data is not None and image is not None:
        bgr = as_bgr(image)
        stale = (
            data.get("version") != NAMETAG_BOXES_VERSION
            or list(data.get("size") or []) != [bgr.shape[1], bgr.shape[0]]
            or (layers is not None and int(data.get("layers", 0)) > int(layers))
        )
        if stale:
            data = None
    if data is None and image is not None:
        data = measure_nametag_boxes(image, layers=layers)
        if data is not None and write_if_missing:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
            except OSError:
                pass
    return data


def parse_nametag_row_bands(image):
    """Split a nametag template into name / guild / medal vertical bands.

    Returns a dict:
      - ``name``: (y0, y1) required top plate band (full template width)
      - ``guild``: (y0, y1) or None — optional brown family/guild row
      - ``medal``: (y0, y1) or None — optional medal/tag under guild

    Bands are relative to the template's top-left. Player localization should
    use the **name** band top (template y=0 when the crop starts at the name).
    """
    bgr = as_bgr(image)
    if bgr is None or bgr.size == 0:
        return {"name": (0, 0), "guild": None, "medal": None}

    measured = measure_nametag_boxes(bgr)
    if measured is not None:
        b = measured["bands"]
        return {
            "name": tuple(b["name"]),
            "guild": tuple(b["guild"]) if b.get("guild") else None,
            "medal": tuple(b["medal"]) if b.get("medal") else None,
        }

    height, width = bgr.shape[:2]
    boxes = list(iter_plate_boxes(bgr))
    if not boxes:
        # No detectable plates — treat the whole image as the name row.
        return {"name": (0, height), "guild": None, "medal": None}

    name_box = _select_name_plate_box(boxes, width, height)
    if name_box is None:
        return {"name": (0, height), "guild": None, "medal": None}

    stack = _collect_stack_boxes(name_box, boxes)
    # name band: from top of crop (or name top) through name plate bottom
    name_y0 = 0 if name_box[1] <= 2 else max(0, name_box[1] - 1)
    name_y1 = min(height, name_box[1] + name_box[3] + 1)

    guild = None
    medal = None
    extras = stack[1:]
    if extras:
        # First stacked plate under the name is guild/family when brown-heavy;
        # remaining / cyan-tinted lower bars are medal/tag.
        first = extras[0]
        fy0 = max(name_y1, first[1] - 1)
        fy1 = min(height, first[1] + first[3] + 1)
        first_roi = bgr[first[1] : first[1] + first[3], first[0] : first[0] + first[2]]
        first_is_brown = brown_plate_support(first_roi) >= max(
            cyan_plate_support(first_roi), 0.05
        )
        if first_is_brown:
            guild = (fy0, fy1)
            rest = extras[1:]
        else:
            # Non-brown second row (Artale medal / CMS rainbow tag)
            medal = (fy0, fy1)
            rest = extras[1:]
        if rest and medal is None:
            last = rest[-1]
            medal = (
                max(fy1 if guild else name_y1, last[1] - 1),
                min(height, last[1] + last[3] + 1),
            )
        elif rest and medal is not None:
            last = rest[-1]
            medal = (
                medal[0],
                min(height, max(medal[1], last[1] + last[3] + 1)),
            )

    # Guild/family plate is an rgba(0,0,0,0.8) translucent box: on dark maps it
    # is not detected as a plate. Recover it from the white guild text sitting
    # between the name plate and a lower medal plate (map-independent).
    if guild is None:
        lower = [b for b in boxes if b[1] >= name_y1 + 12]
        if lower:
            mtop = min(b[1] for b in lower)
            white = (bgr[name_y1:mtop].min(axis=2) > 225).sum(axis=1)
            if mtop - name_y1 >= 12 and int((white >= 4).sum()) >= 6:
                guild = (name_y1, max(name_y1 + 1, mtop - 1))
                last = max(lower, key=lambda b: b[1] + b[3])
                medal = (guild[1], min(height, last[1] + last[3] + 1))

    # If nothing was classified but template continues below the name with
    # plate support, keep a single optional band as medal for scoring.
    if guild is None and medal is None and name_y1 < height - 4:
        below = bgr[name_y1:height]
        if plate_support(below) >= 0.08:
            medal = (name_y1, height)

    return {"name": (name_y0, name_y1), "guild": guild, "medal": medal}



# ---- layer / row-count helpers (import-time 一层/两层/三层) ----
NAMETAG_LAYER_META_SUFFIX = ".layers.json"
VALID_NAMETAG_LAYERS = (1, 2, 3)


def normalize_nametag_layers(value, default=3):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return int(default)
    if n in VALID_NAMETAG_LAYERS:
        return n
    return int(default)


def nametag_layers_meta_path(name, directory=DEFAULT_NAMETAG_DIR):
    safe = safe_nametag_name(name)
    return os.path.join(directory, f"{safe}{NAMETAG_LAYER_META_SUFFIX}")


def save_nametag_layers(name, layers, directory=DEFAULT_NAMETAG_DIR):
    layers = normalize_nametag_layers(layers, default=3)
    path = nametag_layers_meta_path(name, directory)
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"layers": layers}, fh, ensure_ascii=False, indent=2)
    return path


def load_nametag_layers(name, directory=DEFAULT_NAMETAG_DIR, default=None):
    path = nametag_layers_meta_path(name, directory)
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return normalize_nametag_layers(data.get("layers"), default=default or 3)
    except Exception:
        return default


def crop_nametag_to_layers(image, layers):
    """Keep only the first N plate rows from a nametag crop.

    1 = name only (no hard secondary)
    2 = name + first secondary (guild OR medal)
    3 = full name+guild+medal stack (hard match requires both secondaries)
    """
    layers = normalize_nametag_layers(layers, default=3)
    if image is None or getattr(image, "size", 0) == 0:
        return image
    if layers >= 3:
        return image
    bands = parse_nametag_row_bands(image)
    name = bands.get("name") or (0, image.shape[0])
    if layers <= 1:
        y1 = max(int(name[1]), 1)
        return image[0:y1].copy()
    secondary = None
    guild = bands.get("guild")
    medal = bands.get("medal")
    if guild and guild[1] > guild[0]:
        secondary = guild
    elif medal and medal[1] > medal[0]:
        secondary = medal
    if secondary is None:
        y1 = max(int(name[1]), 1)
        return image[0:y1].copy()
    y1 = max(int(secondary[1]), int(name[1]))
    return image[0:y1].copy()



def crop_nametag_guild_band(image):
    """Crop only the guild/family plate row from a multi-layer nametag.

    Returns ``(guild_bgr, info)`` where ``info`` contains:
      - ``guild_band``: (y0, y1) in the source image
      - ``name_band``: (y0, y1) in the source image
      - ``guild_dy``: pixels from source top to guild top (equals the
        name-row template height when the crop starts at the name). Used to
        convert a guild-match top-left back to an equivalent name-row
        top-left, and to derive
        ``guild_offset_y ≈ name_offset_y + guild_dy``.

    Returns ``(None, None)`` when no guild/family band is present.
    """
    bgr = as_bgr(image)
    if bgr is None or getattr(bgr, "size", 0) == 0:
        return None, None
    bands = parse_nametag_row_bands(bgr)
    guild = bands.get("guild")
    if not guild or guild[1] <= guild[0]:
        # Fall back: first secondary under the name (brown-or-not) when the
        # classifier stored it as medal-only (Artale / odd CMS crops).
        medal = bands.get("medal")
        name = bands.get("name") or (0, 0)
        if medal and medal[1] > medal[0] and medal[0] >= max(int(name[1]) - 2, 0):
            guild = medal
        else:
            return None, None
    y0, y1 = int(guild[0]), int(guild[1])
    y0 = max(0, y0)
    y1 = min(bgr.shape[0], max(y1, y0 + 1))
    crop = bgr[y0:y1].copy()
    name = bands.get("name") or (0, y0)
    info = {
        "guild_band": (y0, y1),
        "name_band": (int(name[0]), int(name[1])),
        "guild_dy": y0,
    }
    return crop, info


def derive_guild_offset(name_offset, guild_dy, configured=None):
    """Player-center offset from a **guild-row** match top-left.

    Name matching uses ``nametag.offset`` relative to the **name-row** top.
    The guild plate sits below the name, so the Y offset must be larger by
    approximately ``guild_dy`` (name-row height / guild top in the stack).

    ``configured`` may be a ``[dx, dy]`` override from config. When omitted,
    returns ``[name_offset_x, name_offset_y + guild_dy]``.
    """
    try:
        ox = float(name_offset[0]) if name_offset is not None else 0.0
        oy = float(name_offset[1]) if name_offset is not None else 30.0
    except (TypeError, ValueError, IndexError):
        ox, oy = 0.0, 30.0
    if configured is not None:
        try:
            return [float(configured[0]), float(configured[1])]
        except (TypeError, ValueError, IndexError):
            pass
    return [ox, oy + max(0, int(guild_dy))]


def prepare_nametag_template(image, keep_optional_rows=True, layers=None):
    """Crop a nametag screenshot to a stable matching template.

    Tight crops (width < 200 and height < 120) start from the full stack, then
    ``layers`` (1/2/3) may drop lower bands. Large screenshots are first cropped
    to the contiguous name(+guild)(+medal) stack, then the same layer trim.

    ``keep_optional_rows=False`` is treated as layers=1 (name-only) when
    ``layers`` is omitted — legacy CMS name-only path.
    """
    if image is None or image.size == 0:
        return image

    if layers is None and keep_optional_rows is False:
        layers = 1

    bgr = as_bgr(image)
    height, width = bgr.shape[:2]

    # Already a tight nametag asset — optionally trim to selected layers.
    if width < TIGHT_NAMETAG_MAX_WIDTH and height < TIGHT_NAMETAG_MAX_HEIGHT:
        if layers is not None:
            return crop_nametag_to_layers(image, layers)
        return image

    boxes = list(iter_plate_boxes(bgr))
    if not boxes:
        return image

    selected = _select_name_plate_box(boxes, width, height)
    if selected is None:
        return image

    pad = 1
    nx, ny, nw, nh, _ = selected
    stack = _collect_stack_boxes(selected, boxes)
    x0, y0, x1, y1 = _union_box_bounds(stack, pad, width, height)

    # Artale medal bars may lack a strong plate blob — grow downward only when
    # the band under the stack looks plate-like (cyan/brown), not terrain.
    ex0 = max(0, nx - pad)
    ey0 = max(0, ny - pad)
    ex1 = min(width, nx + nw + pad)
    ey1 = min(height, ny + nh + pad)
    scan_x0 = max(0, nx - 8)
    scan_x1 = min(width, nx + nw + 8)
    medal_scan = min(height, max(y1, ey1) + max(28, nh + 12))
    probe_y0 = max(y1, ey1)
    if medal_scan > probe_y0 and scan_x1 > scan_x0:
        probe = bgr[probe_y0:medal_scan, scan_x0:scan_x1]
        if plate_support(probe) >= 0.10:
            region = probe
            green = (
                (region[:, :, 0] <= 20)
                & (region[:, :, 1] >= 230)
                & (region[:, :, 2] <= 20)
            )
            content = ~green
            hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            content = content & ((hsv[:, :, 1] > 25) | (hsv[:, :, 2] < 200))
            # Prefer pixels that are actually on a plate mask.
            content = content & (plate_mask(region) > 0)
            if content.any():
                ys, xs = np.where(content)
                ey1 = min(height, probe_y0 + int(ys.max()) + 1 + pad)
                span = int(xs.max()) - int(xs.min()) + 1
                if span <= int(nw * 1.15) + 4:
                    ex0 = min(ex0, max(0, scan_x0 + int(xs.min()) - pad))
                    ex1 = max(ex1, min(width, scan_x0 + int(xs.max()) + 1 + pad))
    x0 = min(x0, ex0)
    y0 = min(y0, ey0)
    x1 = max(x1, ex1)
    y1 = max(y1, ey1)

    # keep_optional_rows=False historically meant CMS name-only; callers that
    # still pass False on a *large* screenshot get name plate only on chroma.
    if not keep_optional_rows:
        plate_roi = bgr[
            max(0, ny - pad) : min(height, ny + nh + pad),
            max(0, nx - pad) : min(width, nx + nw + pad),
        ]
        is_cms_brown = brown_plate_support(plate_roi) >= max(
            cyan_plate_support(plate_roi), 0.05
        )
        if is_cms_brown:
            name_crop = image[
                max(0, ny - pad) : min(height, ny + nh + pad),
                max(0, nx - pad) : min(width, nx + nw + pad),
            ]
            if name_crop.size == 0:
                return image
            # Name-only CMS path; layers>1 still limited to this name plate.
            if layers is not None:
                name_crop = crop_nametag_to_layers(name_crop, min(int(layers), 1) or 1)
            return _on_green_chroma(name_crop, pad=2)

    cropped = image[y0:y1, x0:x1]
    if cropped.size == 0:
        return image
    if layers is not None:
        cropped = crop_nametag_to_layers(cropped, layers)
    return cropped


def _clip_search_box(image, search_box):
    image_height, image_width = image.shape[:2]
    x0, y0, x1, y1 = search_box
    x0 = max(0, min(int(x0), image_width))
    y0 = max(0, min(int(y0), image_height))
    x1 = max(x0, min(int(x1), image_width))
    y1 = max(y0, min(int(y1), image_height))
    return x0, y0, x1, y1


def _scale_template(template, mask, scale_x, scale_y):
    if (round(scale_x, 4), round(scale_y, 4)) == (1.0, 1.0):
        return template, mask
    scaled_template = cv2.resize(
        template,
        None,
        fx=scale_x,
        fy=scale_y,
        interpolation=cv2.INTER_AREA,
    )
    scaled_mask = cv2.resize(
        mask,
        (scaled_template.shape[1], scaled_template.shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )
    return scaled_template, scaled_mask


def _parse_scale(scale):
    if isinstance(scale, (int, float)):
        return float(scale), float(scale)
    if len(scale) == 2:
        return float(scale[0]), float(scale[1])
    return None


def _masked_sqdiff_normed(roi, tmpl, mask):
    """Single-location masked TM_SQDIFF_NORMED (lower is better)."""
    if roi is None or tmpl is None or roi.size == 0 or tmpl.size == 0:
        return 1.0
    if roi.shape[:2] != tmpl.shape[:2]:
        return 1.0
    if mask is None:
        mask = np.full(tmpl.shape[:2], 255, dtype=np.uint8)
    if mask.shape[:2] != tmpl.shape[:2]:
        return 1.0
    weights = (mask > 0).astype(np.float32)
    weight_sum = float(weights.sum())
    if weight_sum < 1.0:
        return 1.0
    # Broadcast mask over channels.
    if roi.ndim == 3:
        w = weights[:, :, None]
        diff = (roi.astype(np.float32) - tmpl.astype(np.float32)) ** 2
        num = float((diff * w).sum())
        den = float(
            (
                (roi.astype(np.float32) ** 2 * w).sum()
                * (tmpl.astype(np.float32) ** 2 * w).sum()
            )
            ** 0.5
        )
    else:
        diff = (roi.astype(np.float32) - tmpl.astype(np.float32)) ** 2
        num = float((diff * weights).sum())
        den = float(
            (
                (roi.astype(np.float32) ** 2 * weights).sum()
                * (tmpl.astype(np.float32) ** 2 * weights).sum()
            )
            ** 0.5
        )
    if den <= 1e-6:
        return 1.0
    return float(np.clip(num / den, 0.0, 1.0))


def _band_score(image, template, mask, band, loc, scale_x, scale_y):
    """Masked SQDIFF for one vertical band at a full-template top-left ``loc``."""
    if not band:
        return 1.0
    y0, y1 = band
    if y1 <= y0:
        return 1.0
    band_tmpl = template[y0:y1]
    band_mask = mask[y0:y1]
    scaled_tmpl, scaled_mask = _scale_template(
        band_tmpl, band_mask, scale_x, scale_y
    )
    th, tw = scaled_tmpl.shape[:2]
    loc_x, loc_y = loc
    sy = loc_y + int(round(y0 * scale_y))
    roi = image[sy : sy + th, loc_x : loc_x + tw]
    return _masked_sqdiff_normed(roi, scaled_tmpl, scaled_mask)


def _secondary_bands(bands):
    """Yield (key, (y0, y1)) for guild/medal bands present on the template."""
    for key in ("guild", "medal"):
        band = bands.get(key)
        if band and band[1] > band[0]:
            yield key, band


def _hard_secondary_ok(image, template, mask, bands, loc, scale_x, scale_y):
    """Validate secondary bands under a hard multi-row candidate.

    Follows the imported template (一层/两层/三层), not a global 3-row lock:
    - 0 secondary (一层): always True — name-only matching.
    - 1 secondary (两层): that band must match.
    - 2+ secondaries (三层): **all** template secondary bands must match.
      Choosing 一层/两层 at import crops the PNG so this branch is not forced.
    """
    secondary = list(_secondary_bands(bands))
    if not secondary:
        return True
    require_all = len(secondary) >= 2
    ok_any = False
    for _key, band in secondary:
        score = _band_score(
            image, template, mask, band, loc, scale_x, scale_y
        )
        hit = score < SECONDARY_ROW_MATCH_THRES
        if require_all and not hit:
            return False
        if hit:
            ok_any = True
    return ok_any


def _name_band_ok(image, template, mask, bands, loc, scale_x, scale_y):
    """Name-row band must independently support a hard two-row hit."""
    name_band = bands.get("name")
    if not name_band or name_band[1] <= name_band[0]:
        return True
    score = _band_score(
        image, template, mask, name_band, loc, scale_x, scale_y
    )
    return score < NAME_BAND_MATCH_THRES


def find_best_nametag_match(
    image,
    template,
    mask,
    scales,
    search_box,
    require_plate=False,
    min_plate_support=0.18,
    top_k=8,
    search_plates=None,
):
    """Match a nametag at several scales inside a bounded region.

    **Hard two-row** (template has guild and/or medal band): the full stacked
    template (name + medal) is the primary match target. Candidates must also
    pass independent name-band and secondary-band checks so a lone name plate
    or pet tag cannot lock. Returned ``loc`` is the top-left of the **full**
    match (template top ≈ name-row top for prepared crops). Returned
    ``(height, width)`` is the scaled **full** template size so debug overlays
    enclose both rows. Player body offset should still use this top (name-row
    top) minus ``offset_y``.

    **Name-only** templates (no secondary band): legacy name-row primary match.

    Return tuple ``(loc, score, (height, width), (scale_x, scale_y))``.
    """
    if search_plates is None:
        search_plates = require_plate

    x0, y0, x1, y1 = _clip_search_box(image, search_box)
    search_image = image[y0:y1, x0:x1]
    if search_image.size == 0 or template is None or template.size == 0:
        return None

    if mask is None:
        mask = np.full(template.shape[:2], 255, dtype=np.uint8)

    bands = parse_nametag_row_bands(template)
    hard_two_row = any(True for _ in _secondary_bands(bands))

    if hard_two_row:
        # Primary target = FULL name+medal template. Prefer plate-anchored
        # search first so terrain/FX false peaks do not bury the real stack.
        best = None
        if search_plates:
            best = _match_near_plates(
                image,
                template,
                mask,
                bands,
                scales,
                (x0, y0, x1, y1),
                min_plate_support,
                hard_two_row=True,
            )
        dense = _match_template_candidates(
            image,
            search_image,
            template,
            mask,
            bands,
            scales,
            x0,
            y0,
            require_plate,
            min_plate_support,
            top_k if require_plate else 1,
            hard_two_row=True,
        )
        if dense is not None and (best is None or dense[4] < best[4]):
            best = dense
        if best is None:
            return None
        return best[0], best[1], best[2], best[3]

    # ---- Name-only template path (legacy) ----
    name_y0, name_y1 = bands["name"]
    if name_y1 <= name_y0:
        name_y0, name_y1 = 0, template.shape[0]

    name_template = template[name_y0:name_y1]
    name_mask = mask[name_y0:name_y1]
    name_y_offset = name_y0

    best = _match_template_candidates(
        image,
        search_image,
        name_template,
        name_mask,
        bands,
        scales,
        x0,
        y0,
        require_plate,
        min_plate_support,
        top_k if require_plate else 1,
        hard_two_row=False,
        full_template=template,
        full_mask=mask,
        name_y_offset=name_y_offset,
    )

    if search_plates:
        plate_match = _match_near_plates(
            image,
            name_template,
            name_mask,
            bands,
            scales,
            (x0, y0, x1, y1),
            min_plate_support,
            hard_two_row=False,
            full_template=template,
            full_mask=mask,
            name_y_offset=name_y_offset,
        )
        if plate_match is not None and (
            best is None or plate_match[4] < best[4]
        ):
            best = plate_match

    if best is None:
        return None
    return best[0], best[1], best[2], best[3]




def find_nametag_match_candidates(
    image,
    template,
    mask,
    scales,
    search_box,
    require_plate=False,
    min_plate_support=0.18,
    top_k=8,
    search_plates=None,
    max_keep=6,
):
    """Like ``find_best_nametag_match`` but return up to ``max_keep`` peaks.

    Each item is ``(loc, score, (height, width), (scale_x, scale_y))`` sorted
    by ascending score (SQDIFF). Used for ROI / second-peak ambiguity gates.
    """
    if search_plates is None:
        search_plates = require_plate

    x0, y0, x1, y1 = _clip_search_box(image, search_box)
    search_image = image[y0:y1, x0:x1]
    if search_image.size == 0 or template is None or template.size == 0:
        return []

    if mask is None:
        mask = np.full(template.shape[:2], 255, dtype=np.uint8)

    bands = parse_nametag_row_bands(template)
    hard_two_row = any(True for _ in _secondary_bands(bands))

    collected = []

    def _absorb(match):
        if match is None:
            return
        # match may be 5-tuple with ranked score from internal helpers
        loc, score, size, scale = match[0], match[1], match[2], match[3]
        ranked = float(match[4]) if len(match) > 4 else float(score)
        for prev in collected:
            if _peak_distance(prev[0], loc) < max(size[1] // 2, 20):
                if ranked < prev[4]:
                    prev[:] = [loc, float(score), size, scale, ranked]
                return
        collected.append([loc, float(score), size, scale, ranked])

    if hard_two_row:
        if search_plates:
            _absorb(
                _match_near_plates(
                    image,
                    template,
                    mask,
                    bands,
                    scales,
                    (x0, y0, x1, y1),
                    min_plate_support,
                    hard_two_row=True,
                )
            )
        # Pull multiple dense peaks
        for cand in _match_template_candidate_list(
            image,
            search_image,
            template,
            mask,
            bands,
            scales,
            x0,
            y0,
            require_plate,
            min_plate_support,
            max(top_k, max_keep),
            hard_two_row=True,
        ):
            _absorb(cand)
    else:
        name_y0, name_y1 = bands["name"]
        if name_y1 <= name_y0:
            name_y0, name_y1 = 0, template.shape[0]
        name_template = template[name_y0:name_y1]
        name_mask = mask[name_y0:name_y1]
        name_y_offset = name_y0
        for cand in _match_template_candidate_list(
            image,
            search_image,
            name_template,
            name_mask,
            bands,
            scales,
            x0,
            y0,
            require_plate,
            min_plate_support,
            max(top_k, max_keep),
            hard_two_row=False,
            full_template=template,
            full_mask=mask,
            name_y_offset=name_y_offset,
        ):
            _absorb(cand)
        if search_plates:
            _absorb(
                _match_near_plates(
                    image,
                    name_template,
                    name_mask,
                    bands,
                    scales,
                    (x0, y0, x1, y1),
                    min_plate_support,
                    hard_two_row=False,
                    full_template=template,
                    full_mask=mask,
                    name_y_offset=name_y_offset,
                )
            )

    collected.sort(key=lambda item: item[4])
    out = []
    for item in collected[: max(1, int(max_keep))]:
        out.append((item[0], item[1], item[2], item[3]))
    return out


def _match_template_candidate_list(
    image,
    search_image,
    match_template,
    match_mask,
    bands,
    scales,
    x0,
    y0,
    require_plate,
    min_plate_support,
    candidate_limit,
    hard_two_row=False,
    full_template=None,
    full_mask=None,
    name_y_offset=0,
):
    """Slide ``match_template`` and return up to ``candidate_limit`` valid hits.

    Each hit is ``(loc, score, (h, w), (sx, sy), ranked)`` sorted by ranked.
    """
    if full_template is None:
        full_template = match_template
    if full_mask is None:
        full_mask = match_mask

    hits = []
    seen_scales = set()
    for scale in scales:
        parsed = _parse_scale(scale)
        if parsed is None:
            continue
        scale_x, scale_y = parsed
        if scale_x <= 0 or scale_y <= 0:
            continue
        scale_key = (round(scale_x, 4), round(scale_y, 4))
        if scale_key in seen_scales:
            continue
        seen_scales.add(scale_key)

        scaled_template, scaled_mask = _scale_template(
            match_template, match_mask, scale_x, scale_y
        )
        template_height, template_width = scaled_template.shape[:2]
        if (
            search_image.shape[0] < template_height
            or search_image.shape[1] < template_width
        ):
            continue

        result = cv2.matchTemplate(
            search_image,
            scaled_template,
            cv2.TM_SQDIFF_NORMED,
            mask=scaled_mask,
        )
        result = np.nan_to_num(result, nan=1.0, posinf=1.0, neginf=1.0)
        work = result.copy()
        suppress = max(template_width // 2, 12)
        max_probes = max(candidate_limit * 8, 40)
        valid_seen = 0
        for _ in range(max_probes):
            if valid_seen >= candidate_limit:
                break
            score, _, location, _ = cv2.minMaxLoc(work)
            if score >= 0.55:
                break
            match_loc = (x0 + int(location[0]), y0 + int(location[1]))
            if hard_two_row:
                loc = match_loc
                report_size = (template_height, template_width)
                plate_roi = image[
                    loc[1] : loc[1] + template_height,
                    loc[0] : loc[0] + template_width,
                ]
                name_band = bands.get("name")
                if name_band and name_band[1] > name_band[0]:
                    ny0 = int(round(name_band[0] * scale_y))
                    ny1 = int(round(name_band[1] * scale_y))
                    name_roi = image[
                        loc[1] + ny0 : loc[1] + ny1,
                        loc[0] : loc[0] + template_width,
                    ]
                    if name_roi.size:
                        plate_roi = name_roi
                plate_min = max(min_plate_support, 0.16)
                valid = (not require_plate) or plate_support(plate_roi) >= plate_min
                if valid:
                    valid = _name_band_ok(
                        image,
                        full_template,
                        full_mask,
                        bands,
                        loc,
                        scale_x,
                        scale_y,
                    ) and _hard_secondary_ok(
                        image,
                        full_template,
                        full_mask,
                        bands,
                        loc,
                        scale_x,
                        scale_y,
                    )
                if valid:
                    medal_s = 1.0
                    for _k, band in _secondary_bands(bands):
                        medal_s = min(
                            medal_s,
                            _band_score(
                                image,
                                full_template,
                                full_mask,
                                band,
                                loc,
                                scale_x,
                                scale_y,
                            ),
                        )
                    ranked = 0.55 * float(score) + 0.45 * float(medal_s)
                else:
                    ranked = float(score)
            else:
                loc = (
                    match_loc[0],
                    match_loc[1] - int(round(name_y_offset * scale_y)),
                )
                report_size = (template_height, template_width)
                roi = image[
                    match_loc[1] : match_loc[1] + template_height,
                    match_loc[0] : match_loc[0] + template_width,
                ]
                valid = (not require_plate) or plate_support(roi) >= min_plate_support
                ranked = float(score)

            if valid:
                valid_seen += 1
                hits.append(
                    (
                        loc,
                        float(score),
                        report_size,
                        (scale_x, scale_y),
                        ranked,
                    )
                )
            ly, lx = int(location[1]), int(location[0])
            work[
                max(0, ly - suppress) : ly + suppress,
                max(0, lx - suppress) : lx + suppress,
            ] = 1.0
    hits.sort(key=lambda item: item[4])
    return hits[: max(1, int(candidate_limit))]


def _match_template_candidates(
    image,
    search_image,
    match_template,
    match_mask,
    bands,
    scales,
    x0,
    y0,
    require_plate,
    min_plate_support,
    candidate_limit,
    hard_two_row=False,
    full_template=None,
    full_mask=None,
    name_y_offset=0,
):
    """Slide ``match_template`` over ``search_image`` and pick the best hit."""
    hits = _match_template_candidate_list(
        image,
        search_image,
        match_template,
        match_mask,
        bands,
        scales,
        x0,
        y0,
        require_plate,
        min_plate_support,
        candidate_limit,
        hard_two_row=hard_two_row,
        full_template=full_template,
        full_mask=full_mask,
        name_y_offset=name_y_offset,
    )
    return hits[0] if hits else None


def _match_near_plates(
    image,
    match_template,
    match_mask,
    bands,
    scales,
    search_box,
    min_plate_support,
    hard_two_row=False,
    full_template=None,
    full_mask=None,
    name_y_offset=0,
):
    x0, y0, x1, y1 = search_box
    region = image[y0:y1, x0:x1]
    if region.size == 0:
        return None

    if full_template is None:
        full_template = match_template
    if full_mask is None:
        full_mask = match_mask

    best = None
    # When hard two-row, scan around plates but allow room for the medal below.
    base_h = match_template.shape[0]
    base_w = match_template.shape[1]
    margin = max(int(base_w * 0.35), 10)
    below_pad = int(base_h * 0.85) if hard_two_row else 0
    for px, py, width, height, _area in iter_plate_boxes(region):
        box = (
            x0 + px - margin,
            y0 + py - margin,
            x0 + px + width + margin,
            y0 + py + height + margin + below_pad,
        )
        clipped = _clip_search_box(image, box)
        search_image = image[clipped[1] : clipped[3], clipped[0] : clipped[2]]
        match = _match_template_candidates(
            image,
            search_image,
            match_template,
            match_mask,
            bands,
            scales,
            clipped[0],
            clipped[1],
            True,
            min_plate_support,
            4,
            hard_two_row=hard_two_row,
            full_template=full_template,
            full_mask=full_mask,
            name_y_offset=name_y_offset,
        )
        if match is not None and (best is None or match[4] < best[4]):
            best = match
    return best
