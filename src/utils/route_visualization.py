"""Display-only rendering for route maps.

The navigation engine relies on exact RGB pixels in ``route*.png``.  This
module never mutates or saves those images; it builds a separate, polished
BGR preview for the UI.
"""

from __future__ import annotations

import cv2
import numpy as np


_BACKGROUND = np.array((20, 24, 32), dtype=np.uint8)


def _normalise_color_actions(color_actions):
    actions = {}
    for color, command in (color_actions or {}).items():
        if isinstance(color, str):
            try:
                color = tuple(int(value.strip()) for value in color.split(","))
            except (TypeError, ValueError):
                continue
        try:
            rgb = tuple(int(value) for value in color)
        except (TypeError, ValueError):
            continue
        if len(rgb) == 3 and all(0 <= value <= 255 for value in rgb):
            actions[rgb] = str(command)
    return actions


def _fit_to_canvas(image, height, width):
    if image is None:
        return np.zeros((height, width, 3), dtype=np.uint8)
    image = np.asarray(image)
    if image.ndim == 2:
        image = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("Route preview images must have 1 or 3 color channels")
    image = image[:, :, :3].astype(np.uint8, copy=False)
    if image.shape[:2] == (height, width):
        return image.copy()
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    copy_height = min(height, image.shape[0])
    copy_width = min(width, image.shape[1])
    canvas[:copy_height, :copy_width] = image[:copy_height, :copy_width]
    return canvas


def _content_bounds(base, combined_route_mask, padding):
    # Treat very dark pixels as empty canvas. Route masks are included so an
    # isolated action marker is never cropped away.
    content = np.max(base, axis=2) > 12
    if combined_route_mask is not None:
        content |= combined_route_mask > 0
    points = cv2.findNonZero(content.astype(np.uint8))
    if points is None:
        return 0, 0, base.shape[1], base.shape[0]
    x, y, width, height = cv2.boundingRect(points)
    return (
        max(0, x - padding),
        max(0, y - padding),
        min(base.shape[1], x + width + padding),
        min(base.shape[0], y + height + padding),
    )


def _alpha_color(image, mask, color, opacity=0.9):
    alpha = (mask.astype(np.float32) / 255.0 * opacity)[:, :, None]
    color_layer = np.empty_like(image)
    color_layer[:] = color
    return np.clip(
        image.astype(np.float32) * (1.0 - alpha)
        + color_layer.astype(np.float32) * alpha,
        0,
        255,
    ).astype(np.uint8)


def _command_badge(command):
    words = command.lower().split()
    if "goal" in words:
        return "GOAL"
    if "teleport" in words:
        return "T"
    if "jump" in words:
        return "J"
    if words and all(word == "stop" for word in words):
        return "S"
    if len(words) > 1 and words[0] == "none" and words[1] == "up":
        return "U"
    if len(words) > 1 and words[0] == "none" and words[1] == "down":
        return "D"
    return ""


