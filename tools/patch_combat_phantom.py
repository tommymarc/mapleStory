# -*- coding: utf-8 -*-
"""Fix phantom swings + walk-through / stand-idle near mobs (剑客)."""
from __future__ import annotations
from pathlib import Path
import py_compile
import re
import shutil
import time

ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ENG = ROOT / "src" / "engine" / "MapleStoryAutoLevelUp.py"
PROF = ROOT / "src" / "ui" / "profession_config.py"
YAML_PATHS = [
    ROOT / "config" / "config_professions.yaml",
    ROOT / "dist" / "config" / "config_professions.yaml",
]
MARKER = "COMBAT_LIVE_ONLY_ATTACK_V1"


def patch_engine(text: str) -> str:
    if MARKER in text:
        print("engine already patched")
        return text

    # 1) Miss grace: stand, do NOT pulse attack (phantom swings)
    old_grace = '''                self.cmd_move_x = "none"
                self.cmd_move_y = "none"
                self.cmd_action = "none"
                self._pulse_direction_then_attack(
                    self.engage_side, cooldown, now=now
                )
                return
'''
    new_grace = '''                # ''' + MARKER + ''' miss-grace: hold feet, never swing at empty air
                self.cmd_move_x = "none"
                self.cmd_move_y = "none"
                self.cmd_action = "none"
                return
'''
    if old_grace not in text:
        raise SystemExit("miss-grace pulse block not found")
    text = text.replace(old_grace, new_grace, 1)
    print("patched: miss-grace no attack")

    # 2) Directional attack: nearest from LIVE only (soft is for debug/TTL UI)
    old_near = '''            # Get nearest monster to player (uses decision_monsters: live±soft)
            monster_left  = self.get_nearest_monster(is_left = True)
            monster_right = self.get_nearest_monster(is_left = False)
'''
    new_near = '''            # Get nearest monster from LIVE detections only — soft/ghosts caused
            # phantom swings after kill/run. Soft tracks remain for overlays.
            monster_left  = self.get_nearest_monster(
                is_left=True, monsters=self.monsters
            )
            monster_right = self.get_nearest_monster(
                is_left=False, monsters=self.monsters
            )
'''
    if old_near not in text:
        raise SystemExit("nearest monster block not found")
    text = text.replace(old_near, new_near, 1)
    print("patched: live-only nearest")

    # 3) Attack boxes: small center overlap so "walk through" / on-top still hits
    old_range = '''        elif self.cfg["bot"]["attack"] in ("directional", "hybrid"):
            if is_left:
                x0 = max(
                    0,
                    self.loc_player[0] - self.cfg["directional_attack"]["range_x"],
                )
                x1 = self.loc_player[0]
            else:
                x0 = self.loc_player[0]
                x1 = min(
                    self.img_frame.shape[1],
                    x0 + self.cfg["directional_attack"]["range_x"],
                )
            half_height = self.cfg["directional_attack"]["range_y"] // 2
            y0 = max(0, self.loc_player[1] - half_height)
            y1 = min(self.img_frame.shape[0], self.loc_player[1] + half_height)
'''
    new_range = '''        elif self.cfg["bot"]["attack"] in ("directional", "hybrid"):
            # Overlap a few px across the player so a mob underfoot is not
            # lost between left/right boxes (walk-through / stand-on).
            overlap = 12
            if is_left:
                x0 = max(
                    0,
                    self.loc_player[0] - self.cfg["directional_attack"]["range_x"],
                )
                x1 = min(
                    self.img_frame.shape[1],
                    self.loc_player[0] + overlap,
                )
            else:
                x0 = max(0, self.loc_player[0] - overlap)
                x1 = min(
                    self.img_frame.shape[1],
                    self.loc_player[0] + self.cfg["directional_attack"]["range_x"],
                )
            half_height = self.cfg["directional_attack"]["range_y"] // 2
            y0 = max(0, self.loc_player[1] - half_height)
            y1 = min(self.img_frame.shape[0], self.loc_player[1] + half_height)
'''
    if old_range not in text:
        raise SystemExit("get_attack_range directional block not found")
    text = text.replace(old_range, new_range, 1)
    print("patched: attack box overlap")

    # 4) Side check: allow near-center mobs
    old_side = '''            if direction == "left":
                return monster_center_x < player_x  # Monster should be left of player
            else:  # direction == "right"
                return monster_center_x > player_x  # Monster should be right of player
'''
    new_side = '''            # Allow near-center (underfoot) to count for either asked side.
            if abs(monster_center_x - player_x) <= 12:
                return True
            if direction == "left":
                return monster_center_x < player_x  # Monster should be left of player
            else:  # direction == "right"
                return monster_center_x > player_x  # Monster should be right of player
'''
    if old_side not in text:
        raise SystemExit("side check not found")
    text = text.replace(old_side, new_side, 1)
    print("patched: underfoot side ok")

    # 5) Soft decision: never merge soft into decision when live empty for attack
    # Keep soft for overlays but make decision live-only always when track on
    old_soft = '''        soft_when_live_max = self._monster_track_soft_when_live_max()
        if len(live) > soft_when_live_max:
            self.decision_monsters = list(live)
        else:
            self.decision_monsters = list(live) + list(soft)
        return self.decision_monsters
'''
    new_soft = '''        # Attack path uses live-only (see update_cmd_by_mob_detection). Soft is
        # kept for overlays / diagnostics, not for swing decisions.
        soft_when_live_max = self._monster_track_soft_when_live_max()
        if len(live) > soft_when_live_max:
            self.decision_monsters = list(live)
        else:
            # Still expose soft in decision_monsters for engage-empty checks that
            # only need "recently saw something", but swings use self.monsters.
            self.decision_monsters = list(live) + list(soft)
        return self.decision_monsters
'''
    if old_soft not in text:
        raise SystemExit("soft merge block not found")
    text = text.replace(old_soft, new_soft, 1)
    print("patched: soft comment (live swings)")

    return text


