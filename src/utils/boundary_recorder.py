"""Boundary / cliff-range capture for smart_patrol patrol.yaml.

Hotkeys when KeyBoardListener is attached:
  F6  Capture LEFT safe edge (range[0] = player_x / minimap_w)
  F7  Sample RIGHT safe edge (range[1]) in memory only — UI 「保存边界」 writes disk
  F9  Quit session
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2

from src.utils.common import (
    get_minimap_loc_size,
    get_player_location_on_minimap,
    is_mac,
    is_img_16_to_9,
)
from src.utils.global_var import WINDOW_WORKING_SIZE
from src.utils.logger import logger
from src.utils.paths import MINIMAPS
from src.utils.patrol import load_patrol, patrol_path
from src.utils.map_overlay import x_to_ratio
from src.utils.rope_recorder import load_recorder_cfg, cfg_name_from_path
from src.input.KeyBoardListener import KeyBoardListener

if is_mac():
    from src.input.GameWindowCapturorForMac import GameWindowCapturor
else:
    from src.input.GameWindowCapturor import GameWindowCapturor


def player_x_ratio(loc_player_minimap, minimap_w: int) -> Optional[float]:
    """Return player x as 0–1 ratio of minimap width (same as smart_patrol)."""
    if loc_player_minimap is None or not minimap_w:
        return None
    try:
        x = float(loc_player_minimap[0])
    except (TypeError, IndexError, ValueError):
        return None
    return x_to_ratio(x, int(minimap_w))


def normalize_range(left: float, right: float) -> List[float]:
    left = max(0.0, min(1.0, float(left)))
    right = max(0.0, min(1.0, float(right)))
    if left > right:
        left, right = right, left
    return [left, right]


class BoundaryRecorder:
    """Capture live minimap player x ratios into patrol.yaml range."""

    def __init__(self, map_name: str, cfg: dict, register_hotkeys: bool = True):
        self.map_name = map_name
        self.cfg = cfg
        self.capture = GameWindowCapturor(cfg)
        self.kb = KeyBoardListener(cfg=cfg, is_autobot=False)
        if register_hotkeys:
            self.kb.register_func_key_handler("f6", self.capture_left)
            self.kb.register_func_key_handler("f7", self.capture_right)
            self.kb.register_func_key_handler("f9", self.request_stop)

        self.is_terminated = False
        self.loc_minimap = (0, 0)
        self.img_minimap = None
        self.minimap_w = 0
        self.loc_player_minimap = None
        self.img_frame_debug = None
        self.last_status = "Ready — stand LEFT edge F6, RIGHT edge F7"
        self.fps_limit = 20
        self.left_ratio: Optional[float] = None
        self.right_ratio: Optional[float] = None
        self.last_saved_range: Optional[List[float]] = None
        # seed from existing patrol.yaml
        doc = load_patrol(map_name)
        rng = doc.get("range") or [0.15, 0.85]
        self.left_ratio = float(rng[0])
        self.right_ratio = float(rng[1])

        os.makedirs(os.path.join(MINIMAPS, map_name), exist_ok=True)
        logger.info(
            "[BoundaryRecorder] map=%s path=%s current range=%s"
            % (map_name, patrol_path(map_name), [self.left_ratio, self.right_ratio])
        )

    def request_stop(self):
        self.is_terminated = True
        self.last_status = "Stopping…"

    def _current_x_ratio(self) -> Optional[float]:
        return player_x_ratio(self.loc_player_minimap, self.minimap_w)

    def capture_left(self) -> Optional[float]:
        ratio = self._current_x_ratio()
        if ratio is None:
            self.last_status = "Cannot capture left: minimap player not detected"
            logger.warning("[BoundaryRecorder] %s" % (self.last_status,))
            return None
        self.left_ratio = ratio
        self.last_status = f"LEFT range[0]={ratio:.3f} — walk RIGHT then F7"
        logger.info("[BoundaryRecorder] LEFT=%s" % (ratio,))
        return ratio

    def capture_right(self) -> Optional[List[float]]:
        """Sample RIGHT ratio only. Does not write patrol.yaml (manual Save in UI)."""
        ratio = self._current_x_ratio()
        if ratio is None:
            self.last_status = "Cannot capture right: minimap player not detected"
            logger.warning("[BoundaryRecorder] %s" % (self.last_status,))
            return None
        self.right_ratio = ratio
        left = self.left_ratio if self.left_ratio is not None else max(0.0, ratio - 0.02)
        rng = normalize_range(left, ratio)
        self.left_ratio, self.right_ratio = rng[0], rng[1]
        self.last_saved_range = None
        self.last_status = (
            f"Sampled RIGHT={ratio:.3f} (preview {rng[0]:.3f}–{rng[1]:.3f}) — click 保存边界 to write"
        )
        logger.info("[BoundaryRecorder] SAMPLE right=%s range=%s (no disk write)" % (ratio, rng))
        return rng

    def get_img_frame(self):
        frame = self.capture.get_frame()
        if frame is None:
            self.last_status = "Waiting for game window…"
            return None
        if getattr(self.capture, "returns_client_frame", False):
            frame_no_title = frame
            if not is_img_16_to_9(frame_no_title, self.cfg):
                return None
            return cv2.resize(
                frame_no_title,
                WINDOW_WORKING_SIZE,
                interpolation=cv2.INTER_NEAREST,
            )
        title_bar_height = int(self.cfg["game_window"]["title_bar_height"])
        if frame.shape[0] <= title_bar_height:
            return None
        frame_no_title = frame[title_bar_height:, :]
        return cv2.resize(
            frame_no_title,
            WINDOW_WORKING_SIZE,
            interpolation=cv2.INTER_NEAREST,
        )

    def run_once(self):
        img = self.get_img_frame()
        if img is None:
            return
        self.img_frame_debug = img.copy()
        loc_size = get_minimap_loc_size(img)
        if loc_size is None:
            cv2.putText(
                self.img_frame_debug,
                "Minimap not found",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
            return
        x, y, w, h = loc_size
        self.loc_minimap = (x, y)
        self.minimap_w = int(w)
        self.img_minimap = img[y : y + h, x : x + w]
        player_color = self.cfg.get("minimap", {}).get("player_color", (0, 255, 255))
        self.loc_player_minimap = get_player_location_on_minimap(
            self.img_minimap, minimap_player_color=player_color
        )
        cur = self._current_x_ratio()
        lines = [
            f"BoundaryRecorder map={self.map_name}",
            "F6 left | F7 right+save | F9 quit",
            self.last_status[:80],
            f"range L={self.left_ratio} R={self.right_ratio} cur={cur}",
        ]
        if self.loc_player_minimap is not None:
            cv2.circle(
                self.img_minimap,
                self.loc_player_minimap,
                3,
                (0, 255, 255),
                -1,
            )
        for i, text in enumerate(lines):
            cv2.putText(
                self.img_frame_debug,
                text,
                (10, 28 + i * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 200, 0),
                2,
                cv2.LINE_AA,
            )
        if self.img_minimap is not None:
            preview = cv2.resize(
                self.img_minimap,
                None,
                fx=2,
                fy=2,
                interpolation=cv2.INTER_NEAREST,
            )
            ph, pw = preview.shape[:2]
            fh, fw = self.img_frame_debug.shape[:2]
            x0 = max(0, fw - pw - 8)
            y0 = 8
            y1 = min(fh, y0 + ph)
            x1 = min(fw, x0 + pw)
            self.img_frame_debug[y0:y1, x0:x1] = preview[: y1 - y0, : x1 - x0]

    def cleanup(self):
        try:
            self.capture.stop()
        except Exception:
            pass
        try:
            self.kb.stop()
        except Exception:
            pass
