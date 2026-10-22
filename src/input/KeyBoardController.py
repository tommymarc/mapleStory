'''
KeyBoardController
Simulate user keyboard input to control character in the game 
'''
# Standard Import
import random
import threading
import time

# Library import
import pyautogui
from pynput import keyboard

# Local import
from src.utils.logger import logger
from src.utils.common import is_mac, is_windows
from src.utils.profession_bindings import resolve_profession_binding

if is_windows():
    import pydirectinput as keyboard_output
else:
    keyboard_output = pyautogui

if is_mac():
    import Quartz
else:
    import pygetwindow as gw

pyautogui.PAUSE = 0  # remove mouse API delay
keyboard_output.PAUSE = 0  # remove keyboard backend delay

_FAILSAFE_EXCEPTIONS = tuple({
    pyautogui.FailSafeException,
    getattr(keyboard_output, "FailSafeException", pyautogui.FailSafeException),
})

# Add a small human-like timing variation to every keyboard input event.
# Delaying key-up also varies the time that the key remains held.
KEY_INPUT_JITTER_MIN = 0.01
KEY_INPUT_JITTER_MAX = 0.08
_pressed_keys = set()
_pressed_keys_lock = threading.RLock()


def _wait_for_key_input_jitter():
    time.sleep(random.uniform(KEY_INPUT_JITTER_MIN, KEY_INPUT_JITTER_MAX))

def key_down(key):
    '''
    Press key down
    '''
    if not key:
        return False

    # The controller evaluates held directions every frame. Only emit and
    # jitter the real up -> down transition instead of repeating keyDown.
    with _pressed_keys_lock:
        if key in _pressed_keys:
            return False
        _wait_for_key_input_jitter()
        try:
            keyboard_output.keyDown(key)
        except _FAILSAFE_EXCEPTIONS:
            logger.warning("[key_down] keyboard backend failsafe triggered during key_down.")
            recover_mouse()
            return False
        _pressed_keys.add(key)
        return True

def key_up(key, force=False):
    '''
    Release key
    '''
    if not key:
        return False

    with _pressed_keys_lock:
        if not force and key not in _pressed_keys:
            return False
        # This delay is part of the key's held duration, so long presses and
        # direction holds receive the same 0.01-0.08 second timing variation.
        _wait_for_key_input_jitter()
        try:
            keyboard_output.keyUp(key)
        except _FAILSAFE_EXCEPTIONS:
            logger.warning("[key_up] keyboard backend failsafe triggered during key_up.")
            recover_mouse()
            return False
        _pressed_keys.discard(key)
        return True