def patch_sword_yaml(text: str) -> str:
    old = """      combat:
        monster_track_enable: true
        monster_track_ttl_sec: 0.5
      directional_attack:
"""
    new = """      combat:
        monster_track_enable: true
        monster_track_ttl_sec: 0.18
        monster_track_soft_when_live_max: 0
        engage_miss_grace_sec: 0.12
      monster_detect:
        diff_thres: 0.28
      directional_attack:
"""
    if "diff_thres: 0.28" in text and "monster_track_ttl_sec: 0.18" in text:
        print("yaml already tightened")
        return text
    if old not in text:
        # try looser
        if "monster_track_ttl_sec: 0.5" in text:
            text = text.replace("monster_track_ttl_sec: 0.5", "monster_track_ttl_sec: 0.18", 1)
            if "monster_track_soft_when_live_max" not in text.split("剑客")[1].split("战士")[0]:
                text = text.replace(
                    "monster_track_ttl_sec: 0.18\n",
                    "monster_track_ttl_sec: 0.18\n        monster_track_soft_when_live_max: 0\n        engage_miss_grace_sec: 0.12\n",
                    1,
                )
            if "monster_detect:" not in text.split("剑客")[1].split("战士")[0]:
                text = text.replace(
                    "      directional_attack:\n",
                    "      monster_detect:\n        diff_thres: 0.28\n      directional_attack:\n",
                    1,
                )
            print("yaml patched via fallback")
            return text
        raise SystemExit("sword combat yaml block not found")
    return text.replace(old, new, 1)


def patch_sword_profile(text: str) -> str:
    # Update _sword_profile overrides dict similarly
    # Find combat overrides in _sword_profile
    m = re.search(
        r'("overrides"\s*:\s*\{[\s\S]*?"combat"\s*:\s*\{)([\s\S]*?)(\},)',
        text,
    )
    if not m:
        # try single quotes
        print("WARN: could not regex sword profile combat; try simple replace")
    # Simple replacements inside file for known values
    if '"monster_track_ttl_sec": 0.5' in text:
        text = text.replace('"monster_track_ttl_sec": 0.5', '"monster_track_ttl_sec": 0.18')
        print("profile ttl 0.18")
    if "'monster_track_ttl_sec': 0.5" in text:
        text = text.replace("'monster_track_ttl_sec': 0.5", "'monster_track_ttl_sec': 0.18")
    # inject soft_when_live_max and engage + monster_detect if missing in sword profile
    if "monster_track_soft_when_live_max" not in text:
        text = text.replace(
            '"monster_track_ttl_sec": 0.18',
            '"monster_track_ttl_sec": 0.18,\n'
            '                    "monster_track_soft_when_live_max": 0,\n'
            '                    "engage_miss_grace_sec": 0.12',
        )
        print("profile soft_max + grace")
    if '"monster_detect"' not in text.split("def _sword_profile")[1].split("def ")[0]:
        # insert monster_detect before directional_attack in overrides
        text = text.replace(
            '"directional_attack":',
            '"monster_detect": {"diff_thres": 0.28},\n'
            '                "directional_attack":',
            1,
        )
        print("profile monster_detect thres")
    return text


def main():
    bak = ENG.with_suffix(ENG.suffix + f".bak_combat_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(ENG, bak)
    print("backup", bak)
    eng = patch_engine(ENG.read_text(encoding="utf-8"))
    ENG.write_text(eng, encoding="utf-8")
    py_compile.compile(str(ENG), doraise=True)
    print("engine compile OK")

    for yp in YAML_PATHS:
        if not yp.exists():
            print("missing", yp)
            continue
        t = patch_sword_yaml(yp.read_text(encoding="utf-8"))
        yp.write_text(t, encoding="utf-8")
        print("wrote", yp)

    if PROF.exists():
        pt = patch_sword_profile(PROF.read_text(encoding="utf-8"))
        PROF.write_text(pt, encoding="utf-8")
        py_compile.compile(str(PROF), doraise=True)
        print("profession_config OK")

    print("DONE", MARKER)


if __name__ == "__main__":
    main()
