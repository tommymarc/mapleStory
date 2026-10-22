# -*- coding: utf-8 -*-
"""Smooth stiff 剑客 combat + fix box-but-no-attack overlap gate."""
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
MARKER = "SMOOTH_COMBAT_V1"

# Looser detect + snappier engage feel
SWORD_OVERRIDES = {
    "combat": {
        "monster_track_enable": True,
        "monster_track_ttl_sec": 0.25,
        "monster_track_soft_when_live_max": 0,
        "engage_miss_grace_sec": 0.08,
        "engage_hold_sec": 0.45,
    },
    "monster_detect": {
        "diff_thres": 0.35,
        "max_mob_area_trigger": 400,
        "detect_every_n_frames": 1,
    },
    "directional_attack": {
        "character_turn_delay": 0.02,
        "cooldown": 0.32,
        "range_x": 130,
        "range_y": 80,
        "skip_turn_if_facing": True,
    },
}


def merge_yaml(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sword = data.setdefault("professions", {}).setdefault("剑客", {})
    ov = sword.setdefault("overrides", {})
    for section, vals in SWORD_OVERRIDES.items():
        dst = ov.setdefault(section, {})
        if not isinstance(dst, dict):
            ov[section] = dict(vals)
        else:
            dst.update(vals)
    # keep other sword keys
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("yaml", path.name)
    print(" ", yaml.safe_dump(ov, allow_unicode=True, sort_keys=False).strip()[:400])


def patch_engine(text: str) -> str:
    if MARKER in text:
        print("engine already has", MARKER)
        return text

    # 1) Softer overlap gate (if not already from LOOSEN)
    if "LOOSEN_BOX_ATTACK_V1" not in text and "Require meaningful overlap" not in text:
        old = '''            if inter_area >= inter_area_thres:
                # Compute distance to player center
                monster_center = (mx1 + mw // 2, my1 + mh // 2)
'''
        new = '''            # ''' + MARKER + ''' overlap: don't require near-full template area
            need = min(inter_area_thres, max(80, int(mw * mh * 0.22)))
            if inter_area >= need:
                # Compute distance to player center
                monster_center = (mx1 + mw // 2, my1 + mh // 2)
'''
        if old not in text:
            raise SystemExit("inter_area block missing")
        text = text.replace(old, new, 1)
        print("patched inter_area")
    else:
        print("inter_area already softened")

    # 2) Faster turn path: if skip_turn_if_facing OR pending same side > 1 frame, attack sooner
    # Reduce stall when direction delivery never confirms: after turn_delay*1.5, attack anyway
    old_pulse_tail = '''        if not direction_delivered:
            self.cmd_move_x = attack_direction
            return False
        if now < float(getattr(self, "combat_turn_ready_at", 0.0)):
            return False

        self.cmd_move_x = "none"
        self.cmd_action = "attack"
        self.t_last_attack = now
'''
    new_pulse_tail = '''        # ''' + MARKER + ''': don't freeze forever waiting for KB facing report
        ready_at = float(getattr(self, "combat_turn_ready_at", 0.0))
        force_after = ready_at + max(0.05, turn_delay)
        if not direction_delivered and now < force_after:
            self.cmd_move_x = attack_direction
            return False
        if now < ready_at and direction_delivered:
            return False

        self.cmd_move_x = "none"
        self.cmd_action = "attack"
        self.t_last_attack = now
'''
    if old_pulse_tail not in text:
        # maybe already partially edited
        if "force_after" in text:
            print("pulse already has force_after")
        else:
            raise SystemExit("pulse tail not found")
    else:
        text = text.replace(old_pulse_tail, new_pulse_tail, 1)
        print("patched turn force-attack")

    # 3) Default engage_hold shorter via _engage_hold_sec fallback when combat key set — yaml handles it

    return text


def patch_builtin_profile(text: str) -> str:
    """Best-effort update of _sword_profile numeric literals."""
    reps = [
        ('"monster_track_ttl_sec": 0.18', '"monster_track_ttl_sec": 0.25'),
        ('"monster_track_ttl_sec": 0.5', '"monster_track_ttl_sec": 0.25'),
        ('"diff_thres": 0.28', '"diff_thres": 0.35'),
        ('"character_turn_delay": 0.03', '"character_turn_delay": 0.02'),
        ('"cooldown": 0.35', '"cooldown": 0.32'),
    ]
    for a, b in reps:
        if a in text:
            text = text.replace(a, b)
            print("profile", a, "->", b)
    # inject engage_hold / max_mob if missing in sword profile block
    if "engage_hold_sec" not in text:
        text = text.replace(
            '"engage_miss_grace_sec": 0.12',
            '"engage_miss_grace_sec": 0.08,\n'
            '                    "engage_hold_sec": 0.45',
        )
        text = text.replace(
            '"engage_miss_grace_sec": 0.08',
            '"engage_miss_grace_sec": 0.08,\n'
            '                    "engage_hold_sec": 0.45',
        )
    if "max_mob_area_trigger" not in text.split("def _sword_profile")[-1][:1200]:
        text = text.replace(
            '"monster_detect": {"diff_thres": 0.35}',
            '"monster_detect": {"diff_thres": 0.35, "max_mob_area_trigger": 400}',
        )
        text = text.replace(
            '"monster_detect": {"diff_thres": 0.35, "max_mob_area_trigger": 450}',
            '"monster_detect": {"diff_thres": 0.35, "max_mob_area_trigger": 400}',
        )
    return text


def main():
    for yp in YAMLS:
        if yp.exists():
            merge_yaml(yp)

    bak = ENG.with_suffix(ENG.suffix + f".bak_smooth_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(ENG, bak)
    print("backup", bak)
    eng = patch_engine(ENG.read_text(encoding="utf-8"))
    ENG.write_text(eng, encoding="utf-8")
    py_compile.compile(str(ENG), doraise=True)
    print("engine compile OK")

    if PROF.exists():
        pt = patch_builtin_profile(PROF.read_text(encoding="utf-8"))
        PROF.write_text(pt, encoding="utf-8")
        py_compile.compile(str(PROF), doraise=True)
        print("profession compile OK")

    # quick log peek
    log = ROOT / "_live_diag" / "combat_1min_run.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        print("1min_log_tail:")
        for line in lines[-25:]:
            print(line)

    print("DONE", MARKER)


if __name__ == "__main__":
    main()