def recover_mouse():
    '''
    Move mouse back to center to avoid pyautogui failsafe
    '''
    pyautogui.FAILSAFE = False # Temp disasble failsafe to avoid nested exception
    keyboard_output.FAILSAFE = False

    screen_w, screen_h = pyautogui.size()
    pyautogui.moveTo(screen_w // 2, screen_h // 2)
    time.sleep(0.2) # Give it a moment to "cool down"

    pyautogui.FAILSAFE = True # Recover failsafe
    keyboard_output.FAILSAFE = True

def press_key(key, duration=0.05):
    '''
    Simulates a key press for a specified duration
    '''
    if key and key_down(key):
        time.sleep(duration)
        key_up(key)


def press_hotkey(*keys, duration=0.05):
    """Press a key combination and always release it in reverse order."""
    pressed = []
    try:
        for key in keys:
            if key and key_down(key):
                pressed.append(key)
        time.sleep(duration)
    finally:
        for key in reversed(pressed):
            key_up(key)

class KeyBoardController():
    '''
    KeyBoardController
    '''
    def __init__(self, cfg):
        self.cfg = cfg
        self.cmd_action = "none"
        self.cmd_up_down = "none"
        self.cmd_left_right = "none"
        self.cmd_up_down_last = ""
        self.cmd_left_right_last = ""
        # Last horizontal direction actually delivered to the game. Releasing
        # a movement key does not change the direction the character faces.
        self.facing_direction = None
        self.t_last_direction_input = 0.0
        self.window_title = cfg["game_window"]["title"]
        self.fps = 0 # Frame per seconds
        # Timer
        self.t_last_up = 0.0
        self.t_last_down = 0.0
        self.t_last_toggle = 0.0
        self.t_last_screenshot = 0.0
        self.t_last_jump_down = 0.0
        self.t_last_run = time.time()
        self.t_last_skill = 0.0 # Last time character perform action(attack, cast spell, ...)
        self.t_last_aoe_press = 0.0
        self.suppress_jump = False  # smart_patrol edge: skip jump in jump-attack
        self._jump_attack_pending = None  # {"key": str, "fire_at": float, "is_aoe": bool}
        self._jump_attack_hold_dir = None  # left|right held across jump-attack delay
        self.t_last_buff_cast = [0] * len(self.cfg["buff_skill"]["keys"]) # Last time cast buff skill
        self.t_last_profession_action = {}
        # Flags
        self.is_enable = True
        self.is_need_force_heal = False
        self.is_terminated = False
        # Parameters
        self.debounce_interval = self.cfg["system"]["key_debounce_interval"]
        self.fps_limit = self.cfg["system"]["fps_limit_keyboard_controller"]

        # use 'ctrl', 'alt' for mac, because it's hard to get around
        # macOS's security settings
        if is_mac():
            self.toggle_key = keyboard.Key.ctrl
            self.screenshot_key = keyboard.Key.alt
            self.terminate_key = keyboard.Key.esc
        else:
            self.toggle_key = keyboard.Key.f1
            self.screenshot_key = keyboard.Key.f2
            self.terminate_key = keyboard.Key.f12

        # set up attack key
        self.attack_key = ""
        if cfg["bot"]["attack"] == "aoe_skill":
            self.attack_key = cfg["key"]["aoe_skill"]
        elif cfg["bot"]["attack"] in ("directional", "hybrid"):
            self.attack_key = cfg["key"]["directional_attack"]
        else:
            raise ValueError(f"Unexpected attack type: {cfg['bot']['attack']}")

        # Start keyboard control thread
        threading.Thread(target=self.run, daemon=True).start()

        logger.info("[KeyBoardController] Init done")

    def toggle_enable(self):
        '''
        toggle_enable
        '''
        self.is_enable = not self.is_enable
        logger.info(f"Player pressed F1, is_enable:{self.is_enable}")

        # Make sure all key are released
        self.release_all_key()

    def disable(self):
        '''
        disable keyboard controlller
        '''
        self.is_enable = False

    def enable(self):
        '''
        enable keyboard controlller
        '''
        self.is_enable = True

    def set_command(self, new_command):
        '''
        Set keyboard command
        '''
        self.cmd_left_right, self.cmd_up_down, self.cmd_action = new_command.split()

    def trigger_profession_action(self, action_id):
        """Press the game key bound to a semantic profession action."""
        key = resolve_profession_binding(self.cfg, action_id)
        if not key:
            logger.warning(
                f"[KeyBoardController] No key is bound to profession action: {action_id}"
            )
            return False
        press_key(key)
        self.t_last_skill = time.time()
        self.t_last_aoe_press = 0.0
        logger.info(
            f"[KeyBoardController] Trigger profession action '{action_id}' with key '{key}'"
        )
        return True

    def is_game_window_active(self):
        '''
        Check if the game window is currently the active (foreground) window.

        Returns:
        - True
        - False
        '''
        if is_mac():
            active_window = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID
            )
            for window in active_window:
                window_name = window.get(Quartz.kCGWindowName, '')
                if window_name and self.window_title in window_name:
                    return True
            return False
        else:
            try:
                active_window = gw.getActiveWindow()
                if not active_window:
                    return False
                return self.window_title in active_window.title
            except Exception as e:
                return False

    def release_all_key(self):
        '''
        Release all key
        '''
        key_up("left", force=True)
        key_up("right", force=True)
        key_up("up", force=True)
        key_up("down", force=True)
        # Also release attack keys to stop any ongoing attacks
        key_up(self.attack_key, force=True)

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


    def _jump_attack_enabled(self):
        raw = self.cfg.get("bot", {}).get("jump_attack", False)
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)

    def _jump_attack_delay(self):
        bot = self.cfg.get("bot", {}) if isinstance(self.cfg.get("bot"), dict) else {}
        lo = float(bot.get("jump_attack_delay_min", 0.04) or 0.04)
        hi = float(bot.get("jump_attack_delay_max", 0.15) or 0.15)
        if hi < lo:
            lo, hi = hi, lo
        lo = max(0.01, lo)
        hi = max(lo, hi)
        return random.uniform(lo, hi)

    def _cancel_jump_attack_pending(self):
        self._jump_attack_pending = None
        self._jump_attack_hold_dir = None

    def _schedule_jump_attack(self, attack_key, is_aoe=False):
        """Tap jump once, keep move keys held, fire attack after random delay."""
        # Prefer current move command, else last facing, for hold during delay.
        hold = None
        if self.cmd_left_right in ("left", "right"):
            hold = self.cmd_left_right
        elif getattr(self, "facing_direction", None) in ("left", "right"):
            hold = self.facing_direction
        self._jump_attack_hold_dir = hold
        if hold:
            key_down(hold)
        jump_key = self.cfg.get("key", {}).get("jump", "")
        if jump_key:
            press_key(jump_key)
        delay = self._jump_attack_delay()
        self._jump_attack_pending = {
            "key": attack_key,
            "fire_at": time.time() + delay,
            "is_aoe": bool(is_aoe),
        }
        logger.info(
            f"[KeyBoardController] Jump-attack: jump then attack '{attack_key}' "
            f"in {delay:.2f}s (move held)"
        )

    def _maybe_fire_jump_attack(self):
        pending = self._jump_attack_pending
        if not pending:
            return
        if time.time() < float(pending.get("fire_at", 0.0)):
            return
        attack_key = pending.get("key") or ""
        is_aoe = bool(pending.get("is_aoe"))
        self._jump_attack_pending = None
        self._jump_attack_hold_dir = None
        if not attack_key:
            return
        now = time.time()
        if is_aoe:
            min_gap = 0.7
            if now - float(getattr(self, "t_last_aoe_press", 0.0)) < min_gap:
                return
            press_key(attack_key)
            self.t_last_aoe_press = now
            self.t_last_skill = now
            logger.info(
                f"[KeyBoardController] Jump-attack AoE press key: '{attack_key}'"
            )
        else:
            press_key(attack_key)
            self.t_last_skill = now

    def _press_combat_attack(self, attack_key, is_aoe=False):
        """Press attack, optionally as jump-then-attack while movement stays held."""
        if not attack_key:
            return False
        if self._jump_attack_enabled() and not bool(getattr(self, "suppress_jump", False)):
            # Cancel any stale pending combo; start a fresh jump -> delay -> hit.
            self._schedule_jump_attack(attack_key, is_aoe=is_aoe)
            return True
        # Edge / jump suppressed / mode off: attack in place only.
        self._cancel_jump_attack_pending()
        now = time.time()
        if is_aoe:
            min_gap = 0.7
            if now - float(getattr(self, "t_last_aoe_press", 0.0)) < min_gap:
                return False
            press_key(attack_key)
            self.t_last_aoe_press = now
            self.t_last_skill = now
            logger.info(
                f"[KeyBoardController] AoE attack press key: '{attack_key}'"
            )
        else:
            press_key(attack_key)
            self.t_last_skill = now
        return True

    def run(self):
        '''
        run
        '''
        while not self.is_terminated:
            # Check if game window is active
            if not self.is_enable or not self.is_game_window_active():
                self.limit_fps()
                continue

            # Buff skill
            for i, buff_skill_key in enumerate(self.cfg["buff_skill"]["keys"]):
                cooldown = self.cfg["buff_skill"]["cooldown"][i]
                if time.time() - self.t_last_buff_cast[i] >= cooldown and \
                    time.time() - self.t_last_skill > self.cfg["buff_skill"]["action_cooldown"]:
                    press_key(buff_skill_key)
                    logger.info(f"[Buff] Press buff skill key: '{buff_skill_key}' (cooldown: {cooldown}s)")
                    # Reset timers
                    self.t_last_buff_cast[i] = time.time()
                    self.t_last_skill = time.time()
                    break

            # Profession actions with independent timers. Pet feeding is kept
            # separate from BUFF so both can use different keys and intervals.
            profession = self.cfg.get("profession", {})
            bindings = profession.get("bindings", {}) if isinstance(profession, dict) else {}
            intervals = profession.get("intervals", {}) if isinstance(profession, dict) else {}
            pet_food_key = bindings.get("pet_food", "") if isinstance(bindings, dict) else ""
            if pet_food_key:
                interval = max(1, int(intervals.get("pet_food", 600)))
                last_triggered = self.t_last_profession_action.get("pet_food", 0)
                if (
                    time.time() - last_triggered >= interval
                    and time.time() - self.t_last_skill
                    > self.cfg["buff_skill"]["action_cooldown"]
                ):
                    press_key(pet_food_key)
                    now = time.time()
                    self.t_last_profession_action["pet_food"] = now
                    self.t_last_skill = now
                    logger.info(
                        f"[PetFood] Press pet food key: '{pet_food_key}' "
                        f"(interval: {interval}s)"
                    )

            # Force Heal: cancel other actions; HealthMonitor owns multi-press potions
            if self.is_need_force_heal:
                self.cmd_action = "none"

            ##########################
            ### Left-Right Command ###
            ##########################
            # During jump-attack delay, keep pathfinding direction held.
            if self._jump_attack_pending and self._jump_attack_hold_dir in ("left", "right"):
                if self.cmd_left_right in ("none", "stop", ""):
                    self.cmd_left_right = self._jump_attack_hold_dir
            if self.cmd_left_right == "left":
                key_up("right")
                if key_down("left"):
                    self.facing_direction = "left"
                    self.t_last_direction_input = time.time()
            elif self.cmd_left_right == "right":
                key_up("left")
                if key_down("right"):
                    self.facing_direction = "right"
                    self.t_last_direction_input = time.time()
            elif self.cmd_left_right == "stop":
                key_up("left")
                key_up("right")
            elif self.cmd_left_right == "none":
                if self.cmd_left_right_last != "none":
                    key_up("left")
                    key_up("right")
            else:
                logger.error("[KeyBoardController] Unsupported left-right command: "
                             f"{self.cmd_left_right}")
            self.cmd_left_right_last = self.cmd_left_right

            #######################
            ### Up-Down Command ###
            #######################
            if self.cmd_up_down == "up":
                key_up("down")
                key_down("up")
            elif self.cmd_up_down == "down":
                key_up("up")
                key_down("down")
            elif self.cmd_up_down == "stop":
                key_up("up")
                key_up("down")
            elif self.cmd_up_down == "none":
                if self.cmd_up_down_last != "none":
                    key_up("up")
                    key_up("down")
            else:
                logger.error("[KeyBoardController] Unsupported up-down command: "
                             f"{self.cmd_up_down}")
            self.cmd_up_down_last = self.cmd_up_down

            ######################
            ### Action Command ###
            ######################
            # One-shot actions: press once then clear. Leaving jump/attack/
            # teleport/aoe_attack sticky made the keyboard FPS loop re-press
            # the same key every frame (AoE 'c' spam / higher 测谎 risk).
            # Complete scheduled jump-attack hit while direction keys stay held.
            self._maybe_fire_jump_attack()

            if self.cmd_action == "jump":
                # Standalone jump (route/scan) cancels pending jump-attack.
                self._cancel_jump_attack_pending()
                press_key(self.cfg["key"]["jump"])
                self.cmd_action = "none"
            elif self.cmd_action == "teleport":
                self._cancel_jump_attack_pending()
                press_key(self.cfg["key"]["teleport"])
                self.cmd_action = "none"
            elif self.cmd_action == "attack":
                self._press_combat_attack(self.attack_key, is_aoe=False)
                self.cmd_action = "none"
            elif self.cmd_action == "aoe_attack":
                # Hybrid AoE uses a separate key from directional attack_key.
                aoe_key = self.cfg.get("key", {}).get("aoe_skill", "")
                if aoe_key:
                    self._press_combat_attack(aoe_key, is_aoe=True)
                else:
                    logger.warning(
                        "[KeyBoardController] aoe_attack requested but "
                        "key.aoe_skill is empty"
                    )
                self.cmd_action = "none"
            elif self.cmd_action == "add_hp":
                press_key(self.cfg["key"]["add_hp"])
                self.cmd_action = "none"  # Reset command
            elif self.cmd_action == "add_mp":
                press_key(self.cfg["key"]["add_mp"])
                self.cmd_action = "none"  # Reset command
            elif self.cmd_action == "goal":
                pass
            elif self.cmd_action == "none":
                pass
            elif resolve_profession_binding(self.cfg, self.cmd_action):
                # Profession-labelled actions are one-shot commands. For
                # example: "none none secondary_attack_1".
                self.trigger_profession_action(self.cmd_action)
                self.cmd_action = "none"
            else:
                logger.error("[KeyBoardController] Unsupported action command: "
                             f"{self.cmd_action}")

            self.limit_fps()

        self.release_all_key() # Prevent key keep press down after termination

        logger.info("[KeyBoardController] terminated")
