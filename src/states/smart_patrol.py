"""Smart patrol mode: Scan <-> Engage <-> Return (rope / layer change).

Phase1: single-layer bounds + Scan/Engage attack (rope Return deferred; rope_enable default false).
Boundary always wins over mob chase. P2 rope macros remain optional behind rope_enable.
"""
from __future__ import annotations

import math
import time

from src.states.base_state import State
from src.utils.logger import logger
from src.utils.ropes import (
    dist2,
    is_off_preferred_band,
    nearest_edge,
)


PHASE_SCAN = "scan"
PHASE_ENGAGE = "engage"
PHASE_RETURN = "return"


class SmartPatrolState(State):
    """Walk the current platform via minimap, engage, or climb recorded ropes."""

    def __init__(self, name, bot):
        super().__init__(name, bot)
        self.phase = PHASE_SCAN
        self.scan_dir = "right"
        self.turn_point_cnt = 0
        self.t_phase_enter = 0.0
        self.t_scan_dir_since = 0.0
        self.t_no_mob_since = 0.0
        self.t_last_rope_attempt = 0.0
        self.active_edge = None
        self.return_sub = "approach"  # approach | climb
        self.t_climb_start = 0.0
        self.t_last_missing_rope_log = 0.0
        self._y_soft_locked = False
        self._y_lock_anchor = None
        self._y_lock_since = 0.0

    def _sp_cfg(self):
        cfg = self.bot.cfg.get("smart_patrol") or {}
        if not isinstance(cfg, dict):
            cfg = {}
        return cfg

    def _cfg_float(self, key, default):
        raw = self._sp_cfg().get(key, default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    def _cfg_int(self, key, default):
        raw = self._sp_cfg().get(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return int(default)

    def _cfg_bool(self, key, default=True):
        raw = self._sp_cfg().get(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw) if raw is not None else bool(default)

    def _scan_range(self):
        raw = self._sp_cfg().get("range", [0.25, 0.75])
        try:
            left, right = float(raw[0]), float(raw[1])
        except (TypeError, ValueError, IndexError):
            left, right = 0.25, 0.75
        left = max(0.0, min(1.0, left))
        right = max(0.0, min(1.0, right))
        if left > right:
            left, right = right, left
        return left, right

    def _rope_doc(self):
        return getattr(self.bot, "rope_doc", None) or {}

    def _rope_edges(self):
        edges = getattr(self.bot, "rope_edges", None)
        if edges is None:
            edges = self._rope_doc().get("edges") or []
        return edges or []

    def _preferred_y(self):
        cfg_y = self._sp_cfg().get("preferred_y", None)
        if cfg_y is not None:
            try:
                return float(cfg_y)
            except (TypeError, ValueError):
                pass
        doc_y = self._rope_doc().get("preferred_y", None)
        if doc_y is not None:
            try:
                return float(doc_y)
            except (TypeError, ValueError):
                pass
        return None

    def _preferred_tol(self):
        cfg_tol = self._sp_cfg().get("preferred_y_tol", None)
        if cfg_tol is not None:
            return max(1.0, self._cfg_float("preferred_y_tol", 12.0))
        try:
            return max(1.0, float(self._rope_doc().get("preferred_y_tol", 12) or 12))
        except (TypeError, ValueError):
            return 12.0

    def on_enter(self):
        self.phase = PHASE_SCAN
        self.scan_dir = "right"
        self.turn_point_cnt = 0
        now = time.time()
        self.t_phase_enter = now
        self.t_scan_dir_since = now
        self.t_no_mob_since = 0.0
        self.t_last_rope_attempt = 0.0
        self.active_edge = None
        self.return_sub = "approach"
        self.t_climb_start = 0.0
        self.t_last_missing_rope_log = 0.0
        self._y_soft_locked = False
        self._y_lock_anchor = None
        self._y_lock_since = 0.0
        if hasattr(self.bot, "clear_engage"):
            self.bot.clear_engage()
        self._warn_missing_ropes(now, force=True)

    def on_exit(self):
        self.bot.cmd_move_x = "none"
        self.bot.cmd_move_y = "none"
        self.bot.cmd_action = "none"
        self.active_edge = None

    def check_transitions(self):
        return None

    def _enter_phase(self, phase):
        if self.phase == phase:
            return
        self.phase = phase
        self.t_phase_enter = time.time()
        self.t_no_mob_since = 0.0
        if phase == PHASE_SCAN:
            self.turn_point_cnt = 0
            self.t_scan_dir_since = time.time()
            self.active_edge = None
            self.return_sub = "approach"
            if hasattr(self.bot, "clear_engage"):
                self.bot.clear_engage()
        elif phase == PHASE_RETURN:
            self.return_sub = "approach"
            self.t_climb_start = 0.0
            if hasattr(self.bot, "clear_engage"):
                self.bot.clear_engage()

    def _has_combat_target(self):
        monsters = getattr(self.bot, "monsters", None) or []
        decision = getattr(self.bot, "decision_monsters", None)
        if decision is None:
            decision = monsters
        soft = False
        if hasattr(self.bot, "has_soft_combat_target"):
            try:
                soft = bool(self.bot.has_soft_combat_target())
            except Exception:
                soft = False
        engaging = False
        if hasattr(self.bot, "is_engaging"):
            try:
                engaging = bool(self.bot.is_engaging())
            except Exception:
                engaging = False
        return bool(decision) or soft or engaging

    def _has_in_range_attack_target(self):
        """True only when a monster is inside the attack/AoE box.

        Search-ROI ghosts used to count as combat targets, which froze Scan
        locomotion for up to engage_timeout_sec while the character stood still.
        """
        bot = self.bot
        attack = ""
        try:
            attack = str((bot.cfg.get("bot") or {}).get("attack") or "")
        except Exception:
            attack = ""
        try:
            aoe_n = int(getattr(bot, "hybrid_aoe_monster_count", 0) or 0)
        except (TypeError, ValueError):
            aoe_n = 0
        trigger = 2
        try:
            trigger = max(1, int((bot.cfg.get("hybrid_attack") or {}).get(
                "aoe_trigger_count", 2
            )))
        except (TypeError, ValueError, AttributeError):
            trigger = 2
        if attack == "hybrid" and aoe_n >= trigger:
            return True
        getter = getattr(bot, "get_nearest_monster", None)
        if callable(getter):
            try:
                if getter(is_left=True) is not None:
                    return True
                if getter(is_left=False) is not None:
                    return True
            except Exception:
                pass
        return False

    def _keep_patrol_locomotion(self):
        """Keep left/right Scan walking unless this frame needs a facing pulse.

        Hybrid AoE can fire while walking. Directional attacks that are already
        pulsing a turn keep that pulse for one frame.
        """
        action = getattr(self.bot, "cmd_action", "none")
        if action == "attack":
            return
        pending = getattr(self.bot, "combat_turn_pending_direction", None)
        move = getattr(self.bot, "cmd_move_x", "none")
        if pending in ("left", "right") and move == pending:
            return
        self.apply_scan_move()
        if action == "aoe_attack":
            self.bot.cmd_action = action
        self._enforce_x_bounds(allow_outside_for_return=False)

    def _flip_scan_dir(self):
        self.scan_dir = "left" if self.scan_dir == "right" else "right"
        self.turn_point_cnt = 0
        self.t_scan_dir_since = time.time()

    def _minimap_xy(self):
        """Player (x, y) on captured minimap; None if unavailable."""
        if not getattr(self.bot, "is_player_minimap_detected", False):
            return None
        loc = getattr(self.bot, "loc_player_minimap", None)
        if loc is None:
            return None
        try:
            return (float(loc[0]), float(loc[1]))
        except (TypeError, IndexError, ValueError):
            return None

    def _minimap_x_ratio(self):
        """Player x on captured minimap in [0, 1]; None if unavailable."""
        xy = self._minimap_xy()
        img = getattr(self.bot, "img_minimap", None)
        if xy is None or img is None:
            return None
        try:
            w = int(img.shape[1])
        except (TypeError, IndexError, AttributeError):
            return None
        if w <= 0:
            return None
        return max(0.0, min(1.0, xy[0] / float(w)))


    _MISSING_ROPE_MSG = "必须先录绳子才能掉层爬回"

    def _warn_missing_ropes(self, now, force=False):
        """Soft one-shot info when Return cannot run (no modal / no error spam)."""
        if not self._cfg_bool("rope_enable", False):
            return False
        if self._rope_edges():
            return False
        # At most once per enter (t_last_missing_rope_log reset in on_enter).
        if self.t_last_missing_rope_log > 0 and not force:
            return True
        self.t_last_missing_rope_log = now if now else time.time()
        logger.info(
            "[smart_patrol] ropes.yaml edges=[] — Return disabled. "
            + self._MISSING_ROPE_MSG
            + " (UI: 地图→管理→绳子)"
        )
        return True

    def _maybe_soft_lock_preferred_y(self, now):
        """If preferred_y unset, soft-lock to stable minimap y while fighting/scanning with mobs.

        Enables fall / off-band detection before the user sets preferred_y manually.
        Does not invent rope coordinates.
        """
        if self._preferred_y() is not None:
            self._y_lock_anchor = None
            self._y_lock_since = 0.0
            return
        # Only accumulate while we have combat targets (engage or scan-with-mobs).
        if not self._has_combat_target():
            self._y_lock_anchor = None
            self._y_lock_since = 0.0
            return
        xy = self._minimap_xy()
        if xy is None:
            self._y_lock_anchor = None
            self._y_lock_since = 0.0
            return
        y = float(xy[1])
        stable_tol = max(1.0, self._cfg_float("preferred_y_autolock_tol", 3.0))
        need_sec = max(0.5, self._cfg_float("preferred_y_autolock_sec", 3.0))
        if self._y_lock_anchor is None:
            self._y_lock_anchor = y
            self._y_lock_since = now
            return
        if abs(y - self._y_lock_anchor) > stable_tol:
            self._y_lock_anchor = y
            self._y_lock_since = now
            return
        if (now - self._y_lock_since) < need_sec:
            return
        # Soft-lock into rope_doc (runtime); leave cfg preferred_y null so user override still wins later.
        doc = self._rope_doc()
        if not isinstance(doc, dict):
            return
        locked = float(self._y_lock_anchor)
        doc["preferred_y"] = locked
        self._y_soft_locked = True
        self._y_lock_anchor = None
        self._y_lock_since = 0.0
        logger.info(
            "[smart_patrol] soft-locked preferred_y=%.1f after %.1fs stable y (fall detection enabled)"
            % (locked, need_sec)
        )

    def _scan_no_mob_missing_rope(self, now):
        """When Scan has no mobs and no rope edges: remind user; keep slow walk in range."""
        if self.phase != PHASE_SCAN:
            return False
        if self._has_combat_target():
            return False
        if self._rope_edges():
            return False
        if not self._cfg_bool("rope_enable", False):
            return False
        no_mob_turn = max(0.1, self._cfg_float("no_mob_turn_sec", 1.5))
        if self.t_no_mob_since <= 0.0:
            self.t_no_mob_since = now
            return False
        if (now - self.t_no_mob_since) < no_mob_turn:
            return False
        self._warn_missing_ropes(now, force=False)
        # Stay on platform: normal range-bounded scan walk (no inventing ropes / no layer hops).
        return True

    def _near_patrol_edge(self, ratio, left_r, right_r):
        """True when x-ratio is at/past bound or within edge_jump_margin inside."""
        margin = max(0.0, self._cfg_float("edge_jump_margin", 0.03))
        return (
            ratio <= left_r + margin
            or ratio >= right_r - margin
        )

    def _edge_flags(self):
        """Return (ratio, left_r, right_r, at_left, at_right, past_left, past_right) or Nones."""
        left_r, right_r = self._scan_range()
        ratio = self._minimap_x_ratio()
        if ratio is None:
            return None, left_r, right_r, False, False, False, False
        margin = max(0.0, self._cfg_float("edge_jump_margin", 0.03))
        past_left = ratio <= left_r
        past_right = ratio >= right_r
        at_left = ratio <= left_r + margin
        at_right = ratio >= right_r - margin
        return ratio, left_r, right_r, at_left, at_right, past_left, past_right

    def _filter_outward_bound_monsters(self):
        """Drop mobs further outside the patrol edge so chase/attack never walks off-cliff.

        Boundary always wins: at/near left edge, ignore targets left of player;
        at/near right edge, ignore targets right of player. In-place Hybrid/AoE on
        remaining (inward / overlapping) targets is still allowed.
        """
        ratio, left_r, right_r, at_left, at_right, past_left, past_right = self._edge_flags()
        if ratio is None:
            return
        if not (at_left or at_right or past_left or past_right):
            return
        loc = getattr(self.bot, "loc_player", None)
        if loc is None:
            return
        try:
            px = float(loc[0])
        except (TypeError, IndexError, ValueError):
            return

        def keep(monster):
            try:
                mx, _my = monster["position"]
                mw, _mh = monster["size"]
                cx = float(mx) + float(mw) / 2.0
            except (TypeError, KeyError, ValueError, IndexError):
                return True
            # Outward = further past the edge we are already at.
            block_left = at_left or past_left
            block_right = at_right or past_right
            if block_left and cx < px - 2.0:
                return False
            if block_right and cx > px + 2.0:
                return False
            return True

        for attr in ("decision_monsters", "monsters", "soft_monsters"):
            lst = getattr(self.bot, attr, None)
            if not lst:
                continue
            filtered = [m for m in lst if keep(m)]
            setattr(self.bot, attr, filtered)
        # Keep hybrid AoE count coherent with filtered live list.
        try:
            if getattr(self.bot, "cfg", {}).get("bot", {}).get("attack") == "hybrid":
                if hasattr(self.bot, "count_monsters_in_aoe_range"):
                    self.bot.hybrid_aoe_monster_count = self.bot.count_monsters_in_aoe_range()
        except Exception:
            pass

    def _bound_aware_mob_detection(self):
        """Detect mobs, drop outward-of-bound chase targets, then attack — then hard clamp."""
        if hasattr(self.bot, "detect_monsters_near_player"):
            self.bot.detect_monsters_near_player()
            self._filter_outward_bound_monsters()
            self.bot.update_cmd_by_mob_detection(use_cached=True)
        else:
            self.bot.update_cmd_by_mob_detection()
            self._filter_outward_bound_monsters()
        self._enforce_x_bounds(allow_outside_for_return=False)

    def _enforce_x_bounds(self, allow_outside_for_return=False):
        """Hard clamp: boundary ALWAYS wins over mob chase / turn-pulse.

        - Past range: force inward move; cancel jump/teleport.
        - At/within edge_jump_margin: never allow cmd_move_x further outward
          (stand or face inward; Hybrid/AoE attack in place is OK).
        Returns True when a clamp was applied. Skip during Return.
        """
        if allow_outside_for_return:
            return False
        ratio, left_r, right_r, at_left, at_right, past_left, past_right = self._edge_flags()
        if ratio is None:
            return False
        moved = False
        if past_left and past_right:
            self.bot.cmd_move_x = "none"
            self.bot.cmd_move_y = "none"
            self.bot.cmd_action = "none"
            return True
        if past_left:
            want = "right"
            if self.scan_dir != want:
                self.scan_dir = want
                self.turn_point_cnt = 0
                self.t_scan_dir_since = time.time()
            self.bot.cmd_move_x = want
            self.bot.cmd_move_y = "none"
            if getattr(self.bot, "cmd_action", "none") in ("jump", "teleport"):
                self.bot.cmd_action = "none"
            return True
        if past_right:
            want = "left"
            if self.scan_dir != want:
                self.scan_dir = want
                self.turn_point_cnt = 0
                self.t_scan_dir_since = time.time()
            self.bot.cmd_move_x = want
            self.bot.cmd_move_y = "none"
            if getattr(self.bot, "cmd_action", "none") in ("jump", "teleport"):
                self.bot.cmd_action = "none"
            return True
        # Inside range but at margin: block outward chase / directional turn pulse.
        mx = getattr(self.bot, "cmd_move_x", "none")
        if at_left and mx == "left":
            # Stand (or face inward); do not walk further off the left cliff.
            self.bot.cmd_move_x = "none"
            if self.scan_dir == "left":
                self.scan_dir = "right"
                self.turn_point_cnt = 0
                self.t_scan_dir_since = time.time()
            moved = True
        elif at_right and mx == "right":
            self.bot.cmd_move_x = "none"
            if self.scan_dir == "right":
                self.scan_dir = "left"
                self.turn_point_cnt = 0
                self.t_scan_dir_since = time.time()
            moved = True
        if at_left or at_right:
            if getattr(self.bot, "cmd_action", "none") in ("jump", "teleport"):
                self.bot.cmd_action = "none"
                moved = True
        return moved

    def apply_scan_move(self):
        """Walk left/right on the current layer using minimap x bounds (hard edges)."""
        left_r, right_r = self._scan_range()
        # Default 1 = flip on first frame past bound (was 5; delayed flips caused cliff falls).
        thres = max(1, self._cfg_int("turn_point_thres", 1))
        scan_turn_sec = max(0.5, self._cfg_float("scan_turn_sec", 8.0))
        now = time.time()

        ratio = self._minimap_x_ratio()
        clamped = False
        if ratio is not None:
            past_left = ratio <= left_r
            past_right = ratio >= right_r
            if past_left or past_right:
                # Immediate flip + inward move — do not wait turn_point_thres frames off-cliff.
                want = "right" if past_left and not past_right else (
                    "left" if past_right and not past_left else None
                )
                if want is None:
                    self.bot.cmd_move_x = "none"
                    self.bot.cmd_move_y = "none"
                    self.bot.cmd_action = "none"
                    return
                if self.scan_dir != want:
                    self.scan_dir = want
                    self.turn_point_cnt = 0
                    self.t_scan_dir_since = now
                else:
                    # Already facing inside; still count for compatibility with thres>=2 configs.
                    self.turn_point_cnt = min(self.turn_point_cnt + 1, thres)
                clamped = True
            else:
                self.turn_point_cnt = 0

        # Time-based flip only while safely inside bounds (avoid fighting hard clamp).
        if (not clamped) and (now - self.t_scan_dir_since >= scan_turn_sec):
            self._flip_scan_dir()

        self.bot.cmd_move_x = self.scan_dir if self.scan_dir in ("left", "right") else "right"
        self.bot.cmd_move_y = "none"
        # Zero jump/teleport near or past edges to avoid cliff hops.
        if ratio is not None and self._near_patrol_edge(ratio, left_r, right_r):
            self.bot.cmd_action = "none"
        elif getattr(self.bot, "cmd_action", "none") not in ("jump", "teleport"):
            self.bot.cmd_action = "none"

    def _should_leave_engage(self, now):
        engage_timeout = max(0.5, self._cfg_float("engage_timeout_sec", 6.0))
        no_mob_turn = max(0.1, self._cfg_float("no_mob_turn_sec", 1.5))

        if now - self.t_phase_enter >= engage_timeout:
            return True

        if self._has_in_range_attack_target():
            self.t_no_mob_since = 0.0
            return False

        if self.t_no_mob_since <= 0.0:
            self.t_no_mob_since = now
            return False
        return (now - self.t_no_mob_since) >= no_mob_turn

    def _should_start_return(self, now):
        if not self._cfg_bool("rope_enable", False):
            return False
        edges = self._rope_edges()
        if not edges:
            return False
        cooldown = max(1.0, self._cfg_float("rope_cooldown_sec", 8.0))
        if now - self.t_last_rope_attempt < cooldown and self.t_last_rope_attempt > 0:
            # Still allow immediate return when clearly off preferred band.
            pass
        else:
            pass

        xy = self._minimap_xy()
        player_y = None if xy is None else xy[1]
        off_band = is_off_preferred_band(
            player_y, self._preferred_y(), self._preferred_tol()
        )
        if off_band:
            if now - self.t_last_rope_attempt >= min(2.0, cooldown):
                return True

        # Scan: no mobs for no_mob_turn_sec → try a layer change via rope.
        if self.phase != PHASE_SCAN:
            return False
        if self._has_combat_target():
            self.t_no_mob_since = 0.0
            return False
        no_mob_turn = max(0.1, self._cfg_float("no_mob_turn_sec", 1.5))
        if self.t_no_mob_since <= 0.0:
            self.t_no_mob_since = now
            return False
        if (now - self.t_no_mob_since) < no_mob_turn:
            return False
        if now - self.t_last_rope_attempt < cooldown:
            return False
        return True

    def _pick_return_edge(self):
        xy = self._minimap_xy()
        if xy is None:
            # Fall back to first edge if minimap briefly lost.
            edges = self._rope_edges()
            return edges[0] if edges else None
        prefer = self._preferred_y()
        # When off-band, bias toward edges whose end is nearer preferred_y.
        return nearest_edge(self._rope_edges(), xy, prefer_end_y=prefer)

    def _begin_return(self):
        edge = self._pick_return_edge()
        if edge is None:
            return False
        self.active_edge = edge
        self.t_last_rope_attempt = time.time()
        self._enter_phase(PHASE_RETURN)
        return True

    def _approach_dist(self):
        return max(2.0, self._cfg_float("rope_approach_dist", 8.0))

    def _arrive_dist(self):
        return max(2.0, self._cfg_float("rope_arrive_dist", 10.0))

    def _climb_timeout(self):
        hint = None
        if self.active_edge is not None:
            hint = self.active_edge.get("duration_hint_sec")
        if hint is not None:
            try:
                return max(1.5, float(hint) * 2.5)
            except (TypeError, ValueError):
                pass
        return max(2.0, self._cfg_float("rope_climb_timeout_sec", 6.0))

    def apply_return_move(self):
        """Navigate to rope start on minimap, then hold up/down until near end."""
        edge = self.active_edge
        if edge is None:
            self._enter_phase(PHASE_SCAN)
            self.apply_scan_move()
            return

        start = edge.get("start") or [0, 0]
        end = edge.get("end") or start
        direction = edge.get("direction") or "up"
        if direction not in ("up", "down"):
            direction = "up"

        xy = self._minimap_xy()
        approach = self._approach_dist()
        arrive = self._arrive_dist()
        now = time.time()

        if xy is None:
            # Keep climbing / approaching blindly with recorded direction.
            if self.return_sub == "climb":
                self.bot.cmd_move_x = "none"
                self.bot.cmd_move_y = direction
            else:
                self.bot.cmd_move_x = "none"
                self.bot.cmd_move_y = "none"
            self.bot.cmd_action = "none"
            if self.return_sub == "climb" and self.t_climb_start > 0:
                if now - self.t_climb_start >= self._climb_timeout():
                    self._finish_return(end_y=float(end[1]))
            return

        if self.return_sub == "approach":
            dx = float(start[0]) - xy[0]
            dy = float(start[1]) - xy[1]
            if math.sqrt(dx * dx + dy * dy) > approach:
                # Prefer horizontal walk toward rope base (same layer).
                if abs(dx) > 2:
                    self.bot.cmd_move_x = "right" if dx > 0 else "left"
                    self.bot.cmd_move_y = "none"
                else:
                    # Same x but wrong y: briefly hold vertical toward start.
                    self.bot.cmd_move_x = "none"
                    self.bot.cmd_move_y = "up" if dy < 0 else "down"
                self.bot.cmd_action = "none"
                if getattr(self.bot, "is_player_stuck", lambda: False)():
                    self.bot.cmd_action = "jump"
                return
            self.return_sub = "climb"
            self.t_climb_start = now

        # climb
        dx_end = float(end[0]) - xy[0]
        # Nudge horizontally toward end while holding vertical.
        if abs(dx_end) > approach:
            self.bot.cmd_move_x = "right" if dx_end > 0 else "left"
        else:
            self.bot.cmd_move_x = "none"
        self.bot.cmd_move_y = direction
        self.bot.cmd_action = "none"

        if math.sqrt(dist2(xy, end)) <= arrive:
            self._finish_return(end_y=float(end[1]))
            return
        if self.t_climb_start > 0 and (now - self.t_climb_start) >= self._climb_timeout():
            self._finish_return(end_y=float(end[1]))

    def _finish_return(self, end_y=None):
        # Lock preferred band to landing if not set in cfg.
        if end_y is not None and self._sp_cfg().get("preferred_y", None) is None:
            doc = self._rope_doc()
            if isinstance(doc, dict):
                doc["preferred_y"] = float(end_y)
        self.active_edge = None
        self.return_sub = "approach"
        self._enter_phase(PHASE_SCAN)
        self.apply_scan_move()

    def on_frame(self):
        if getattr(self.bot, "handle_hit_react_frame", lambda: False)():
            return

        now = time.time()
        self._maybe_soft_lock_preferred_y(now)

        if self.phase == PHASE_RETURN:
            self.apply_return_move()
        elif self.phase == PHASE_SCAN:
            self.apply_scan_move()
            self._enforce_x_bounds(allow_outside_for_return=False)
            self._bound_aware_mob_detection()
            if self._has_in_range_attack_target():
                self._enter_phase(PHASE_ENGAGE)
            self._keep_patrol_locomotion()
            if not self._has_in_range_attack_target():
                if self._should_start_return(now):
                    if self._begin_return():
                        self.apply_return_move()
                    else:
                        # edges empty or pick failed — do not spin silently
                        self._scan_no_mob_missing_rope(now)
                        if getattr(self.bot, "is_player_stuck", lambda: False)():
                            self.bot.update_cmd_by_random(allow_jump=False)
                            self._enforce_x_bounds(allow_outside_for_return=False)
                else:
                    self._scan_no_mob_missing_rope(now)
                    if getattr(self.bot, "is_player_stuck", lambda: False)():
                        self.bot.update_cmd_by_random(allow_jump=False)
                        self._enforce_x_bounds(allow_outside_for_return=False)
        else:
            # ENGAGE — attack in-range targets but keep Scan walking.
            self._bound_aware_mob_detection()
            if self._should_leave_engage(now):
                # Prefer rope when off preferred band after engage ends.
                if self._should_start_return(now) and self._begin_return():
                    self.apply_return_move()
                else:
                    self._enter_phase(PHASE_SCAN)
                    self._keep_patrol_locomotion()
            elif self._should_start_return(now) and is_off_preferred_band(
                None if self._minimap_xy() is None else self._minimap_xy()[1],
                self._preferred_y(),
                self._preferred_tol(),
            ):
                if self._begin_return():
                    self.apply_return_move()
            else:
                self._keep_patrol_locomotion()

        # Final hard clamp for Scan/Engage so chase/random never walks past range.
        if self.phase != PHASE_RETURN:
            self._enforce_x_bounds(allow_outside_for_return=False)

        # Near/past patrol bounds: jump-attack becomes attack-only (no outward jump).
        ratio, left_r, right_r, at_left, at_right, past_left, past_right = self._edge_flags()
        near_edge = False
        if ratio is not None:
            near_edge = bool(
                at_left or at_right or past_left or past_right
                or self._near_patrol_edge(ratio, left_r, right_r)
            )
        self.bot.suppress_jump = near_edge
        if getattr(self.bot, "kb", None) is not None:
            self.bot.kb.suppress_jump = near_edge
            self.bot.kb.set_command(
                self.bot.cmd_move_x + " " + self.bot.cmd_move_y + " " + self.bot.cmd_action
            )
        if self.bot.cmd_action in ("jump", "teleport", "attack", "aoe_attack"):
            self.bot.cmd_action = "none"