def _draw_badge(image, center, label, color):
    x, y = center
    radius = 11 if label != "GOAL" else 17
    cv2.circle(image, (x, y), radius + 2, (245, 248, 255), -1, cv2.LINE_AA)
    cv2.circle(image, (x, y), radius, color, -1, cv2.LINE_AA)
    font_scale = 0.32 if label == "GOAL" else 0.43
    thickness = 1
    (width, height), _ = cv2.getTextSize(
        label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
    )
    cv2.putText(
        image,
        label,
        (x - width // 2, y + height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def _draw_direction_arrow(image, center, command):
    horizontal = command.lower().split()[0] if command else ""
    if horizontal not in ("left", "right"):
        return
    x, y = center
    dx = 10 if horizontal == "right" else -10
    cv2.arrowedLine(
        image,
        (x - dx, y),
        (x + dx, y),
        (255, 255, 255),
        2,
        cv2.LINE_AA,
        tipLength=0.42,
    )


def _legend_entries(actions):
    entries = []
    seen = set()
    for rgb, command in actions.items():
        words = command.lower().split()
        if "goal" in words:
            label = "GOAL"
        elif "teleport" in words:
            label = "TELE"
        elif "jump" in words:
            label = "JUMP"
        elif words and words[0] in ("left", "right"):
            label = words[0].upper()
        else:
            continue
        if label in seen:
            continue
        seen.add(label)
        entries.append(((rgb[2], rgb[1], rgb[0]), label))
    return entries[:6]


def render_route_visualization(
    base_bgr,
    route_bgr=None,
    color_actions=None,
    *,
    player_position=None,
    viewport=None,
    current_command=None,
    scale=4,
    crop=True,
    show_legend=True,
):
    """Return a polished BGR route preview without changing the source arrays.

    ``color_actions`` accepts either RGB tuple keys or ``"R,G,B"`` keys.
    Coordinates for ``player_position`` and ``viewport`` are expressed in the
    original map coordinate system.
    """
    if base_bgr is None and route_bgr is None:
        return np.zeros((120, 180, 3), dtype=np.uint8)

    reference = base_bgr if base_bgr is not None else route_bgr
    reference = np.asarray(reference)
    if reference.ndim < 2 or reference.shape[0] == 0 or reference.shape[1] == 0:
        return np.zeros((120, 180, 3), dtype=np.uint8)
    height, width = reference.shape[:2]
    base = _fit_to_canvas(base_bgr, height, width)
    route = _fit_to_canvas(route_bgr, height, width)
    actions = _normalise_color_actions(color_actions)

    masks = []
    combined_mask = np.zeros((height, width), dtype=np.uint8)
    route_delta = np.any(route != base, axis=2)
    for rgb, command in actions.items():
        bgr = np.array((rgb[2], rgb[1], rgb[0]), dtype=np.uint8)
        # Native minimap art can coincidentally contain a route-code color.
        # A recorded route pixel must therefore both match the code and differ
        # from the same pixel in map.png.
        mask = (np.all(route == bgr, axis=2) & route_delta).astype(np.uint8) * 255
        if np.any(mask):
            masks.append((rgb, command, mask))
            combined_mask = cv2.bitwise_or(combined_mask, mask)

    if crop:
        x0, y0, x1, y1 = _content_bounds(base, combined_mask, padding=5)
    else:
        x0, y0, x1, y1 = 0, 0, width, height

    base_crop = base[y0:y1, x0:x1]
    zoom = max(1, int(round(float(scale))))
    output_size = (max(1, base_crop.shape[1] * zoom), max(1, base_crop.shape[0] * zoom))
    canvas = cv2.resize(base_crop, output_size, interpolation=cv2.INTER_LANCZOS4)

    # Give empty map space a subtle blue-black tone while retaining the native
    # minimap pixels and contrast.
    empty = np.max(canvas, axis=2) < 10
    canvas[empty] = _BACKGROUND
    canvas = cv2.convertScaleAbs(canvas, alpha=1.08, beta=2)

    scaled_masks = []
    kernel_size = max(3, zoom + (1 - zoom % 2))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    for rgb, command, mask in masks:
        mask_crop = mask[y0:y1, x0:x1]
        scaled = cv2.resize(mask_crop, output_size, interpolation=cv2.INTER_NEAREST)
        thick = cv2.dilate(scaled, kernel, iterations=1)
        soft = cv2.GaussianBlur(thick, (0, 0), sigmaX=max(0.8, zoom * 0.35))
        color = (rgb[2], rgb[1], rgb[0])
        canvas = _alpha_color(canvas, soft, color, opacity=0.92)
        # Crisp center preserves the route's shape without jagged enlarged pixels.
        core = cv2.GaussianBlur(scaled, (0, 0), sigmaX=0.7)
        canvas = _alpha_color(canvas, core, color, opacity=1.0)
        scaled_masks.append((command, scaled, color, mask_crop))

    # Add sparse command markers. Ordinary movement gets one arrow per sizeable
    # connected segment; special actions receive labelled badges.
    marker_count = 0
    for command, _scaled, color, raw_mask in scaled_masks:
        count, _labels, stats, centroids = cv2.connectedComponentsWithStats(raw_mask, 8)
        badge = _command_badge(command)
        for component in range(1, count):
            area = stats[component, cv2.CC_STAT_AREA]
            if area <= 0 or marker_count >= 48:
                continue
            cx, cy = centroids[component]
            center = (int(round(cx * zoom)), int(round(cy * zoom)))
            if badge:
                _draw_badge(canvas, center, badge, color)
                marker_count += 1
            elif area >= 4:
                _draw_direction_arrow(canvas, center, command)
                marker_count += 1

    def transform(point):
        return (
            int(round((point[0] - x0) * zoom)),
            int(round((point[1] - y0) * zoom)),
        )

    if viewport is not None and len(viewport) == 4:
        vx, vy, vw, vh = viewport
        top_left = transform((vx, vy))
        bottom_right = transform((vx + vw, vy + vh))
        cv2.rectangle(canvas, top_left, bottom_right, (72, 214, 255), 2, cv2.LINE_AA)

    if player_position is not None and len(player_position) == 2:
        px, py = transform(player_position)
        if -12 <= px < canvas.shape[1] + 12 and -12 <= py < canvas.shape[0] + 12:
            cv2.circle(canvas, (px, py), 9, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, (px, py), 6, (35, 196, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, (px, py), 2, (20, 24, 32), -1, cv2.LINE_AA)

    entries = _legend_entries(actions) if show_legend and masks else []
    if entries or current_command:
        footer_height = 58 if entries and current_command else 34
        footer = np.full((footer_height, canvas.shape[1], 3), (13, 17, 24), dtype=np.uint8)
        x = 12
        for color, label in entries:
            cv2.circle(footer, (x + 5, 17), 5, color, -1, cv2.LINE_AA)
            cv2.putText(
                footer, label, (x + 15, 22), cv2.FONT_HERSHEY_SIMPLEX,
                0.42, (215, 224, 236), 1, cv2.LINE_AA,
            )
            x += 25 + cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0][0]
            if x > footer.shape[1] - 90:
                break
        if current_command:
            command_text = f"CMD  {current_command}"
            (text_width, _), _ = cv2.getTextSize(
                command_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1
            )
            cv2.putText(
                footer,
                command_text,
                (
                    12 if entries else max(12, footer.shape[1] - text_width - 12),
                    48 if entries else 22,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (118, 226, 255),
                1,
                cv2.LINE_AA,
            )
        canvas = np.vstack((canvas, footer))

    return np.ascontiguousarray(canvas)
