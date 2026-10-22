"""Display-only overlays for ropes.yaml / patrol.yaml on map.png.

Does not mutate storage files. Coordinates for rope start/end are minimap
pixel positions (same space as live player detection). Patrol range is a
pair of width ratios in [0, 1].
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from src.utils.image_io import read_image
from src.utils.paths import minimap_dir

# BGR colors
_COLOR_UP = (80, 200, 80)       # green-ish: climb up
_COLOR_DOWN = (80, 160, 255)    # orange: climb down
_COLOR_SELECTED = (255, 210, 60)
_COLOR_BOUNDS = (90, 200, 255)
_COLOR_BAND = (60, 140, 80)
_BACKGROUND = np.array((20, 24, 32), dtype=np.uint8)


def map_png_path(map_name: str) -> str:
    return os.path.join(minimap_dir(map_name), "map.png")


def load_map_bgr(map_name: str) -> Optional[np.ndarray]:
    """Load assets/minimaps/<map>/map.png as BGR, or None if missing."""
    path = map_png_path(map_name)
    if not os.path.isfile(path):
        return None
    return read_image(path, cv2.IMREAD_COLOR)


def _upsample(image: np.ndarray, scale: int) -> np.ndarray:
    zoom = max(1, int(round(float(scale))))
    if zoom == 1:
        return image.copy()
    h, w = image.shape[:2]
    return cv2.resize(
        image,
        (max(1, w * zoom), max(1, h * zoom)),
        interpolation=cv2.INTER_LANCZOS4,
    )


def _tone_map(canvas: np.ndarray) -> np.ndarray:
    empty = np.max(canvas, axis=2) < 10
    canvas = canvas.copy()
    canvas[empty] = _BACKGROUND
    return cv2.convertScaleAbs(canvas, alpha=1.08, beta=2)


def _scale_point(
    pt: Sequence[float],
    scale_x: float,
    scale_y: float,
    zoom: int,
) -> Tuple[int, int]:
    return (
        int(round(float(pt[0]) * scale_x * zoom)),
        int(round(float(pt[1]) * scale_y * zoom)),
    )


def _edge_color(direction: str, selected: bool = False) -> Tuple[int, int, int]:
    if selected:
        return _COLOR_SELECTED
    return _COLOR_UP if str(direction).lower() == "up" else _COLOR_DOWN


def _draw_arrow(
    image: np.ndarray,
    start: Tuple[int, int],
    end: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = 2,
) -> None:
    cv2.arrowedLine(
        image,
        start,
        end,
        color,
        thickness,
        cv2.LINE_AA,
        tipLength=0.25,
    )
    cv2.circle(image, start, max(4, thickness + 2), (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(image, start, max(3, thickness + 1), color, -1, cv2.LINE_AA)
    cv2.circle(image, end, max(4, thickness + 2), (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(image, end, max(3, thickness + 1), color, -1, cv2.LINE_AA)


def _coord_scales(
    map_shape: Tuple[int, ...],
    coord_size: Optional[Sequence[float]] = None,
) -> Tuple[float, float]:
    """Map recorded minimap coords onto map.png when sizes differ.

    If ``coord_size`` is omitted, assume 1:1 with map.png (normal case).
    """
    h, w = map_shape[:2]
    if not coord_size or len(coord_size) < 2:
        return 1.0, 1.0
    try:
        cw, ch = float(coord_size[0]), float(coord_size[1])
    except (TypeError, ValueError):
        return 1.0, 1.0
    if cw <= 0 or ch <= 0:
        return 1.0, 1.0
    return w / cw, h / ch


def render_ropes_overlay(
    map_bgr: Optional[np.ndarray],
    edges: Sequence[Dict[str, Any]],
    *,
    scale: int = 6,
    selected_id: Optional[str] = None,
    coord_size: Optional[Sequence[float]] = None,
    show_legend: bool = True,
) -> np.ndarray:
    """Return an upscaled BGR preview of map.png with rope edges drawn."""
    if map_bgr is None:
        canvas = np.full((160, 240, 3), 32, dtype=np.uint8)
        cv2.putText(
            canvas,
            "No map.png",
            (40, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (180, 180, 180),
            2,
            cv2.LINE_AA,
        )
        return canvas

    base = np.asarray(map_bgr)
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    base = base[:, :, :3].astype(np.uint8, copy=False)
    zoom = max(1, int(round(float(scale))))
    sx, sy = _coord_scales(base.shape, coord_size)
    canvas = _tone_map(_upsample(base, zoom))

    for edge in edges or []:
        start = edge.get("start")
        end = edge.get("end")
        if start is None or end is None:
            continue
        try:
            p0 = _scale_point(start, sx, sy, zoom)
            p1 = _scale_point(end, sx, sy, zoom)
        except (TypeError, ValueError, IndexError):
            continue
        edge_id = str(edge.get("id") or "")
        selected = bool(selected_id) and edge_id == str(selected_id)
        color = _edge_color(str(edge.get("direction") or "up"), selected=selected)
        thickness = 3 if selected else 2
        _draw_arrow(canvas, p0, p1, color, thickness=thickness)
        label = edge_id.replace("rope_", "")
        if label:
            mid = ((p0[0] + p1[0]) // 2 + 6, (p0[1] + p1[1]) // 2 - 6)
            cv2.putText(
                canvas,
                label,
                mid,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (245, 248, 255),
                1,
                cv2.LINE_AA,
            )

    if show_legend:
        footer = np.full((28, canvas.shape[1], 3), (13, 17, 24), dtype=np.uint8)
        cv2.circle(footer, (14, 14), 5, _COLOR_UP, -1, cv2.LINE_AA)
        cv2.putText(footer, "UP", (24, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (215, 224, 236), 1, cv2.LINE_AA)
        cv2.circle(footer, (70, 14), 5, _COLOR_DOWN, -1, cv2.LINE_AA)
        cv2.putText(footer, "DOWN", (80, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (215, 224, 236), 1, cv2.LINE_AA)
        n = len(list(edges or []))
        cv2.putText(
            footer,
            f"{n} rope(s)",
            (max(12, footer.shape[1] - 100), 19),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (118, 226, 255),
            1,
            cv2.LINE_AA,
        )
        canvas = np.vstack((canvas, footer))

    return np.ascontiguousarray(canvas)



def ratio_to_x(ratio: float, width: int) -> int:
    """Pixel x for a 0..1 ratio.

    Must match runtime smart_patrol / F6/F7: ratio = player_x / minimap_w,
    so display x = round(ratio * width), clamped to [0, width - 1].
    (Do NOT use width-1 here — that skews the right edge vs left.)
    """
    w = max(1, int(width))
    r = max(0.0, min(1.0, float(ratio)))
    return min(w - 1, max(0, int(round(r * w))))


def x_to_ratio(x: float, width: int) -> float:
    """Inverse of ratio_to_x / runtime: player_x / minimap_w."""
    w = max(1, int(width))
    try:
        v = float(x) / float(w)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def clamp_range(left: float, right: float, min_gap: float = 0.02) -> tuple:
    """Clamp left < right with a minimum gap (no silent swap)."""
    gap = max(0.005, float(min_gap))
    left = max(0.0, min(1.0, float(left)))
    right = max(0.0, min(1.0, float(right)))
    if right - left >= gap:
        return left, right
    # Expand toward center while respecting [0, 1]
    need = gap - (right - left)
    left = max(0.0, left - need * 0.5)
    right = left + gap
    if right > 1.0:
        right = 1.0
        left = max(0.0, right - gap)
    return left, right


def render_map_base(
    map_bgr: Optional[np.ndarray],
    *,
    scale: int = 6,
    preferred_y: Optional[float] = None,
) -> np.ndarray:
    """Upscaled tone-mapped map without bound lines (for interactive preview)."""
    if map_bgr is None:
        canvas = np.full((160, 240, 3), 32, dtype=np.uint8)
        cv2.putText(
            canvas,
            "No map.png",
            (40, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (180, 180, 180),
            2,
            cv2.LINE_AA,
        )
        return canvas
    base = np.asarray(map_bgr)
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    base = base[:, :, :3].astype(np.uint8, copy=False)
    zoom = max(1, int(round(float(scale))))
    canvas = _tone_map(_upsample(base, zoom))
    h, w = canvas.shape[:2]
    if preferred_y is not None:
        try:
            py = int(round(float(preferred_y) * zoom))
            if 0 <= py < h:
                cv2.line(canvas, (0, py), (w - 1, py), (200, 120, 255), 1, cv2.LINE_AA)
        except (TypeError, ValueError):
            pass
    return np.ascontiguousarray(canvas)


def render_bounds_overlay(
    map_bgr: Optional[np.ndarray],
    left_ratio: float,
    right_ratio: float,
    *,
    scale: int = 4,
    preferred_y: Optional[float] = None,
    show_legend: bool = True,
) -> np.ndarray:
    """Return an upscaled BGR preview with left/right patrol band."""
    if map_bgr is None:
        canvas = np.full((160, 240, 3), 32, dtype=np.uint8)
        cv2.putText(
            canvas,
            "No map.png",
            (40, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (180, 180, 180),
            2,
            cv2.LINE_AA,
        )
        return canvas

    base = np.asarray(map_bgr)
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    base = base[:, :, :3].astype(np.uint8, copy=False)
    zoom = max(1, int(round(float(scale))))
    canvas = _tone_map(_upsample(base, zoom))
    h, w = canvas.shape[:2]

    left = max(0.0, min(1.0, float(left_ratio)))
    right = max(0.0, min(1.0, float(right_ratio)))
    if left > right:
        left, right = right, left
    x0 = ratio_to_x(left, w)
    x1 = ratio_to_x(right, w)

    # Soft shaded patrol band
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x0, 0), (x1, h - 1), _COLOR_BAND, -1)
    canvas = cv2.addWeighted(overlay, 0.28, canvas, 0.72, 0)

    cv2.line(canvas, (x0, 0), (x0, h - 1), _COLOR_BOUNDS, 2, cv2.LINE_AA)
    cv2.line(canvas, (x1, 0), (x1, h - 1), _COLOR_BOUNDS, 2, cv2.LINE_AA)
    cv2.putText(canvas, "L", (max(2, x0 + 4), 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _COLOR_BOUNDS, 1, cv2.LINE_AA)
    cv2.putText(canvas, "R", (min(w - 16, x1 + 4), 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _COLOR_BOUNDS, 1, cv2.LINE_AA)

    if preferred_y is not None:
        try:
            py = int(round(float(preferred_y) * zoom))
            if 0 <= py < h:
                cv2.line(canvas, (0, py), (w - 1, py), (200, 120, 255), 1, cv2.LINE_AA)
                cv2.putText(
                    canvas,
                    "pref_y",
                    (4, max(14, py - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (200, 120, 255),
                    1,
                    cv2.LINE_AA,
                )
        except (TypeError, ValueError):
            pass

    if show_legend:
        footer = np.full((28, canvas.shape[1], 3), (13, 17, 24), dtype=np.uint8)
        text = f"range [{left:.2f}, {right:.2f}]"
        cv2.putText(footer, text, (12, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (118, 226, 255), 1, cv2.LINE_AA)
        canvas = np.vstack((canvas, footer))

    return np.ascontiguousarray(canvas)


def bgr_to_qimage_bytes(image: np.ndarray):
    """Return (contiguous BGR uint8 array) suitable for QImage.Format_BGR888."""
    if image is None:
        return None
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] < 3:
        return None
    return np.ascontiguousarray(arr[:, :, :3].astype(np.uint8))
