# -*- coding: utf-8 -*-
"""Restore attacking: taller attack box + simpler swing (no KB facing wait)."""
from __future__ import annotations
from pathlib import Path
import py_compile
import shutil
import time
import yaml

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ENG = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"
PROF = ROOT / "src" / "ui" / "profession_config.py"
YAMLS = [
    ROOT / "config" / "config_professions.yaml",
    ROOT / "dist" / "config" / "config_professions.yaml",
]
MARKER = "ATTACK_AGAIN_V1"

SWORD = {
    "combat": {
        "monster_track_enable": True,
        "monster_track_ttl_sec": 0.22,
        "monster_track_soft_when_live_max": 0,
        "engage_miss_grace_sec": 0.08,
        "engage_hold_sec": 0.55,
    },
    "monster_detect": {
        "diff_thres": 0.35,
        "max_mob_area_trigger": 350,
        "detect_every_n_frames": 1,
        "search_box_margin": 60,
    },
    "directional_attack": {
        # Engine uses range_y // 2 as half-height; 160 => ±80 so boxed mobs get hit
        "character_turn_delay": 0.02,
        "cooldown": 0.32,
        "range_x": 140,
        "range_y": 160,
        "skip_turn_if_facing": True,
    },
}


def merge_yaml(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ov = data["professions"]["剑客"].setdefault("overrides", {})
    for sec, vals in SWORD.items():
        dst = ov.setdefault(sec, {})
        if isinstance(dst, dict):
            dst.update(vals)
        else:
            ov[sec] = dict(vals)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("yaml", path.name, ov["directional_attack"])


def patch_engine(text: str) -> str:
    if MARKER in text:
        print("engine already", MARKER)
        return text

    # Replace entire _pulse_direction_then_attack with a reliable simple version
    start = text.find("    def _pulse_direction_then_attack(self, attack_direction, cooldown, now=None):")
    if start < 0:
        raise SystemExit("pulse fn missing")
    end = text.find("\n    def ", start + 1)
    if end < 0:
        raise SystemExit("pulse fn end missing")

    new_fn = '''    def _pulse_direction_then_attack(self, attack_direction, cooldown, now=None):
        """Face then attack — do not stall forever on keyboard facing reports."""
        # ''' + MARKER + '''
        now = time.time() if now is None else now
        if now - self.t_last_attack <= max(0.0, float(cooldown)):
            return False

        turn_delay = max(0.0, float(
            self.cfg["directional_attack"].get("character_turn_delay", 0.06)
        ))
        skip_if_facing = self.cfg["directional_attack"].get(
            "skip_turn_if_facing", False
        )
        if isinstance(skip_if_facing, str):
            skip_if_facing = skip_if_facing.strip().lower() in (
                "1", "true", "yes", "on"
            )
        kb = getattr(self, "kb", None)
        facing = getattr(kb, "facing_direction", None) if kb is not None else None
        if skip_if_facing and facing == attack_direction:
            self.cmd_move_x = "none"
            self.cmd_action = "attack"
            self.t_last_attack = now
            self._reset_directional_attack_turn()
            self._set_engage(attack_direction, now=now)
            return True

        pending_direction = getattr(self, "combat_turn_pending_direction", None)
        if pending_direction != attack_direction:
            self.combat_turn_pending_direction = attack_direction
            self.combat_turn_requested_at = now
            self.combat_turn_ready_at = now + turn_delay
            self.cmd_move_x = attack_direction
            return False

        # After turn_delay, always swing — facing report is best-effort only.
        if now < float(getattr(self, "combat_turn_ready_at", 0.0)):
            self.cmd_move_x = attack_direction
            return False

        self.cmd_move_x = "none"
        self.cmd_action = "attack"
        self.t_last_attack = now
        self._reset_directional_attack_turn()
        self._set_engage(attack_direction, now=now)
        logger.debug(
            f"[Directional Attack] Facing {attack_direction}; attack delivered."
        )
        return True

'''
    text = text[:start] + new_fn + text[end:]
    print("replaced pulse fn")
    return text


def main():
    for yp in YAMLS:
        if yp.exists():
            merge_yaml(yp)
    bak = ENG.with_suffix(ENG.suffix + f".bak_atk_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(ENG, bak)
    eng = patch_engine(ENG.read_text(encoding="utf-8"))
    ENG.write_text(eng, encoding="utf-8")
    py_compile.compile(str(ENG), doraise=True)
    print("engine OK")
    # light profile nudge
    if PROF.exists():
        pt = PROF.read_text(encoding="utf-8")
        pt2 = pt.replace('"range_y": 80', '"range_y": 160').replace("'range_y': 80", "'range_y': 160")
        pt2 = pt2.replace('"range_x": 130', '"range_x": 140').replace("'range_x': 130", "'range_x': 140")
        if pt2 != pt:
            PROF.write_text(pt2, encoding="utf-8")
            py_compile.compile(str(PROF), doraise=True)
            print("profile ranges updated")
    print("DONE", MARKER)


if __name__ == "__main__":
    main()
