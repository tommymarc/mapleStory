"""Shared rope / layer-change climb recorder for smart_patrol.

Used by tools/ropeRecorder.py (CLI) and the Map manage UI.
Hotkeys when KeyBoardListener is attached:
  F6  Start recording (fresh live minimap player sample)
  F7  Stop & save end point to ~/.maplebot/maps/<map>/ropes.yaml
  F8  List edges
  F9  Quit

Each F6/F7 re-captures the game window, locates the live minimap inset, and
detects the yellow player marker — same pipeline as runtime smart_patrol Return.
Start/end are live inset pixel coords. Player-not-found refuses to save.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

import cv2

from src.utils.common import (
    get_minimap_loc_size,
    get_player_location_on_minimap,
    is_mac,
    is_img_16_to_9,
    load_yaml,
    override_cfg,
)
from src.utils.global_var import WINDOW_WORKING_SIZE
from src.utils.logger import logger
from src.utils.paths import MINIMAPS, get_app_root
from src.utils.ropes import append_edge, load_ropes, ropes_path
from src.input.KeyBoardListener import KeyBoardListener

if is_mac():
    from src.input.GameWindowCapturorForMac import GameWindowCapturor
else:
    from src.input.GameWindowCapturor import GameWindowCapturor


def load_recorder_cfg(cfg_name: str = "tommy") -> dict:
    """Load config_default + config_{cfg_name} for recorder capture settings."""
    root = str(get_app_root())
    base = load_yaml(os.path.join(root, "config", "config_default.yaml"))
    custom = os.path.join(root, "config", f"config_{cfg_name}.yaml")
    if os.path.isfile(custom):
        override_cfg(base, load_yaml(custom))
    return base


def cfg_name_from_path(config_path: str, default: str = "tommy") -> str:
    if not config_path:
        return default
    base = os.path.basename(config_path)
    if base.startswith("config_") and base.endswith(".yaml"):
        return base[len("config_") : -len(".yaml")]
    return default


class RopeRecorder:
    """Capture minimap player point and append climb edges to ropes.yaml."""

    def __init__(self, map_name: str, cfg: dict, register_hotkeys: bool = True):
        self.map_name = map_name
        self.cfg = cfg
        self.capture = GameWindowCapturor(cfg)
        self.kb = KeyBoardListener(cfg=cfg, is_autobot=False)
        if register_hotkeys:
            self.kb.register_func_key_handler("f6", self.start_record)
            self.kb.register_func_key_handler("f7", self.stop_record)
            self.kb.register_func_key_handler("f8", self.list_edges)
            self.kb.register_func_key_handler("f9", self.request_stop)

        self.is_terminated = False
        self.is_recording = False
        self.start_xy = None
        self.t_record_start = 0.0
        self.loc_minimap = (0, 0)
        self.img_minimap = None
        self.minimap_w = 0
        self.minimap_h = 0
        self.loc_player_minimap = None
        self.img_frame_debug = None
        self.last_status = "Ready — F6 start, climb, F7 save"
        self.fps_limit = 20
        self._window_size_adapted = False
        self.last_saved_edge: Optional[Dict[str, Any]] = None
        self._sample_lock = threading.Lock()

        os.makedirs(os.path.join(MINIMAPS, map_name), exist_ok=True)
        logger.info("[RopeRecorder] map=%s path=%s" % (map_name, ropes_path(map_name)))
        self.list_edges()

    def request_stop(self):
        self.is_terminated = True
        self.last_status = "Stopping…"

    def list_edges(self):
        doc = load_ropes(self.map_name)
        edges = doc.get("edges") or []
        logger.info("[RopeRecorder] %s edges for %s:" % (len(edges), self.map_name))
        for e in edges:
            logger.info(
                "  - %s start=%s end=%s dir=%s hint=%s"
                % (
                    e.get("id"),
                    e.get("start"),
                    e.get("end"),
                    e.get("direction"),
                    e.get("duration_hint_sec"),
                )
            )
        if not edges:
            logger.info("  (none yet — record at least one climb)")
        self.last_status = f"Listed {len(edges)} rope edge(s) — see log"

    def get_img_frame(self):
        frame = self.capture.get_frame()
        if frame is None:
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

    def sample_live_player(self) -> Optional[Tuple[float, float]]:
        """Capture game window → locate minimap inset → detect player marker.

        Same coordinate space as runtime bot / smart_patrol Return.
        Returns (x, y) pixels on the live inset, or None if not found.
        """
        with self._sample_lock:
            img = self.get_img_frame()
            if img is None:
                self.last_status = "Cannot capture: waiting for game window"
                self.loc_player_minimap = None
                return None
            self.img_frame_debug = img.copy()
            loc_size = get_minimap_loc_size(img)
            if loc_size is None:
                self.last_status = "Cannot capture: live minimap not found"
                self.loc_player_minimap = None
                self.minimap_w = 0
                self.minimap_h = 0
                self.img_minimap = None
                logger.warning("[RopeRecorder] %s" % (self.last_status,))
                return None
            x, y, w, h = loc_size
            self.loc_minimap = (x, y)
            self.minimap_w = int(w)
            self.minimap_h = int(h)
            self.img_minimap = img[y : y + h, x : x + w].copy()
            player_color = self.cfg.get("minimap", {}).get("player_color", (0, 255, 255))
            self.loc_player_minimap = get_player_location_on_minimap(
                self.img_minimap, minimap_player_color=player_color
            )
            if self.loc_player_minimap is None:
                self.last_status = (
                    "Cannot capture: player marker not found on live minimap"
                )
                logger.warning("[RopeRecorder] %s" % (self.last_status,))
                return None
            return (
                float(self.loc_player_minimap[0]),
                float(self.loc_player_minimap[1]),
            )

    def _current_player_xy(self):
        if self.loc_player_minimap is None:
            return None
        try:
            return (float(self.loc_player_minimap[0]), float(self.loc_player_minimap[1]))
        except (TypeError, IndexError, ValueError):
            return None

    def start_record(self):
        xy = self.sample_live_player()
        if xy is None:
            return False
        self.is_recording = True
        self.start_xy = xy
        self.t_record_start = time.time()
        self.last_status = (
            f"Recording… start={xy} (live {self.minimap_w}x{self.minimap_h}) "
            f"— climb then press F7"
        )
        logger.info(
            "[RopeRecorder] START start=%s minimap=%sx%s"
            % (xy, self.minimap_w, self.minimap_h)
        )
        return True

    def stop_record(self):
        if not self.is_recording or self.start_xy is None:
            self.last_status = "Not recording — press F6 first"
            logger.warning("[RopeRecorder] %s" % (self.last_status,))
            return None
        xy = self.sample_live_player()
        if xy is None:
            # Keep recording active so user can retry F7 without losing start.
            return None
        duration = max(0.1, time.time() - self.t_record_start)
        direction = "up" if xy[1] < self.start_xy[1] else "down"
        try:
            edge = append_edge(
                self.map_name,
                self.start_xy,
                xy,
                direction=direction,
                duration_hint_sec=round(duration, 2),
            )
        except Exception as err:
            self.last_status = f"Save failed: {err}"
            logger.exception("[RopeRecorder] save failed")
            return None
        self.is_recording = False
        self.start_xy = None
        self.last_saved_edge = edge
        path = ropes_path(self.map_name)
        self.last_status = (
            f"Saved {edge['id']} {edge['direction']} "
            f"{edge['start']}→{edge['end']} ({duration:.1f}s) → {path}"
        )
        logger.info("[RopeRecorder] SAVED %s → %s" % (edge, path))
        return edge

    def run_once(self):
        img = self.get_img_frame()
        if img is None:
            if "Waiting" not in (self.last_status or ""):
                self.last_status = "Waiting for game window…"
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
        self.minimap_h = int(h)
        self.img_minimap = img[y : y + h, x : x + w]
        player_color = self.cfg.get("minimap", {}).get("player_color", (0, 255, 255))
        self.loc_player_minimap = get_player_location_on_minimap(
            self.img_minimap, minimap_player_color=player_color
        )
        lines = [
            f"RopeRecorder map={self.map_name}",
            "F6 start | F7 save | F8 list | F9 quit (live minimap)",
            self.last_status[:80],
        ]
        if self.loc_player_minimap is not None:
            lines.append(f"minimap xy={self.loc_player_minimap} size={self.minimap_w}x{self.minimap_h}")
            cv2.circle(
                self.img_minimap,
                (int(round(self.loc_player_minimap[0])), int(round(self.loc_player_minimap[1]))),
                3,
                (0, 255, 255),
                -1,
            )
        else:
            lines.append("PLAYER MARKER NOT FOUND — will not save")
        if self.is_recording and self.start_xy is not None:
            lines.append(f"REC start={self.start_xy}")
        for i, text in enumerate(lines):
            cv2.putText(
                self.img_frame_debug,
                text,
                (10, 28 + i * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255) if (self.is_recording or self.loc_player_minimap is None) else (0, 200, 0),
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

    def run(self, show_window=True):
        logger.info(
            "[RopeRecorder] Walk to rope, F6, climb to other layer, F7. "
            "Do NOT run smart_patrol while recording."
        )
        while not self.is_terminated:
            t0 = time.time()
            self.run_once()
            if show_window and self.img_frame_debug is not None:
                cv2.imshow("RopeRecorder", self.img_frame_debug)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.is_terminated = True
            elapsed = time.time() - t0
            time.sleep(max(0.0, 1.0 / self.fps_limit - elapsed))
        self.cleanup()
        if show_window:
            cv2.destroyAllWindows()
        logger.info("[RopeRecorder] Done. File: %s" % (ropes_path(self.map_name),))


# Back-compat alias used by older call sites
_load_cfg = load_recorder_cfg
