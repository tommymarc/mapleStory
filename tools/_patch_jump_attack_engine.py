# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(".").resolve()

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")
    print("updated", rel)

# ---------- MapleStoryAutoLevelUp.py: init suppress_jump + sync to kb ----------
eng = read("src/engine/MapleStoryAutoLevelUp.py")
if "suppress_jump" not in eng:
    eng = eng.replace(
        '        self.cmd_action = "none" # "jump" "attack" ....\n',
        '        self.cmd_action = "none" # "jump" "attack" ....\n'
        '        self.suppress_jump = False  # Near patrol edge: jump-attack becomes attack-only\n',
        1,
    )
    eng = eng.replace(
        '        if getattr(self, "kb", None) is not None:\n'
        '            self.kb.set_command(\n'
        '                self.cmd_move_x + \' \' + self.cmd_move_y + \' \' + self.cmd_action\n'
        '            )\n'
        '        return True\n',
        '        if getattr(self, "kb", None) is not None:\n'
        '            self.kb.suppress_jump = bool(getattr(self, "suppress_jump", False))\n'
        '            self.kb.set_command(\n'
        '                self.cmd_move_x + \' \' + self.cmd_move_y + \' \' + self.cmd_action\n'
        '            )\n'
        '        return True\n',
        1,
    )
    write("src/engine/MapleStoryAutoLevelUp.py", eng)
else:
    print("engine already has suppress_jump")

# ---------- smart_patrol.py ----------
sp = read("src/states/smart_patrol.py")
if "suppress_jump" not in sp:
    # Before final set_command, update suppress_jump from edge flags
    old = (
        '        # Final hard clamp for Scan/Engage so chase/random never walks past range.\n'
        '        if self.phase != PHASE_RETURN:\n'
        '            self._enforce_x_bounds(allow_outside_for_return=False)\n'
        '\n'
        '        self.bot.kb.set_command(\n'
        '            self.bot.cmd_move_x + " " + self.bot.cmd_move_y + " " + self.bot.cmd_action\n'
        '        )\n'
    )
    new = (
        '        # Final hard clamp for Scan/Engage so chase/random never walks past range.\n'
        '        if self.phase != PHASE_RETURN:\n'
        '            self._enforce_x_bounds(allow_outside_for_return=False)\n'
        '\n'
        '        # Near/past patrol bounds: do not jump outward during jump-attack.\n'
        '        ratio, left_r, right_r, at_left, at_right, past_left, past_right = self._edge_flags()\n'
        '        near_edge = False\n'
        '        if ratio is not None:\n'
        '            near_edge = bool(\n'
        '                at_left or at_right or past_left or past_right\n'
        '                or self._near_patrol_edge(ratio, left_r, right_r)\n'
        '            )\n'
        '        self.bot.suppress_jump = near_edge\n'
        '        if getattr(self.bot, "kb", None) is not None:\n'
        '            self.bot.kb.suppress_jump = near_edge\n'
        '            self.bot.kb.set_command(\n'
        '                self.bot.cmd_move_x + " " + self.bot.cmd_move_y + " " + self.bot.cmd_action\n'
        '            )\n'
        '        else:\n'
        '            pass\n'
    )
    # The original always called set_command; replace carefully
    if old not in sp:
        # try without the comment variation
        raise SystemExit("smart_patrol set_command block not found")
    # Keep the cmd_action clear after set_command
    # Need to include following lines
    old2 = old + (
        '        if self.bot.cmd_action in ("jump", "teleport", "attack", "aoe_attack"):\n'
        '            self.bot.cmd_action = "none"\n'
    )
    new2 = (
        '        # Final hard clamp for Scan/Engage so chase/random never walks past range.\n'
        '        if self.phase != PHASE_RETURN:\n'
        '            self._enforce_x_bounds(allow_outside_for_return=False)\n'
        '\n'
        '        # Near/past patrol bounds: jump-attack becomes attack-only (no outward jump).\n'
        '        ratio, left_r, right_r, at_left, at_right, past_left, past_right = self._edge_flags()\n'
        '        near_edge = False\n'
        '        if ratio is not None:\n'
        '            near_edge = bool(\n'
        '                at_left or at_right or past_left or past_right\n'
        '                or self._near_patrol_edge(ratio, left_r, right_r)\n'
        '            )\n'
        '        self.bot.suppress_jump = near_edge\n'
        '        if getattr(self.bot, "kb", None) is not None:\n'
        '            self.bot.kb.suppress_jump = near_edge\n'
        '            self.bot.kb.set_command(\n'
        '                self.bot.cmd_move_x + " " + self.bot.cmd_move_y + " " + self.bot.cmd_action\n'
        '            )\n'
        '        if self.bot.cmd_action in ("jump", "teleport", "attack", "aoe_attack"):\n'
        '            self.bot.cmd_action = "none"\n'
    )
    if old2 not in sp:
        raise SystemExit("smart_patrol full trailing block not found")
    sp = sp.replace(old2, new2, 1)
    write("src/states/smart_patrol.py", sp)
else:
    print("smart_patrol already patched")

print("OK engine/patrol")
