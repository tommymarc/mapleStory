# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(".").resolve()

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")
    print("updated", rel)

# ---------- KeyBoardController.py ----------
kb = read("src/input/KeyBoardController.py")
if "_maybe_fire_jump_attack" not in kb:
    # init fields after t_last_skill
    kb = kb.replace(
        '        self.t_last_skill = 0.0 # Last time character perform action(attack, cast spell, ...)\n'
        '        self.t_last_buff_cast = [0] * len(self.cfg["buff_skill"]["keys"]) # Last time cast buff skill\n',
        '        self.t_last_skill = 0.0 # Last time character perform action(attack, cast spell, ...)\n'
        '        self.t_last_aoe_press = 0.0\n'
        '        self.suppress_jump = False  # smart_patrol edge: skip jump in jump-attack\n'
        '        self._jump_attack_pending = None  # {"key": str, "fire_at": float, "is_aoe": bool}\n'
        '        self.t_last_buff_cast = [0] * len(self.cfg["buff_skill"]["keys"]) # Last time cast buff skill\n',
        1,
    )

    # helpers before run()
    helper = '''
    def _jump_attack_enabled(self):
        raw = self.cfg.get("bot", {}).get("jump_attack", False)
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)

    def _jump_attack_delay(self):
        bot = self.cfg.get("bot", {}) if isinstance(self.cfg.get("bot"), dict) else {}
        lo = float(bot.get("jump_attack_delay_min", 0.1) or 0.1)
        hi = float(bot.get("jump_attack_delay_max", 0.8) or 0.8)
        if hi < lo:
            lo, hi = hi, lo
        lo = max(0.05, lo)
        hi = max(lo, hi)
        return random.uniform(lo, hi)

    def _cancel_jump_attack_pending(self):
        self._jump_attack_pending = None

    def _schedule_jump_attack(self, attack_key, is_aoe=False):
        """Tap jump once, keep move keys held, fire attack after random delay."""
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

'''
    if "def run(self):" not in kb:
        raise SystemExit("run() not found")
    kb = kb.replace("    def run(self):\n", helper + "    def run(self):\n", 1)

    # At start of enabled loop body, fire pending jump-attack (after buffs is also ok;
    # put right before Action Command section so move keys already updated this frame)
    # Replace attack / aoe_attack handlers
    old_actions = '''            if self.cmd_action == "jump":
                press_key(self.cfg["key"]["jump"])
                self.cmd_action = "none"
            elif self.cmd_action == "teleport":
                press_key(self.cfg["key"]["teleport"])
                self.cmd_action = "none"
            elif self.cmd_action == "attack":
                press_key(self.attack_key)
                self.t_last_skill = time.time()
                self.cmd_action = "none"
            elif self.cmd_action == "aoe_attack":
                # Hybrid AoE uses a separate key from directional attack_key.
                aoe_key = self.cfg.get("key", {}).get("aoe_skill", "")
                now = time.time()
                # Hard min interval even if engine re-sends aoe_attack.
                # Match engine hybrid AoE floor (>=0.7s) near attack recovery.
                min_gap = 0.7
                if aoe_key and (now - float(getattr(self, "t_last_aoe_press", 0.0)) >= min_gap):
                    press_key(aoe_key)
                    self.t_last_aoe_press = now
                    self.t_last_skill = now
                    logger.info(
                        f"[KeyBoardController] AoE attack press key: '{aoe_key}'"
                    )
                elif not aoe_key:
                    logger.warning(
                        "[KeyBoardController] aoe_attack requested but "
                        "key.aoe_skill is empty"
                    )
                self.cmd_action = "none"
'''
    new_actions = '''            # Complete scheduled jump-attack hit while direction keys stay held.
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
'''
    if old_actions not in kb:
        raise SystemExit("attack action block not found for replacement")
    kb = kb.replace(old_actions, new_actions, 1)

    # If t_last_aoe_press was already declared elsewhere, avoid duplicate
    # Check for double declaration
    if kb.count("self.t_last_aoe_press = 0.0") > 1:
        # keep first in __init__, remove later duplicates that aren't assignment in methods
        pass

    write("src/input/KeyBoardController.py", kb)
else:
    print("KeyBoardController already patched")

print("OK KB")
