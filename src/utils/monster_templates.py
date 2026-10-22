"""Monster sprite loading helpers."""

import os

import cv2
import numpy as np

from src.utils.image_io import read_image


def select_monster_template_files(
    files,
    prefixes=None,
    max_files=6,
    per_prefix=None,
):
    """Pick living-pose sprites, capped per prefix then overall.

    Original balance: stand + move, 3 files each (6 total). A naive
    ``files[:6]`` after sorting stand-first would keep 6 stand poses and
    drop every walk frame.
    """
    files = [path for path in files if path]
    prefixes = [str(prefix).lower() for prefix in (prefixes or []) if str(prefix).strip()]
    try:
        max_files = int(max_files or 0)
    except (TypeError, ValueError):
        max_files = 0
    try:
        per_prefix = None if per_prefix is None else int(per_prefix)
    except (TypeError, ValueError):
        per_prefix = None

    if prefixes:
        grouped = {prefix: [] for prefix in prefixes}
        for path in files:
            base = os.path.basename(path).lower()
            matched = next(
                (prefix for prefix in prefixes if base.startswith(prefix)),
                None,
            )
            if matched is not None:
                grouped[matched].append(path)
        if per_prefix is None and max_files > 0:
            per_prefix = max(1, max_files // len(prefixes))
        selected = []
        for prefix in prefixes:
            bucket = sorted(grouped[prefix])
            if per_prefix and per_prefix > 0:
                bucket = bucket[:per_prefix]
            selected.extend(bucket)
        if max_files > 0:
            selected = selected[:max_files]
        return selected

    files = sorted(files)
    if max_files > 0:
        files = files[:max_files]
    return files


def load_monster_template(path, alpha_threshold=32):
    """Load a monster sprite and derive a mask from RGBA or green screen.

    Official monster assets are RGBA PNG files. Transparent pixels must not
    participate in template matching, otherwise discarded background RGB
    values become part of the monster template. Legacy green-screen assets
    remain supported as a fallback.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")

    image = read_image(path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Failed to load image: {path}")

    alpha_threshold = max(1, min(255, int(alpha_threshold)))
    if image.ndim == 3 and image.shape[2] == 4:
        img_bgr = image[:, :, :3]
        alpha = image[:, :, 3]
        mask = np.where(alpha >= alpha_threshold, 255, 0).astype(np.uint8)
    else:
        if image.ndim == 2:
            img_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            img_bgr = image[:, :, :3]
        green_background = np.all(img_bgr == (0, 255, 0), axis=2)
        mask = np.where(green_background, 0, 255).astype(np.uint8)

    visible_pixels = cv2.findNonZero(mask)
    if visible_pixels is None:
        raise ValueError(f"Monster image has no visible pixels: {path}")

    x, y, width, height = cv2.boundingRect(visible_pixels)
    return (
        img_bgr[y:y + height, x:x + width],
        mask[y:y + height, x:x + width],
    )
