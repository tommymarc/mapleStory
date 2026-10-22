# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(".").resolve()

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")
    print("updated", rel)

eng = read("src/engine/MapleStoryAutoLevelUp.py")

# Helper method near _pulse_direction_then_attack
if "_jump_attack_enabled" not in eng:
    eng = eng.replace(
        '    def _reset_directional_attack_turn(self):\n',
        '''    def _jump_attack_enabled(self):
        raw = self.cfg.get("bot", {}).get("jump_attack", False) if isinstance(self.cfg, dict) else False
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)

    def _reset_directional_attack_turn(self):\n''',
        1,
    )

# Keep move held when delivering directional attack under jump-attack mode
old = (
        '        self.cmd_move_x = "none"\n'
        '        self.cmd_action = "attack"\n'
        '        self.t_last_attack = now\n'
        '        self._reset_directional_attack_turn()\n'
        '        # Refresh engage window on each delivered attack\n'
        '        self._set_engage(attack_direction, now=now)\n'
        '        logger.debug(\n'
        '            f"[Directional Attack] Facing {attack_direction}; attack delivered."\n'
        '        )\n'
        '        return True\n'
)
new = (
        '        # Jump-attack: keep holding attack_direction so move stays down\n'
        '        # through tap-jump -> delay -> tap-hit. Otherwise release move.\n'
        '        if self._jump_attack_enabled() and not bool(getattr(self, "suppress_jump", False)):\n'
        '            self.cmd_move_x = attack_direction\n'
        '        else:\n'
        '            self.cmd_move_x = "none"\n'
        '        self.cmd_action = "attack"\n'
        '        self.t_last_attack = now\n'
        '        self._reset_directional_attack_turn()\n'
        '        # Refresh engage window on each delivered attack\n'
        '        self._set_engage(attack_direction, now=now)\n'
        '        logger.debug(\n'
        '            f"[Directional Attack] Facing {attack_direction}; attack delivered."\n'
        '        )\n'
        '        return True\n'
)
if old not in eng:
    raise SystemExit("directional deliver block not found")
eng = eng.replace(old, new, 1)

# Hybrid AoE: keep engage side / previous move when jump-attack
old_aoe = (
                    '                    self._reset_directional_attack_turn()\n'
                    '                    self.cmd_move_x = "none"\n'
                    '                    self.cmd_move_y = "none"\n'
                    '                    self.cmd_action = "aoe_attack"\n'
)
new_aoe = (
                    '                    self._reset_directional_attack_turn()\n'
                    '                    # Jump-attack: keep horizontal move held during jump->AoE combo.\n'
                    '                    side = getattr(self, "engage_side", None)\n'
                    '                    if (self._jump_attack_enabled()\n'
                    '                            and not bool(getattr(self, "suppress_jump", False))\n'
                    '                            and side in ("left", "right")):\n'
                    '                        self.cmd_move_x = side\n'
                    '                    else:\n'
                    '                        self.cmd_move_x = "none"\n'
                    '                    self.cmd_move_y = "none"\n'
                    '                    self.cmd_action = "aoe_attack"\n'
)
if old_aoe not in eng:
    raise SystemExit("hybrid aoe block not found")
eng = eng.replace(old_aoe, new_aoe, 1)

# Pure aoe_skill attack - also keep move if any
# Looking at aoe_skill path: only sets cmd_action = attack, doesn't clear move - OK

write("src/engine/MapleStoryAutoLevelUp.py", eng)

# KB: while jump-attack pending, force-hold the scheduled direction
kb = read("src/input/KeyBoardController.py")
if "_jump_attack_hold_dir" not in kb:
    kb = kb.replace(
        '        self._jump_attack_pending = None  # {"key": str, "fire_at": float, "is_aoe": bool}\n',
        '        self._jump_attack_pending = None  # {"key": str, "fire_at": float, "is_aoe": bool}\n'
        '        self._jump_attack_hold_dir = None  # left|right held across jump-attack delay\n',
        1,
    )
    kb = kb.replace(
        '    def _cancel_jump_attack_pending(self):\n'
        '        self._jump_attack_pending = None\n',
        '    def _cancel_jump_attack_pending(self):\n'
        '        self._jump_attack_pending = None\n'
        '        self._jump_attack_hold_dir = None\n',
        1,
    )
    kb = kb.replace(
        '        jump_key = self.cfg.get("key", {}).get("jump", "")\n'
        '        if jump_key:\n'
        '            press_key(jump_key)\n'
        '        delay = self._jump_attack_delay()\n'
        '        self._jump_attack_pending = {\n'
        '            "key": attack_key,\n'
        '            "fire_at": time.time() + delay,\n'
        '            "is_aoe": bool(is_aoe),\n'
        '        }\n',
        '        # Prefer current move command, else last facing, for hold during delay.\n'
        '        hold = None\n'
        '        if self.cmd_left_right in ("left", "right"):\n'
        '            hold = self.cmd_left_right\n'
        '        elif getattr(self, "facing_direction", None) in ("left", "right"):\n'
        '            hold = self.facing_direction\n'
        '        self._jump_attack_hold_dir = hold\n'
        '        if hold:\n'
        '            key_down(hold)\n'
        '        jump_key = self.cfg.get("key", {}).get("jump", "")\n'
        '        if jump_key:\n'
        '            press_key(jump_key)\n'
        '        delay = self._jump_attack_delay()\n'
        '        self._jump_attack_pending = {\n'
        '            "key": attack_key,\n'
        '            "fire_at": time.time() + delay,\n'
        '            "is_aoe": bool(is_aoe),\n'
        '        }\n',
        1,
    )
    # After firing attack, clear hold dir (engine will re-issue move next frame)
    kb = kb.replace(
        '        self._jump_attack_pending = None\n'
        '        if not attack_key:\n'
        '            return\n'
        '        now = time.time()\n'
        '        if is_aoe:\n',
        '        self._jump_attack_pending = None\n'
        '        self._jump_attack_hold_dir = None\n'
        '        if not attack_key:\n'
        '            return\n'
        '        now = time.time()\n'
        '        if is_aoe:\n',
        1,
    )

    # In left-right command section: if pending hold, don't release that key on "none"
    # Find the none branch for left-right
    marker = '            ### Horizontal Movement ###'
    # Actually look for cmd_left_right == "none"
    old_lr_none = None
    lines = kb.splitlines()
    for i,l in enumerate(lines):
        if 'elif self.cmd_left_right == "none"' in l or (l.strip() == 'elif self.cmd_left_right == "none":'):
            # show context
            pass
    # Use a safer approach: before processing left-right, if pending hold, override cmd
    inject = (
        '            ########################\n'
        '            ### Left-Right Command ###\n'
    )
    # Find actual section header in file
    for i,l in enumerate(kb.splitlines()):
        if 'Left-Right' in l or 'left-right' in l.lower() or 'Horizontal' in l:
            print('LINE', i+1, l)

    write("src/input/KeyBoardController.py", kb)
    print("partial KB hold-dir done; need inject override")
else:
    print("hold dir already present")

print("engine OK")
