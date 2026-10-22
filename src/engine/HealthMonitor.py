'''
Health Monitor take game windows as input to calculate player's HP/MP/EXP Bar percentage.
When player's HP/MP drop to specific threshold, it'd press key to drink potion 
'''

# Standard Import
import math
import threading
import time
import cv2
import itertools
import random

# Local Import
from src.utils.logger import logger
from src.utils.common import get_bar_percent
from src.input.KeyBoardController import press_key

class HealthMonitor:
    '''
    Independent health monitoring thread that can heal while other actions are running
    '''
    def __init__(self, cfg, kb_controller):
        self.cfg = cfg
        self.kb = kb_controller
        self.is_terminated = False
        self.enabled = True
        self.thread = None # health monitor thread

        # Health monitoring state
        self.hp_percent = 100
        self.mp_percent = 100
        self.exp_percent = 100

        # Timers
        self.t_last_heal = 0
        self.t_last_mp = 0
        self.t_last_hp_reduce = 0
        self.t_last_run = 0
        self.t_hp_watch_dog = time.time()
        self.t_last_bar_detection_warning = 0
        self.has_valid_bar_detection = False

        # Frame data (will be updated by main thread)
        self.img_frame = None
        self.frame_lock = threading.Lock()

        # FPS settings
        self.fps_limit = self.cfg["health_monitor"]["fps_limit"]
        self.fps = 0

        # Debug information
        # hp/mp/exp bars loc and size, [(x,y,w,h), ...]
        self.loc_size_bars = [(0, 0, 0, 0),
                              (0, 0, 0, 0),
                              (0, 0, 0, 0)]

        logger.info("[Health Monitor] Init done")

    def start(self):
        '''
        Start health monitoring thread
        '''
        if not self.is_terminated:
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logger.info("[Health Monitor] Started")

    def stop(self):
        '''
        Stop health monitoring thread
        '''
        self.is_terminated = True
        if self.thread:
            self.thread.join()
            logger.info("[Health Monitor] Terminated")

    def enable(self):
        '''
        Enable health monitoring
        '''
        self.enabled = True

    def disable(self):
        '''
        Disable health monitoring
        '''
        self.enabled = False

    def update_frame(self, img_frame):
        '''
        Update frame data from main thread
        '''
        with self.frame_lock:
            self.img_frame = img_frame

    def _find_status_bar_boxes(self, white_mask):
        """Find the aligned HP, MP and EXP border rectangles adaptively."""
        contours, _ = cv2.findContours(
            white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        frame_h, frame_w = white_mask.shape[:2]
        min_width = max(40, int(frame_w * 0.03))
        max_width = max(min_width + 1, int(frame_w * 0.25))
        max_height = max(12, int(frame_h * 0.6))
        candidates = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            ratio = w / float(max(1, h))
            if (
                min_width <= w <= max_width
                and 6 <= h <= max_height
                and 3.0 <= ratio <= 20.0
            ):
                candidates.append((x, y, w, h))

        best = None
        best_score = float("inf")
        for group in itertools.combinations(candidates, 3):
            bars = sorted(group, key=lambda bar: bar[0])
            widths = [bar[2] for bar in bars]
            heights = [bar[3] for bar in bars]
            centers_y = [bar[1] + bar[3] / 2.0 for bar in bars]
            avg_width = sum(widths) / 3.0
            avg_height = sum(heights) / 3.0

            if max(centers_y) - min(centers_y) > max(4.0, avg_height * 0.5):
                continue
            if max(widths) > min(widths) * 1.8:
                continue
            if max(heights) - min(heights) > max(4.0, avg_height * 0.5):
                continue

            gaps = [
                bars[1][0] - (bars[0][0] + bars[0][2]),
                bars[2][0] - (bars[1][0] + bars[1][2]),
            ]
            if any(
                gap < -5 or gap > max(60.0, avg_width * 0.75)
                for gap in gaps
            ):
                continue

            score = (
                (max(centers_y) - min(centers_y)) * 5.0
                + (max(widths) - min(widths))
                + (max(heights) - min(heights)) * 3.0
                + abs(gaps[0] - gaps[1])
            )
            if score < best_score:
                best = bars
                best_score = score

        return best or [], sorted(candidates, key=lambda bar: (bar[1], bar[0]))

    def get_hp_mp_exp_percent(self):
        '''
        Extracts the player's HP, MP, and EXP ratios from game frame.

        This function:
        - Crops the predefined HP, MP, and EXP bar regions from the game frame.
        - Identifies empty areas in each bar.
        - Computes the fill ratio for each bar as: 1 - (empty_pixels / total_pixels).

        Returns:
            tuple: (hp_percent, mp_percent, exp_percent), each a float between 0 and 1.
        '''
        if self.img_frame is None:
            return None, None, None

        with self.frame_lock:
            img_frame = self.img_frame.copy()

        img_frame_gray = cv2.cvtColor(img_frame, cv2.COLOR_BGR2GRAY)
        white_mask = cv2.inRange(img_frame_gray, 240, 255)
        # cv2.imshow("white_mask", white_mask)

        loc_size_bars, candidates = self._find_status_bar_boxes(white_mask)
        if len(loc_size_bars) != 3:
            now = time.time()
            if now - getattr(self, "t_last_bar_detection_warning", 0) > 5.0:
                logger.warning(
                    "[Health Monitor] Unable to locate HP/MP/EXP bars; "
                    f"horizontal white-box candidates: {candidates}"
                )
                self.t_last_bar_detection_warning = now
            self.has_valid_bar_detection = False
            return (None, None, None)

        if not getattr(self, "has_valid_bar_detection", False):
            logger.info(
                f"[Health Monitor] Located HP/MP/EXP bars: {loc_size_bars}"
            )
        self.has_valid_bar_detection = True

        # Update loc_size_bars
        self.loc_size_bars = loc_size_bars

        # Get bar filled ratio
        percent_bars = []
        for x, y, w, h in loc_size_bars:
            percent_bars.append(get_bar_percent(img_frame[y:y+h, x:x+w]))
        return percent_bars

    def _get_potion_profile(self):
        """Return potion_profile dict (may be empty)."""
        hm = self.cfg.get("health_monitor") or {}
        profile = hm.get("potion_profile")
        return profile if isinstance(profile, dict) else {}

    def _potion_profile_enabled(self):
        """True only when user enabled/saved potion config dialog."""
        return bool(self._get_potion_profile().get("enable", False))

    def _calc_presses(self, current_percent, target_percent, potion_amount, max_stat, max_presses):
        """
        Compute potion key presses for one burst using absolute restore values.

        deficit = max_stat * max(0, target_percent - current_percent) / 100
        presses = ceil(deficit / potion_amount), clamped to [1, max_presses]
        If already above target -> 0 (skip).
        If potion_amount <= 0 -> 1 press (legacy).
        Caller must ensure max_stat > 0; otherwise use single-press fallback.
        """
        try:
            amount = float(potion_amount)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            return 1

        deficit = float(max_stat) * max(0.0, float(target_percent) - float(current_percent)) / 100.0
        if deficit <= 0:
            return 0

        presses = int(math.ceil(deficit / amount))
        max_p = max(1, int(max_presses))
        return max(1, min(max_p, presses))

    def _press_potion_burst(self, key, presses, press_interval):
        """Press potion key N times with jittered interval between presses."""
        for i in range(presses):
            press_key(key, 0.05)
            if i < presses - 1:
                interval = float(press_interval) * random.uniform(0.8, 1.4)
                time.sleep(max(0.0, interval))

    def _monitor_loop(self):
        """
        Main monitoring loop running in separate thread
        """
        while not self.is_terminated:
            try:
                if not self.enabled:
                    self.limit_fps()
                    continue

                # Get current time
                t_cur = time.time()

                # Get current HP/MP ratios
                hp_percent, mp_percent, exp_percent = self.get_hp_mp_exp_percent()
                if hp_percent is not None:
                    # Check if HP bar has reduced
                    if self.hp_percent > hp_percent:
                        self.t_last_hp_reduce = t_cur
                    self.hp_percent = hp_percent
                if mp_percent is not None:
                    self.mp_percent = mp_percent
                if exp_percent is not None:
                    self.exp_percent = exp_percent

                hm = self.cfg["health_monitor"]
                profile = self._get_potion_profile()
                profile_on = bool(profile.get("enable", False))

                # Thresholds: potion profile min% when enabled, else classic single threshold
                if profile_on:
                    hp_thres = profile.get(
                        "add_hp_percent_min", hm["add_hp_percent"]
                    )
                    mp_thres = profile.get(
                        "add_mp_percent_min", hm["add_mp_percent"]
                    )
                else:
                    hp_thres = hm["add_hp_percent"]
                    mp_thres = hm["add_mp_percent"]

                hp_cd = hm["add_hp_cooldown"]
                mp_cd = hm["add_mp_cooldown"]
                watchdog_timeout = hm["return_home_watch_dog_timeout"]

                # Check if need to heal (with cooldown)
                if hm.get("force_heal", False):
                    # Ignore attack priority via KB flag
                    if self.hp_percent <= hp_thres:
                        if not self.kb.is_need_force_heal:
                            logger.info(f"[Health Monitor] Force heal triggered, "
                                        f"HP: {self.hp_percent:.1f}%")
                        self.kb.is_need_force_heal = True
                        hp_cd_eff = hp_cd * getattr(self, "_hp_cd_jitter", 1.0)
                        if t_cur - self.t_last_heal > hp_cd_eff:
                            self._heal()
                            self.t_last_heal = time.time()
                            # Anti-spam: single jitter on post-heal cooldown
                            self._hp_cd_jitter = random.uniform(0.85, 1.35)
                    else:
                        self.kb.is_need_force_heal = False
                else:
                    hp_cd_eff = hp_cd * getattr(self, "_hp_cd_jitter", 1.0)
                    if (self.hp_percent <= hp_thres and
                        t_cur - self.t_last_heal > hp_cd_eff):
                        self._heal()
                        self.t_last_heal = time.time()
                        # Anti-spam: single jitter on post-heal cooldown
                        self._hp_cd_jitter = random.uniform(0.85, 1.35)

                # Check if no HP potion and need to return home
                if hm.get("return_home_if_no_potion", False):
                    if self.hp_percent >= hp_thres:
                        self.t_hp_watch_dog = t_cur # reset watchdog
                    else:
                        # If watchdog timeout, use homing scroll to return home
                        if t_cur - self.t_hp_watch_dog > watchdog_timeout:
                            logger.warning(f"[Health Monitor] HP({self.hp_percent:.1f}%) < {hp_thres:.1f}% "
                                           f"for {round(t_cur - self.t_hp_watch_dog, 2)} seconds.")
                            logger.warning(f"[Health Monitor] Return home because potion is used up.")
                            press_key(self.cfg["key"]["return_home"]) # Return home
                            self.is_terminated = True # Terminate Health monitor
                            self.kb.is_terminated = True # Terminate AutoBot

                # Check if need MP (with cooldown)
                mp_cd_eff = mp_cd * getattr(self, "_mp_cd_jitter", 1.0)
                if (self.mp_percent <= mp_thres and t_cur - self.t_last_mp > mp_cd_eff):
                    self._add_mp()
                    self.t_last_mp = time.time()
                    # Anti-spam: single jitter on post-mp cooldown
                    self._mp_cd_jitter = random.uniform(0.85, 1.35)

                # Sleep to avoid excessive CPU usage
                self.limit_fps()

            except Exception as e:
                logger.error(f"[Health Monitor] {e}")
                self.limit_fps()

    def _heal(self):
        """
        HP potion: classic single press, or multi-press burst when potion_profile enabled.
        """
        try:
            key = self.cfg["key"]["add_hp"]
            profile = self._get_potion_profile()
            if not profile.get("enable", False):
                # Original logic: one key press per trigger
                logger.info(
                    f"[Health Monitor] Add HP: {round(self.hp_percent, 1)}%"
                )
                press_key(key, 0.05)
                return

            target = profile.get("add_hp_percent_max", 70)
            potion_amount = profile.get("add_hp_potion_amount", 300)
            max_presses = profile.get(
                "add_hp_max_presses", profile.get("max_presses", 5)
            )
            press_interval = profile.get(
                "add_hp_press_interval", profile.get("press_interval", 0.15)
            )
            try:
                max_hp = int(profile.get("add_hp_max", 0) or 0)
            except (TypeError, ValueError):
                max_hp = 0

            if max_hp <= 0:
                logger.warning(
                    "[Health Monitor] potion_profile enabled but add_hp_max "
                    "missing/<=0; falling back to single HP press"
                )
                logger.info(
                    f"[Health Monitor] Add HP: {round(self.hp_percent, 1)}%"
                )
                press_key(key, 0.05)
                return

            presses = self._calc_presses(
                self.hp_percent, target, potion_amount, max_hp, max_presses
            )
            if presses <= 0:
                return

            deficit = max_hp * max(0.0, float(target) - float(self.hp_percent)) / 100.0
            logger.info(
                f"[Health Monitor] HP burst: presses={presses}, "
                f"current={self.hp_percent:.1f}%, target={target}%, "
                f"max_hp={max_hp}, deficit={deficit:.0f}, amount={potion_amount}"
            )
            self._press_potion_burst(key, presses, press_interval)
        except Exception as e:
            logger.error(f"[Health Monitor] Heal action failed: {e}")

    def _add_mp(self):
        """
        MP potion: classic single press, or multi-press burst when potion_profile enabled.
        """
        try:
            key = self.cfg["key"]["add_mp"]
            profile = self._get_potion_profile()
            if not profile.get("enable", False):
                # Original logic: one key press per trigger
                logger.info(
                    f"[Health Monitor] Add MP: {round(self.mp_percent, 1)}%"
                )
                press_key(key, 0.05)
                return

            target = profile.get("add_mp_percent_max", 60)
            potion_amount = profile.get("add_mp_potion_amount", 150)
            max_presses = profile.get(
                "add_mp_max_presses", profile.get("max_presses", 5)
            )
            press_interval = profile.get(
                "add_mp_press_interval", profile.get("press_interval", 0.15)
            )
            try:
                max_mp = int(profile.get("add_mp_max", 0) or 0)
            except (TypeError, ValueError):
                max_mp = 0

            if max_mp <= 0:
                logger.warning(
                    "[Health Monitor] potion_profile enabled but add_mp_max "
                    "missing/<=0; falling back to single MP press"
                )
                logger.info(
                    f"[Health Monitor] Add MP: {round(self.mp_percent, 1)}%"
                )
                press_key(key, 0.05)
                return

            presses = self._calc_presses(
                self.mp_percent, target, potion_amount, max_mp, max_presses
            )
            if presses <= 0:
                return

            deficit = max_mp * max(0.0, float(target) - float(self.mp_percent)) / 100.0
            logger.info(
                f"[Health Monitor] MP burst: presses={presses}, "
                f"current={self.mp_percent:.1f}%, target={target}%, "
                f"max_mp={max_mp}, deficit={deficit:.0f}, amount={potion_amount}"
            )
            self._press_potion_burst(key, presses, press_interval)
        except Exception as e:
            logger.error(f"[Health Monitor] MP action failed: {e}")

    def limit_fps(self):
        '''
        Limit FPS
        '''
        # If the loop finished early, sleep to maintain target FPS
        target_duration = 1.0 / self.fps_limit  # seconds per frame
        frame_duration = time.time() - self.t_last_run
        if frame_duration < target_duration:
            time.sleep(target_duration - frame_duration)

        # Update FPS
        self.fps = round(1.0 / (time.time() - self.t_last_run))
        self.t_last_run = time.time()
        # logger.info(f"FPS = {self.fps}")
